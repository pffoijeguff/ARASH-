"""Bounded descriptive features for the live public market-data stream.

Metrics are for market-quality observation and research only. They are not trading signals
or recommendations, and reported trade side is not assumed to reveal hidden aggressor intent.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from arash.data.streaming import OrderBookSnapshot, PublicTrade

ZERO = Decimal("0")
ONE = Decimal("1")


class StreamingMicrostructureFeatures:
    """Maintain a bounded rolling trade-flow window and enrich events with latest book state."""

    def __init__(
        self,
        *,
        window_seconds: int = 60,
        max_trade_events: int = 5000,
        depth_limit: int = 10,
    ) -> None:
        if type(window_seconds) is not int or not 5 <= window_seconds <= 3600:
            raise ValueError("window_seconds must be an integer between 5 and 3600")
        if type(max_trade_events) is not int or not 100 <= max_trade_events <= 100_000:
            raise ValueError("max_trade_events must be an integer between 100 and 100000")
        if type(depth_limit) is not int or not 1 <= depth_limit <= 500:
            raise ValueError("depth_limit must be an integer between 1 and 500")
        self.window_seconds = window_seconds
        self.max_trade_events = max_trade_events
        self.depth_limit = depth_limit
        self._trades: deque[PublicTrade] = deque()
        self._trade_timestamps: list[datetime] = []
        self._latest_book: OrderBookSnapshot | None = None
        self._event_watermark: datetime | None = None
        self._late_trade_events = 0
        self._pruned_trade_events = 0

    def observe(self, event: OrderBookSnapshot | PublicTrade) -> dict[str, Any]:
        """Return the raw event plus bounded, descriptive rolling market features."""
        if not isinstance(event, (OrderBookSnapshot, PublicTrade)):
            raise TypeError("event must be an OrderBookSnapshot or PublicTrade")

        if self._event_watermark is None or event.exchange_timestamp > self._event_watermark:
            self._event_watermark = event.exchange_timestamp
        watermark = self._event_watermark
        cutoff = watermark - timedelta(seconds=self.window_seconds)

        if isinstance(event, OrderBookSnapshot):
            self._latest_book = event
            payload = event.to_dict(depth_limit=self.depth_limit)
        else:
            payload = event.to_dict()
            if event.exchange_timestamp < cutoff:
                self._late_trade_events += 1
            else:
                timestamps = self._trade_timestamps
                insertion_index = bisect_right(timestamps, event.exchange_timestamp)
                if insertion_index < len(timestamps):
                    self._late_trade_events += 1
                    timestamps.insert(insertion_index, event.exchange_timestamp)
                    trades = list(self._trades)
                    trades.insert(insertion_index, event)
                    self._trades = deque(trades)
                else:
                    timestamps.append(event.exchange_timestamp)
                    self._trades.append(event)
                while len(self._trades) > self.max_trade_events:
                    self._trades.popleft()
                    self._trade_timestamps.pop(0)
                    self._pruned_trade_events += 1

        while self._trade_timestamps and self._trade_timestamps[0] < cutoff:
            self._trade_timestamps.pop(0)
            self._trades.popleft()
            self._pruned_trade_events += 1

        payload["microstructure_features"] = self._feature_snapshot(event)
        payload["interpretation_boundary"] = (
            "Descriptive live market observations only; no buy/sell decision is inferred."
        )
        return payload

    def _feature_snapshot(self, event: OrderBookSnapshot | PublicTrade) -> dict[str, Any]:
        buy_volume = sum((trade.volume for trade in self._trades if trade.side == "buy"), ZERO)
        sell_volume = sum((trade.volume for trade in self._trades if trade.side == "sell"), ZERO)
        buy_notional = sum(
            (trade.quote_notional for trade in self._trades if trade.side == "buy"), ZERO
        )
        sell_notional = sum(
            (trade.quote_notional for trade in self._trades if trade.side == "sell"), ZERO
        )
        total_volume = buy_volume + sell_volume
        total_notional = buy_notional + sell_notional
        quote_imbalance = (
            (buy_notional - sell_notional) / total_notional
            if total_notional > ZERO
            else ZERO
        )
        flow_vwap = total_notional / total_volume if total_volume > ZERO else None
        event_at = event.exchange_timestamp
        latest_trade = self._trades[-1] if self._trades else None
        book = self._latest_book
        book_data: dict[str, Any] | None = None
        if book is not None:
            book_data = {
                "book_timestamp": book.exchange_timestamp.isoformat(),
                "book_received_at": book.received_at.isoformat(),
                "book_age_ms": max(
                    0, int((event.received_at - book.received_at).total_seconds() * 1000)
                ),
                "best_bid": str(book.best_bid),
                "best_ask": str(book.best_ask),
                "midpoint": str(book.midpoint),
                "microprice": str(
                    book.to_dict(depth_limit=self.depth_limit)["microprice"]
                ),
                "spread_bps": str(book.spread_bps),
                "top_depth_imbalance": book.to_dict(
                    depth_limit=self.depth_limit
                )["top_depth_imbalance"],
            }
        return {
            "window_seconds": self.window_seconds,
            "window_start_utc": (event_at - timedelta(seconds=self.window_seconds)).isoformat(),
            "window_end_utc": event_at.isoformat(),
            "trade_count": len(self._trades),
            "reported_buy_volume_base": str(buy_volume),
            "reported_sell_volume_base": str(sell_volume),
            "reported_buy_notional_quote": str(buy_notional),
            "reported_sell_notional_quote": str(sell_notional),
            "net_reported_notional_quote": str(buy_notional - sell_notional),
            "reported_side_notional_imbalance": str(quote_imbalance),
            "rolling_trade_vwap": str(flow_vwap) if flow_vwap is not None else None,
            "latest_trade_timestamp": (
                latest_trade.exchange_timestamp.isoformat() if latest_trade else None
            ),
            "latest_trade_age_ms": (
                max(0, int((event_at - latest_trade.exchange_timestamp).total_seconds() * 1000))
                if latest_trade else None
            ),
            "late_trade_events_observed": self._late_trade_events,
            "trade_events_pruned_by_window_or_capacity": self._pruned_trade_events,
            "latest_orderbook": book_data,
            "data_quality_note": (
                "Trade-side imbalance uses the provider's reported buy/sell field; it is not a "
                "verified aggressor-side classification. Order-book depth is displayed liquidity."
            ),
            "signal_generated": False,
            "orders_submitted": False,
        }
