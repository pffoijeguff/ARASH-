"""Realized-performance reports for completed paper-trading positions only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from arash.domain.models import ClosedPaperTrade

ReportPeriod = Literal["today", "week", "month"]
ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    period: ReportPeriod
    timezone_name: str
    start: datetime
    end_exclusive: datetime
    closed_trade_count: int
    winning_trade_count: int
    losing_trade_count: int
    flat_trade_count: int
    gross_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal
    win_rate_percent: Decimal | None
    average_net_pnl: Decimal | None


def period_bounds(period: ReportPeriod, now: datetime, timezone_name: str) -> tuple[datetime, datetime]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {timezone_name}") from exc

    local_now = now.astimezone(tz)
    local_date = local_now.date()
    if period == "today":
        start_date = local_date
        end_date = start_date + timedelta(days=1)
    elif period == "week":
        start_date = local_date - timedelta(days=local_date.weekday())
        end_date = start_date + timedelta(days=7)
    elif period == "month":
        start_date = local_date.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
    else:
        raise ValueError(f"Unsupported report period: {period}")

    start_local = datetime.combine(start_date, time.min, tzinfo=tz)
    end_local = datetime.combine(end_date, time.min, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def build_report(
    trades: list[ClosedPaperTrade],
    period: ReportPeriod,
    now: datetime | None = None,
    timezone_name: str = "Asia/Tehran",
) -> PerformanceReport:
    now = now or datetime.now(timezone.utc)
    start, end = period_bounds(period, now, timezone_name)
    selected = [trade for trade in trades if start <= trade.closed_at < end]

    gross = sum((trade.gross_pnl for trade in selected), ZERO)
    fees = sum((trade.fees for trade in selected), ZERO)
    net = sum((trade.net_pnl for trade in selected), ZERO)
    wins = sum(1 for trade in selected if trade.net_pnl > ZERO)
    losses = sum(1 for trade in selected if trade.net_pnl < ZERO)
    flats = sum(1 for trade in selected if trade.net_pnl == ZERO)
    count = len(selected)

    return PerformanceReport(
        period=period,
        timezone_name=timezone_name,
        start=start,
        end_exclusive=end,
        closed_trade_count=count,
        winning_trade_count=wins,
        losing_trade_count=losses,
        flat_trade_count=flats,
        gross_pnl=gross,
        fees=fees,
        net_pnl=net,
        win_rate_percent=(Decimal(wins) * Decimal("100") / Decimal(count)) if count else None,
        average_net_pnl=(net / Decimal(count)) if count else None,
    )
