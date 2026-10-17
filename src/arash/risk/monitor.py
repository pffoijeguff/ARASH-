"""Persisted-snapshot portfolio risk monitoring for ARASH paper accounts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from decimal import Decimal
from typing import Sequence

from arash.paper.broker import PaperAccountSnapshot
from arash.risk.engine import RiskPolicy

ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class PortfolioRiskAudit:
    account_id: str
    account_currency: str
    status: str
    equity: Decimal
    initial_cash: Decimal
    daily_start_equity: Decimal
    daily_pnl: Decimal
    daily_loss_fraction: Decimal
    daily_loss_limit_amount: Decimal
    peak_observed_equity: Decimal
    drawdown_fraction: Decimal
    current_exposure: Decimal
    exposure_fraction: Decimal
    block_reasons: tuple[str, ...]
    position_checks: tuple[dict[str, str | bool], ...]
    evaluated_at: datetime
    baseline_source: str
    risk_day_timezone: str
    risk_day_start_utc: datetime
    observation_count: int
    max_daily_loss_fraction: Decimal
    max_drawdown_fraction: Decimal
    max_portfolio_exposure_fraction: Decimal
    max_position_fraction: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "mode": "paper_portfolio_risk_audit",
            "live_trading": False,
            "account_id": self.account_id,
            "account_currency": self.account_currency,
            "monetary_values_currency": self.account_currency,
            "amount_contract": f"all monetary figures use {self.account_currency}; FX conversion is disabled",
            "status": self.status,
            "equity": str(self.equity),
            "initial_cash": str(self.initial_cash),
            "daily_start_equity": str(self.daily_start_equity),
            "daily_pnl": str(self.daily_pnl),
            "daily_loss_fraction": str(self.daily_loss_fraction),
            "daily_loss_limit_amount": str(self.daily_loss_limit_amount),
            "peak_observed_equity": str(self.peak_observed_equity),
            "drawdown_fraction": str(self.drawdown_fraction),
            "current_exposure": str(self.current_exposure),
            "exposure_fraction": str(self.exposure_fraction),
            "block_reasons": list(self.block_reasons),
            "position_checks": [dict(row) for row in self.position_checks],
            "evaluated_at": self.evaluated_at.isoformat(),
            "daily_baseline_source": self.baseline_source,
            "risk_day_timezone": self.risk_day_timezone,
            "risk_day_start_utc": self.risk_day_start_utc.isoformat(),
            "persisted_observations_used": self.observation_count,
            "limits": {
                "max_daily_loss_fraction": str(self.max_daily_loss_fraction),
                "max_drawdown_fraction": str(self.max_drawdown_fraction),
                "max_portfolio_exposure_fraction": str(self.max_portfolio_exposure_fraction),
                "max_position_fraction": str(self.max_position_fraction),
            },
            "caveats": [
                "Daily baselines and peaks are derived from persisted paper equity snapshots; missing intraday snapshots can hide earlier extremes.",
                "Marks are caller-supplied, not refreshed from a live market feed by this audit.",
                "Stop execution can gap and losses can exceed modeled thresholds.",
            ],
        }


def audit_portfolio_risk(
    snapshot: PaperAccountSnapshot,
    historical_snapshots: Sequence[dict[str, str]],
    *,
    policy: RiskPolicy | None = None,
    risk_day_timezone: str = "UTC",
) -> PortfolioRiskAudit:
    """Assess daily loss, peak-to-trough drawdown, exposure and per-position sizing.

    Historical snapshots are sorted defensively here; snapshot values remain exact
    Decimal strings in SQLite. The initial cash is a floor on observed peak equity.
    """
    policy = policy or RiskPolicy()
    if not isinstance(risk_day_timezone, str) or not risk_day_timezone.strip():
        raise ValueError("risk_day_timezone must be a non-empty IANA timezone name")
    try:
        day_zone = ZoneInfo(risk_day_timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown IANA risk-day timezone: {risk_day_timezone!r}") from exc
    now = snapshot.recorded_at.astimezone(timezone.utc)
    local_day = now.astimezone(day_zone).date()
    day_start_local = datetime.combine(local_day, time.min, tzinfo=day_zone)
    day_start = day_start_local.astimezone(timezone.utc)
    parsed: list[tuple[datetime, Decimal]] = []
    for row in historical_snapshots:
        try:
            timestamp = datetime.fromisoformat(row["recorded_at"])
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                continue
            timestamp = timestamp.astimezone(timezone.utc)
            if timestamp >= snapshot.recorded_at.astimezone(timezone.utc):
                continue
            value = Decimal(row["equity"])
            if value.is_finite() and value > ZERO:
                parsed.append((timestamp, value))
        except (KeyError, ValueError, ArithmeticError):
            continue
    parsed.sort(key=lambda item: item[0])
    earlier = [(ts, value) for ts, value in parsed if ts < now]
    current_equity = snapshot.equity
    if current_equity <= ZERO:
        peak = max([snapshot.initial_cash, *(v for _, v in earlier)], default=snapshot.initial_cash)
    else:
        peak = max([snapshot.initial_cash, current_equity, *(v for _, v in earlier)], default=snapshot.initial_cash)

    prior_day = [(ts, value) for ts, value in earlier if ts < day_start]
    current_day = [(ts, value) for ts, value in earlier if ts >= day_start]
    if prior_day:
        daily_start = prior_day[-1][1]
        baseline_source = f"latest_persisted_snapshot_before_{risk_day_timezone}_day"
    elif current_day:
        # If no prior-day observation exists, use the first available observation within
        # the current risk day rather than falling directly back to the original deposit.
        daily_start = current_day[0][1]
        baseline_source = f"first_persisted_snapshot_within_{risk_day_timezone}_day_fallback"
    else:
        daily_start = snapshot.initial_cash
        baseline_source = f"initial_cash_fallback_no_day_snapshot"
    if daily_start <= ZERO:
        daily_start = snapshot.initial_cash

    daily_pnl = current_equity - daily_start
    daily_loss_fraction = max(ZERO, -daily_pnl / daily_start) if daily_start > ZERO else ZERO
    daily_loss_limit = daily_start * policy.max_daily_loss_fraction
    drawdown = max(ZERO, (peak - current_equity) / peak) if peak > ZERO else ONE
    exposure = snapshot.position_value
    exposure_fraction = exposure / current_equity if current_equity > ZERO else ONE
    reasons: list[str] = []
    if daily_pnl <= -daily_loss_limit:
        reasons.append("daily_loss_limit_reached_or_exceeded")
    if drawdown >= policy.max_drawdown_fraction:
        reasons.append("maximum_drawdown_reached_or_exceeded")
    if exposure_fraction > policy.max_portfolio_exposure_fraction:
        reasons.append("portfolio_exposure_limit_exceeded")
    if current_equity <= ZERO:
        reasons.append("non_positive_equity")

    checks: list[dict[str, str | bool]] = []
    for position in snapshot.positions:
        market_value = Decimal(position["market_value"])
        fraction = market_value / current_equity if current_equity > ZERO else ONE
        allowed = fraction <= policy.max_position_fraction
        checks.append({
            "symbol": position["symbol"],
            "market_value": str(market_value),
            "equity_fraction": str(fraction),
            "allowed": allowed,
        })
        if not allowed:
            reasons.append(f"position_cap_exceeded:{position['symbol']}")

    return PortfolioRiskAudit(
        account_id=snapshot.account_id,
        account_currency=snapshot.account_currency,
        status="BLOCK" if reasons else "PASS",
        equity=current_equity,
        initial_cash=snapshot.initial_cash,
        daily_start_equity=daily_start,
        daily_pnl=daily_pnl,
        daily_loss_fraction=daily_loss_fraction,
        daily_loss_limit_amount=daily_loss_limit,
        peak_observed_equity=peak,
        drawdown_fraction=drawdown,
        current_exposure=exposure,
        exposure_fraction=exposure_fraction,
        block_reasons=tuple(dict.fromkeys(reasons)),
        position_checks=tuple(checks),
        evaluated_at=now,
        baseline_source=baseline_source,
        risk_day_timezone=risk_day_timezone,
        risk_day_start_utc=day_start,
        observation_count=len(parsed),
        max_daily_loss_fraction=policy.max_daily_loss_fraction,
        max_drawdown_fraction=policy.max_drawdown_fraction,
        max_portfolio_exposure_fraction=policy.max_portfolio_exposure_fraction,
        max_position_fraction=policy.max_position_fraction,
    )
