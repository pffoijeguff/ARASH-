"""Small, dependency-free domain models with explicit validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"


def require_aware_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def require_positive(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{field_name} must be a finite number greater than zero")


def require_non_negative(value: Decimal, field_name: str) -> None:
    if not value.is_finite() or value < 0:
        raise ValueError(f"{field_name} must be a finite number greater than or equal to zero")


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    interval: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        if not self.interval.strip():
            raise ValueError("interval cannot be empty")
        object.__setattr__(self, "timestamp", require_aware_utc(self.timestamp, "timestamp"))
        for name in ("open", "high", "low", "close"):
            require_positive(getattr(self, name), name)
        require_non_negative(self.volume, "volume")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be greater than or equal to open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be less than or equal to open, close, and high")


@dataclass(frozen=True, slots=True)
class ClosedPaperTrade:
    """A completed simulated position; this model cannot send an order anywhere."""

    trade_id: str
    symbol: str
    direction: Direction
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    entry_fee: Decimal
    exit_fee: Decimal
    opened_at: datetime
    closed_at: datetime

    def __post_init__(self) -> None:
        if not self.trade_id.strip():
            raise ValueError("trade_id cannot be empty")
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        object.__setattr__(self, "opened_at", require_aware_utc(self.opened_at, "opened_at"))
        object.__setattr__(self, "closed_at", require_aware_utc(self.closed_at, "closed_at"))
        if self.closed_at < self.opened_at:
            raise ValueError("closed_at cannot be earlier than opened_at")
        require_positive(self.quantity, "quantity")
        require_positive(self.entry_price, "entry_price")
        require_positive(self.exit_price, "exit_price")
        require_non_negative(self.entry_fee, "entry_fee")
        require_non_negative(self.exit_fee, "exit_fee")

    @property
    def gross_pnl(self) -> Decimal:
        if self.direction is Direction.LONG:
            return (self.exit_price - self.entry_price) * self.quantity
        return (self.entry_price - self.exit_price) * self.quantity

    @property
    def fees(self) -> Decimal:
        return self.entry_fee + self.exit_fee

    @property
    def net_pnl(self) -> Decimal:
        return self.gross_pnl - self.fees
