"""Read-only, real-time public order-book streaming for ARASH.

This module subscribes only to public market-data channels. It accepts no exchange
credentials and contains no private-account or order-submission methods.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable

NOBITEX_WEBSOCKET_URL = "wss://wss.nobitex.ir/connection/websocket"
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
        _positive_decimal(self.price, "price")
        _positive_decimal(self.quantity, "quantity")


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
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
            object.__setattr__(self, field_name, value.astimezone(timezone.utc))
        if not self.bids or not self.asks:
            raise ValueError("order book must contain at least one bid and one ask")
        if self.best_bid >= self.best_ask:
            raise ValueError("crossed or locked order book snapshot is not admissible")
        if self.last_trade_price is not None:
            _positive_decimal(self.last_trade_price, "last_trade_price")
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "event_type": "public_orderbook_snapshot",
            "source": self.source,
            "symbol": self.symbol,
            "exchange_timestamp": self.exchange_timestamp.isoformat(),
            "received_at": self.received_at.isoformat(),
            "feed_lag_ms": max(
                0,
                int((self.received_at - self.exchange_timestamp).total_seconds() * 1000),
            ),
            "update_offset": self.update_offset,
            "best_bid": str(self.best_bid),
            "best_ask": str(self.best_ask),
            "midpoint": str(self.midpoint),
            "spread": str(self.spread),
            "spread_bps": str(self.spread_bps),
            "last_trade_price": (
                str(self.last_trade_price) if self.last_trade_price is not None else None
            ),
            "bid_depth_levels": len(self.bids),
            "ask_depth_levels": len(self.asks),
            "bids": [[str(level.price), str(level.quantity)] for level in self.bids],
            "asks": [[str(level.price), str(level.quantity)] for level in self.asks],
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
    if isinstance(raw_timestamp, bool):
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


async def _deliver(
    callback: Callable[[OrderBookSnapshot], object],
    snapshot: OrderBookSnapshot,
) -> None:
    result = callback(snapshot)
    if inspect.isawaitable(result):
        await result  # type: ignore[misc]


async def _wait_for_ack(
    websocket: Any,
    *,
    request_id: int,
    symbol: str,
    callback: Callable[[OrderBookSnapshot], object],
    stop_event: asyncio.Event | None,
) -> None:
    channel = f"public:orderbook-{symbol}"
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
        return


async def stream_public_orderbook(
    symbol: str,
    on_snapshot: Callable[[OrderBookSnapshot], object],
    *,
    stop_event: asyncio.Event | None = None,
    max_reconnects: int = 5,
) -> None:
    """Stream full public order-book snapshots, reconnecting under a bounded backoff.

    The optional websockets dependency is loaded lazily. Only the unauthenticated public
    market-data channel is used; no private channels or trading endpoints are exposed.
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
    reconnects = 0
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
                    stop_event=stop_event,
                )
                if stop_event is not None and stop_event.is_set():
                    return

                await websocket.send(
                    json.dumps({"id": 2, "subscribe": {"channel": channel}})
                )
                await _wait_for_ack(
                    websocket,
                    request_id=2,
                    symbol=normalized_symbol,
                    callback=on_snapshot,
                    stop_event=stop_event,
                )
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
                        await _deliver(on_snapshot, snapshot)
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
