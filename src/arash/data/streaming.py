"""Read-only, real-time public order-book streaming for ARASH.

This module subscribes only to public market-data channels. It accepts no exchange
credentials and contains no private-account or order-submission methods.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable

NOBITEX_WEBSOCKET_URL = "wss://ws.nobitex.ir/connection/websocket"
MAX_MESSAGE_BYTES = 2_000_000
MAX_BOOK_LEVELS = 500
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{3,20}$")
ZERO = Decimal("0")


class PublicMarketStreamError(RuntimeError):
    """Public WebSocket connection, protocol or payload error."""


def _valid_symbol(symbol: str) -> str:
    if not isinstance(symbol, str):
        raise ValueError("symbol must be a string")
    normalized = symbol.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(normalized):
        raise ValueError("symbol must contain 3-20 letters or digits, for example BTCIRT")
    return normalized


def _positive_decimal(value: object, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field_name} must be a decimal value") from exc
    if not result.is_finite() or result <= ZERO:
        raise ValueError(f"{field_name} must be finite and greater than zero")
    return result


@dataclass(frozen=True, slots=True)
class BookLevel:
    price: Decimal
    quantity: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "price", _positive_decimal(self.price, "price"))
        object.__setattr__(self, "quantity", _positive_decimal(self.quantity, "quantity"))


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    symbol: str
    source: str
    exchange_timestamp: datetime
    received_at: datetime
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    last_trade_price: Decimal | None
    update_offset: int | None

    def __post_init__(self) -> None:
        normalized = _valid_symbol(self.symbol)
        object.__setattr__(self, "symbol", normalized)
        for field_name in ("exchange_timestamp", "received_at"):
            value = getattr(self, field_name)
            if not isinstance(value, datetime):
                raise ValueError(f"{field_name} must be a datetime")
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
            object.__setattr__(self, field_name, value.astimezone(timezone.utc))
        bids = tuple(self.bids)
        asks = tuple(self.asks)
        if any(not isinstance(level, BookLevel) for level in bids + asks):
            raise ValueError("bids and asks must contain BookLevel values")
        object.__setattr__(self, "bids", tuple(sorted(bids, key=lambda level: level.price, reverse=True)))
        object.__setattr__(self, "asks", tuple(sorted(asks, key=lambda level: level.price)))
        if not self.bids or not self.asks:
            raise ValueError("order book must contain at least one bid and one ask")
        if self.best_bid >= self.best_ask:
            raise ValueError("crossed or locked order book snapshot is not admissible")
        if self.exchange_timestamp > self.received_at + timedelta(seconds=5):
            raise ValueError("exchange timestamp is implausibly far in the future")
        if self.last_trade_price is not None:
            object.__setattr__(
                self, "last_trade_price", _positive_decimal(self.last_trade_price, "last_trade_price")
            )
        if self.update_offset is not None and (
            type(self.update_offset) is not int or self.update_offset < 0
        ):
            raise ValueError("update_offset must be a non-negative integer or None")

    @property
    def best_bid(self) -> Decimal:
        return self.bids[0].price

    @property
    def best_ask(self) -> Decimal:
        return self.asks[0].price

    @property
    def midpoint(self) -> Decimal:
        return (self.best_bid + self.best_ask) / Decimal("2")

    @property
    def spread(self) -> Decimal:
        return self.best_ask - self.best_bid

    @property
    def spread_bps(self) -> Decimal:
        return self.spread / self.midpoint * Decimal("10000")

    def to_dict(self, *, depth_limit: int = 10) -> dict[str, Any]:
        """Serialize top-of-book metrics and a bounded depth view for downstream analysis."""
        if type(depth_limit) is not int or not 1 <= depth_limit <= MAX_BOOK_LEVELS:
            raise ValueError(f"depth_limit must be an integer between 1 and {MAX_BOOK_LEVELS}")
        bids = self.bids[:depth_limit]
        asks = self.asks[:depth_limit]
        bid_quantity = sum((level.quantity for level in bids), ZERO)
        ask_quantity = sum((level.quantity for level in asks), ZERO)
        total_quantity = bid_quantity + ask_quantity
        depth_imbalance = (
            (bid_quantity - ask_quantity) / total_quantity
            if total_quantity > ZERO
            else ZERO
        )
        best_bid_quantity = self.bids[0].quantity
        best_ask_quantity = self.asks[0].quantity
        microprice_denominator = best_bid_quantity + best_ask_quantity
        microprice = (
            (self.best_ask * best_bid_quantity + self.best_bid * best_ask_quantity)
            / microprice_denominator
            if microprice_denominator > ZERO
            else self.midpoint
        )
        return {
            "schema_version": 1,
            "event_type": "public_orderbook_snapshot",
            "source": self.source,
            "symbol": self.symbol,
            "exchange_timestamp": self.exchange_timestamp.isoformat(),
            "received_at": self.received_at.isoformat(),
            "feed_lag_ms": max(0, int((self.received_at - self.exchange_timestamp).total_seconds() * 1000)),
            "clock_skew_ms": int((self.exchange_timestamp - self.received_at).total_seconds() * 1000),
            "update_offset": self.update_offset,
            "best_bid": str(self.best_bid),
            "best_bid_quantity": str(best_bid_quantity),
            "best_ask": str(self.best_ask),
            "best_ask_quantity": str(best_ask_quantity),
            "midpoint": str(self.midpoint),
            "microprice": str(microprice),
            "spread": str(self.spread),
            "spread_bps": str(self.spread_bps),
            "last_trade_price": (
                str(self.last_trade_price) if self.last_trade_price is not None else None
            ),
            "bid_depth_levels_available": len(self.bids),
            "ask_depth_levels_available": len(self.asks),
            "depth_levels_returned": depth_limit,
            "bid_quantity_top_depth": str(bid_quantity),
            "ask_quantity_top_depth": str(ask_quantity),
            "top_depth_imbalance": str(depth_imbalance),
            "bids": [[str(level.price), str(level.quantity)] for level in bids],
            "asks": [[str(level.price), str(level.quantity)] for level in asks],
            "market_metrics_are_descriptive": True,
            "read_only": True,
            "orders_submitted": False,
        }


def _parse_levels(raw: object, *, side: str) -> tuple[BookLevel, ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"order book {side} must be a non-empty array")
    if len(raw) > MAX_BOOK_LEVELS:
        raise ValueError(f"order book {side} exceeds {MAX_BOOK_LEVELS} depth levels")
    levels: list[BookLevel] = []
    seen_prices: set[Decimal] = set()
    for index, row in enumerate(raw):
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError(f"order book {side}[{index}] must be [price, quantity]")
        level = BookLevel(
            price=_positive_decimal(row[0], f"{side}[{index}].price"),
            quantity=_positive_decimal(row[1], f"{side}[{index}].quantity"),
        )
        if level.price in seen_prices:
            raise ValueError(f"order book {side} contains duplicate price levels")
        seen_prices.add(level.price)
        levels.append(level)
    return tuple(
        sorted(levels, key=lambda level: level.price, reverse=(side == "bids"))
    )


@dataclass(frozen=True, slots=True)
class PublicTrade:
    symbol: str
    exchange_timestamp: datetime
    received_at: datetime
    side: str
    price: Decimal
    volume: Decimal
    source: str = "nobitex-public-websocket"
    update_offset: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", _valid_symbol(self.symbol))
        for field_name in ("exchange_timestamp", "received_at"):
            value = getattr(self, field_name)
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be a timezone-aware datetime")
            object.__setattr__(self, field_name, value.astimezone(timezone.utc))
        side = self.side.strip().lower() if isinstance(self.side, str) else ""
        if side not in {"buy", "sell"}:
            raise ValueError("trade side must be 'buy' or 'sell'")
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "price", _positive_decimal(self.price, "price"))
        object.__setattr__(self, "volume", _positive_decimal(self.volume, "volume"))
        if self.update_offset is not None and (
            type(self.update_offset) is not int or self.update_offset < 0
        ):
            raise ValueError("update_offset must be a non-negative integer or None")
        if self.exchange_timestamp > self.received_at + timedelta(seconds=5):
            raise ValueError("exchange timestamp is implausibly far in the future")

    @property
    def quote_notional(self) -> Decimal:
        return self.price * self.volume

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "event_type": "public_trade",
            "source": self.source,
            "symbol": self.symbol,
            "exchange_timestamp": self.exchange_timestamp.isoformat(),
            "received_at": self.received_at.isoformat(),
            "feed_lag_ms": max(
                0,
                int((self.received_at - self.exchange_timestamp).total_seconds() * 1000),
            ),
            "clock_skew_ms": int(
                (self.exchange_timestamp - self.received_at).total_seconds() * 1000
            ),
            "update_offset": self.update_offset,
            "reported_side": self.side,
            "price": str(self.price),
            "volume": str(self.volume),
            "quote_notional": str(self.quote_notional),
            "interpretation": (
                "Reported exchange trade side; not a standalone directional signal."
            ),
            "read_only": True,
            "orders_submitted": False,
        }


def _unpack_message(raw_message: str | bytes, expected_channel: str) -> tuple[dict[str, Any] | None, int | None]:
    if isinstance(raw_message, bytes):
        if len(raw_message) > MAX_MESSAGE_BYTES:
            raise PublicMarketStreamError("WebSocket message exceeds the configured size limit")
        try:
            text = raw_message.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PublicMarketStreamError("WebSocket message is not valid UTF-8") from exc
    elif isinstance(raw_message, str):
        if len(raw_message.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise PublicMarketStreamError("WebSocket message exceeds the configured size limit")
        text = raw_message
    else:
        raise PublicMarketStreamError("WebSocket message must be text or bytes")

    try:
        envelope = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PublicMarketStreamError("WebSocket message is not valid JSON") from exc
    if not isinstance(envelope, dict):
        raise PublicMarketStreamError("WebSocket JSON message must be an object")
    if envelope == {}:
        return None, None

    error = envelope.get("error")
    if error:
        raise PublicMarketStreamError(f"Public stream protocol error: {error}")

    push = envelope.get("push")
    if not isinstance(push, dict):
        # Connection and subscription acknowledgements are handled by the caller.
        return None, None
    channel = push.get("channel")
    if channel != expected_channel:
        return None, None
    publication = push.get("pub")
    if not isinstance(publication, dict):
        raise PublicMarketStreamError("WebSocket publication is malformed")
    data = publication.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise PublicMarketStreamError("Order-book publication data is not valid JSON") from exc
    if not isinstance(data, dict):
        raise PublicMarketStreamError("Order-book publication data must be an object")
    offset = publication.get("offset")
    if offset is not None:
        try:
            offset = int(offset)
        except (TypeError, ValueError) as exc:
            raise PublicMarketStreamError("Order-book publication offset must be an integer") from exc
        if offset < 0:
            raise PublicMarketStreamError("Order-book publication offset cannot be negative")
    return data, offset


def parse_public_orderbook_message(
    symbol: str,
    raw_message: str | bytes,
    *,
    received_at: datetime | None = None,
) -> OrderBookSnapshot | None:
    """Parse a raw Centrifugo message into a validated full order-book snapshot.

    Returns None for protocol acknowledgements, heartbeats and publications from other
    channels. Fossil/delta-compressed subscriptions are intentionally not used.
    """
    normalized_symbol = _valid_symbol(symbol)
    channel = f"public:orderbook-{normalized_symbol}"
    data, offset = _unpack_message(raw_message, channel)
    if data is None:
        return None
    if "bids" not in data or "asks" not in data:
        raise PublicMarketStreamError("Order-book publication is missing bids or asks")

    raw_timestamp = data.get("lastUpdate")
    if isinstance(raw_timestamp, bool) or not isinstance(raw_timestamp, (int, str)):
        raise PublicMarketStreamError("lastUpdate must be a Unix timestamp in milliseconds")
    try:
        timestamp_ms = int(raw_timestamp)
    except (TypeError, ValueError) as exc:
        raise PublicMarketStreamError("lastUpdate must be a Unix timestamp in milliseconds") from exc
    if timestamp_ms <= 0:
        raise PublicMarketStreamError("lastUpdate must be a positive Unix timestamp")
    try:
        exchange_timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise PublicMarketStreamError("lastUpdate is outside the supported timestamp range") from exc

    bids = _parse_levels(data["bids"], side="bids")
    asks = _parse_levels(data["asks"], side="asks")
    if bids[0].price >= asks[0].price:
        raise PublicMarketStreamError("crossed or locked order book snapshot received")

    last_trade_price = None
    raw_last_trade = data.get("lastTradePrice")
    if raw_last_trade not in (None, ""):
        last_trade_price = _positive_decimal(raw_last_trade, "lastTradePrice")
    captured_at = received_at or datetime.now(timezone.utc)
    return OrderBookSnapshot(
        symbol=normalized_symbol,
        source="nobitex-public-websocket",
        exchange_timestamp=exchange_timestamp,
        received_at=captured_at,
        bids=bids,
        asks=asks,
        last_trade_price=last_trade_price,
        update_offset=offset,
    )


def parse_public_trade_message(
    symbol: str,
    raw_message: str | bytes,
    *,
    received_at: datetime | None = None,
) -> PublicTrade | None:
    """Parse the public market trade channel; private account trade channels are never used."""
    normalized_symbol = _valid_symbol(symbol)
    channel = f"public:trades-{normalized_symbol}"
    data, offset = _unpack_message(raw_message, channel)
    if data is None:
        return None
    raw_timestamp = data.get("time")
    if isinstance(raw_timestamp, bool) or not isinstance(raw_timestamp, (int, str)):
        raise PublicMarketStreamError("trade time must be a Unix timestamp in milliseconds")
    try:
        timestamp_ms = int(raw_timestamp)
        exchange_timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        raise PublicMarketStreamError("trade time is not a valid Unix timestamp") from exc
    if timestamp_ms <= 0:
        raise PublicMarketStreamError("trade time must be a positive Unix timestamp")
    side = data.get("type")
    if side not in {"buy", "sell"}:
        raise PublicMarketStreamError("trade type must be 'buy' or 'sell'")
    try:
        trade = PublicTrade(
            symbol=normalized_symbol,
            exchange_timestamp=exchange_timestamp,
            received_at=received_at or datetime.now(timezone.utc),
            side=side,
            price=_positive_decimal(data.get("price"), "price"),
            volume=_positive_decimal(data.get("volume"), "volume"),
            update_offset=offset,
        )
    except ValueError as exc:
        raise PublicMarketStreamError(f"Invalid public trade publication: {exc}") from exc
    return trade


def fetch_initial_public_orderbook(
    symbol: str,
    *,
    timeout_seconds: float = 8.0,
) -> OrderBookSnapshot:
    """Fetch one bounded, unauthenticated REST snapshot to seed an online book."""
    normalized_symbol = _valid_symbol(symbol)
    if not 0.5 <= timeout_seconds <= 20:
        raise ValueError("timeout_seconds must be between 0.5 and 20 seconds")
    request = Request(
        f"https://apiv2.nobitex.ir/v3/orderbook/{normalized_symbol}",
        headers={"Accept": "application/json", "User-Agent": "ARASH-public-market-data/1.0"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(MAX_MESSAGE_BYTES + 1)
    except HTTPError as exc:
        raise PublicMarketStreamError(
            f"Public order-book bootstrap returned HTTP {exc.code}"
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise PublicMarketStreamError(
            f"Public order-book bootstrap could not complete: {exc}"
        ) from exc
    if len(raw) > MAX_MESSAGE_BYTES:
        raise PublicMarketStreamError("Public order-book bootstrap exceeded the size limit")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicMarketStreamError("Public order-book bootstrap was not valid UTF-8 JSON") from exc
    if not isinstance(data, dict) or data.get("status") != "ok":
        raise PublicMarketStreamError("Public order-book bootstrap returned an invalid response")
    raw_timestamp = data.get("lastUpdate")
    if isinstance(raw_timestamp, bool) or not isinstance(raw_timestamp, (int, str)):
        raise PublicMarketStreamError("REST lastUpdate must be a Unix timestamp in milliseconds")
    try:
        timestamp_ms = int(raw_timestamp)
        exchange_timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        raise PublicMarketStreamError("REST lastUpdate is not a valid Unix timestamp") from exc
    if timestamp_ms <= 0:
        raise PublicMarketStreamError("REST lastUpdate must be a positive Unix timestamp")
    try:
        bids = _parse_levels(data.get("bids"), side="bids")
        asks = _parse_levels(data.get("asks"), side="asks")
        if bids[0].price >= asks[0].price:
            raise ValueError("REST snapshot contains a crossed or locked order book")
        raw_last_trade = data.get("lastTradePrice")
        last_trade = (
            _positive_decimal(raw_last_trade, "lastTradePrice")
            if raw_last_trade not in (None, "")
            else None
        )
        return OrderBookSnapshot(
            symbol=normalized_symbol,
            source="nobitex-public-rest-snapshot",
            exchange_timestamp=exchange_timestamp,
            received_at=datetime.now(timezone.utc),
            bids=bids,
            asks=asks,
            last_trade_price=last_trade,
            update_offset=None,
        )
    except ValueError as exc:
        raise PublicMarketStreamError(f"Invalid REST order-book snapshot: {exc}") from exc


async def _deliver(
    callback: Callable[[Any], object],
    event: OrderBookSnapshot | PublicTrade,
) -> None:
    result = callback(event)
    if inspect.isawaitable(result):
        await result  # type: ignore[misc]


async def _wait_for_ack(
    websocket: Any,
    *,
    request_id: int,
    symbol: str,
    callback: Callable[[Any], object],
    stop_event: asyncio.Event | None,
    trade_callback: Callable[[Any], object] | None = None,
) -> None:
    async with asyncio.timeout(10):
        while stop_event is None or not stop_event.is_set():
            raw_message = await websocket.recv()
            try:
                envelope = json.loads(raw_message)
            except (json.JSONDecodeError, TypeError) as exc:
                raise PublicMarketStreamError("Invalid JSON during WebSocket handshake") from exc
            if envelope == {}:
                await websocket.send("{}")
                continue
            if not isinstance(envelope, dict):
                raise PublicMarketStreamError("Handshake response must be a JSON object")
            if envelope.get("error"):
                raise PublicMarketStreamError(f"WebSocket handshake error: {envelope['error']}")
            if envelope.get("id") == request_id:
                return
            snapshot = parse_public_orderbook_message(symbol, raw_message)
            if snapshot is not None:
                await _deliver(callback, snapshot)
                continue
            trade = parse_public_trade_message(symbol, raw_message)
            if trade is not None and trade_callback is not None:
                await _deliver(trade_callback, trade)
        return


async def stream_public_market_data(
    symbol: str,
    on_snapshot: Callable[[Any], object],
    *,
    on_trade: Callable[[Any], object] | None = None,
    stop_event: asyncio.Event | None = None,
    max_reconnects: int = 5,
) -> None:
    """Stream public order-book snapshots and public trade prints on one connection.

    The optional websockets dependency is loaded lazily. No private account channels or
    order endpoints are used.
    """
    normalized_symbol = _valid_symbol(symbol)
    if type(max_reconnects) is not int or not 0 <= max_reconnects <= 20:
        raise ValueError("max_reconnects must be an integer between 0 and 20")
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise RuntimeError(
            "Public WebSocket streaming requires the optional dependency; install ARASH with "
            "the marketstream extra."
        ) from exc

    channel = f"public:orderbook-{normalized_symbol}"
    trade_channel = f"public:trades-{normalized_symbol}"
    reconnects = 0
    last_snapshot_at: datetime | None = None
    while stop_event is None or not stop_event.is_set():
        try:
            async with connect(
                NOBITEX_WEBSOCKET_URL,
                open_timeout=10,
                close_timeout=5,
                ping_interval=20,
                ping_timeout=20,
                max_size=MAX_MESSAGE_BYTES,
            ) as websocket:
                await websocket.send(json.dumps({"id": 1, "connect": {}}))
                await _wait_for_ack(
                    websocket,
                    request_id=1,
                    symbol=normalized_symbol,
                    callback=on_snapshot,
                    trade_callback=on_trade,
                    stop_event=stop_event,
                )
                if stop_event is not None and stop_event.is_set():
                    return

                await websocket.send(
                    json.dumps({"id": 2, "subscribe": {"channel": channel}})
                )

                async def deliver_monotonic(snapshot: OrderBookSnapshot) -> None:
                    nonlocal last_snapshot_at
                    if last_snapshot_at is not None and snapshot.exchange_timestamp < last_snapshot_at:
                        return
                    last_snapshot_at = snapshot.exchange_timestamp
                    await _deliver(on_snapshot, snapshot)

                await _wait_for_ack(
                    websocket,
                    request_id=2,
                    symbol=normalized_symbol,
                    callback=deliver_monotonic,
                    trade_callback=on_trade,
                    stop_event=stop_event,
                )
                if stop_event is not None and stop_event.is_set():
                    return

                if on_trade is not None:
                    await websocket.send(
                        json.dumps({"id": 3, "subscribe": {"channel": trade_channel}})
                    )
                    await _wait_for_ack(
                        websocket,
                        request_id=3,
                        symbol=normalized_symbol,
                        callback=deliver_monotonic,
                        trade_callback=on_trade,
                        stop_event=stop_event,
                    )
                    if stop_event is not None and stop_event.is_set():
                        return

                initial_snapshot = await asyncio.to_thread(
                    fetch_initial_public_orderbook,
                    normalized_symbol,
                )
                await deliver_monotonic(initial_snapshot)
                if stop_event is not None and stop_event.is_set():
                    return

                while stop_event is None or not stop_event.is_set():
                    try:
                        raw_message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=1.0 if stop_event is not None else 35.0,
                        )
                    except TimeoutError:
                        if stop_event is not None and stop_event.is_set():
                            return
                        if stop_event is None:
                            raise PublicMarketStreamError(
                                "No WebSocket message arrived within 35 seconds; reconnecting"
                            )
                        continue
                    if raw_message == "{}":
                        await websocket.send("{}")
                        continue
                    snapshot = parse_public_orderbook_message(normalized_symbol, raw_message)
                    if snapshot is not None:
                        await deliver_monotonic(snapshot)
                        reconnects = 0
                        continue
                    trade = parse_public_trade_message(normalized_symbol, raw_message)
                    if trade is not None and on_trade is not None:
                        await _deliver(on_trade, trade)
                        reconnects = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if stop_event is not None and stop_event.is_set():
                return
            if reconnects >= max_reconnects:
                raise PublicMarketStreamError(
                    f"Public order-book stream stopped after {reconnects} reconnect attempts: {exc}"
                ) from exc
            delay = min(0.5 * (2 ** reconnects), 8.0)
            reconnects += 1
            await asyncio.sleep(delay)
