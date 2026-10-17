"""Deterministic market-shock stress tests for persisted paper portfolios.

These scenarios are transparent counterfactuals, not forecasts, VaR estimates, or
probability-weighted risk measures. This module is offline-only and never places orders.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from arash.paper.broker import PaperAccountSnapshot
from arash.risk.engine import RiskPolicy
from arash.risk.monitor import audit_portfolio_risk

ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class PortfolioStressScenario:
    scenario_id: str
    shock_fraction: Decimal
    target_symbol: str | None
    interpretation: str

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.scenario_id.replace("-", "").replace("_", "").replace(":", "").isalnum():
            raise ValueError("scenario_id must be a non-empty simple identifier")
        if not isinstance(self.shock_fraction, Decimal) or not self.shock_fraction.is_finite():
            raise ValueError("shock_fraction must be a finite Decimal")
        if not Decimal("-0.95") <= self.shock_fraction <= ZERO:
            raise ValueError("shock_fraction must be between -0.95 and 0 inclusive")
        if self.target_symbol is not None and not self.target_symbol.strip():
            raise ValueError("target_symbol cannot be blank")
        if not self.interpretation.strip():
            raise ValueError("interpretation cannot be blank")


DEFAULT_PORTFOLIO_STRESS_SCENARIOS: tuple[PortfolioStressScenario, ...] = (
    PortfolioStressScenario(
        "parallel_down_5pct", Decimal("-0.05"), None,
        "All marked long positions fall 5%; cash is unchanged.",
    ),
    PortfolioStressScenario(
        "parallel_down_10pct", Decimal("-0.10"), None,
        "All marked long positions fall 10%; cash is unchanged.",
    ),
    PortfolioStressScenario(
        "parallel_down_20pct", Decimal("-0.20"), None,
        "All marked long positions fall 20%; cash is unchanged.",
    ),
)


def _scenario_symbol_component(symbol: str) -> str:
    """Produce a bounded report identifier while preserving the real symbol separately."""
    safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in symbol)
    if safe != symbol or len(safe) > 48:
        suffix = hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:8]
        safe = f"{safe[:48]}_{suffix}"
    return safe


def _finite_decimal_string(value: object, name: str) -> Decimal:
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:  # Decimal conversion can raise several narrow exception types.
        raise ValueError(f"{name} must be a decimal-compatible finite value") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be finite")
    return parsed


def build_portfolio_stress_report(
    snapshot: PaperAccountSnapshot,
    historical_snapshots: Sequence[dict[str, str]],
    *,
    policy: RiskPolicy | None = None,
    risk_day_timezone: str = "UTC",
    scenarios: Sequence[PortfolioStressScenario] = DEFAULT_PORTFOLIO_STRESS_SCENARIOS,
    single_asset_shock: Decimal = Decimal("-0.30"),
) -> dict[str, object]:
    """Create a risk audit plus systematic and single-name market-shock scenarios.

    Historical equity snapshots inform the daily baseline and observed peak, just as
    they do in :func:`audit_portfolio_risk`. Each stress scenario revalues the existing
    positions from their caller-provided marks; it does not model future orders or fees.
    """
    policy = policy or RiskPolicy()
    scenario_list = tuple(scenarios)
    if not scenario_list:
        raise ValueError("at least one portfolio stress scenario is required")
    scenario_ids = [scenario.scenario_id for scenario in scenario_list]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("scenario_id values must be unique")
    if not isinstance(single_asset_shock, Decimal) or not single_asset_shock.is_finite():
        raise ValueError("single_asset_shock must be a finite Decimal")
    if not Decimal("-0.95") <= single_asset_shock < ZERO:
        raise ValueError("single_asset_shock must be between -0.95 and below 0")
    if snapshot.cash < ZERO or snapshot.position_value < ZERO or snapshot.equity <= ZERO:
        raise ValueError("paper snapshot must have non-negative cash/exposure and positive equity")
    if snapshot.cash + snapshot.position_value != snapshot.equity:
        raise ValueError("snapshot equity must equal cash plus position value")

    positions: list[dict[str, object]] = []
    seen_symbols: set[str] = set()
    total_marked_value = ZERO
    for row in snapshot.positions:
        symbol = str(row.get("symbol", "")).strip()
        if not symbol or symbol in seen_symbols:
            raise ValueError("snapshot positions must have unique, non-empty symbols")
        seen_symbols.add(symbol)
        quantity = _finite_decimal_string(row.get("quantity"), f"{symbol}.quantity")
        mark = _finite_decimal_string(row.get("mark_price"), f"{symbol}.mark_price")
        market_value = _finite_decimal_string(row.get("market_value"), f"{symbol}.market_value")
        if quantity <= ZERO or mark <= ZERO or market_value < ZERO:
            raise ValueError(f"{symbol} quantity and mark must be positive and market value non-negative")
        row_quote_currency = row.get("quote_currency")
        row_value_currency = row.get("market_value_currency")
        if row_quote_currency is not None and row_quote_currency != snapshot.account_currency:
            raise ValueError(
                f"{symbol} quote currency {row_quote_currency} does not match account currency "
                f"{snapshot.account_currency}; FX conversion is disabled"
            )
        if row_value_currency is not None and row_value_currency != snapshot.account_currency:
            raise ValueError(
                f"{symbol} market value currency {row_value_currency} does not match account currency "
                f"{snapshot.account_currency}"
            )
        calculated_value = quantity * mark
        if calculated_value != market_value:
            raise ValueError(f"{symbol} market value does not match quantity multiplied by mark price")
        snapshot_mark = snapshot.marks.get(symbol)
        if snapshot_mark is None or _finite_decimal_string(snapshot_mark, f"{symbol}.snapshot_mark") != mark:
            raise ValueError(f"{symbol} position mark does not match snapshot mark manifest")
        positions.append({
            "symbol": symbol,
            "quantity": quantity,
            "mark_price": mark,
            "market_value": market_value,
        })
        total_marked_value += market_value
    if total_marked_value != snapshot.position_value:
        raise ValueError("sum of position market values does not match snapshot position_value")

    baseline = audit_portfolio_risk(snapshot, historical_snapshots, policy=policy, risk_day_timezone=risk_day_timezone)
    all_scenarios = list(scenario_list)
    if positions:
        all_scenarios.extend(
            PortfolioStressScenario(
                scenario_id=f"single_down_30pct:{_scenario_symbol_component(str(position['symbol']))}",
                shock_fraction=single_asset_shock,
                target_symbol=str(position["symbol"]),
                interpretation=f"Only {position['symbol']} falls {abs(single_asset_shock) * Decimal('100')}%; all other marks and cash stay unchanged.",
            )
            for position in positions
        )
    if len({scenario.scenario_id for scenario in all_scenarios}) != len(all_scenarios):
        raise ValueError("scenario identifiers collide between configured and generated scenarios")

    stress_results: list[dict[str, object]] = []
    for scenario in all_scenarios:
        scenario_positions: list[dict[str, str]] = []
        stressed_position_value = ZERO
        position_values: list[tuple[str, Decimal]] = []
        for position in positions:
            symbol = str(position["symbol"])
            current_value = position["market_value"]
            assert isinstance(current_value, Decimal)
            shock = scenario.shock_fraction if scenario.target_symbol is None or scenario.target_symbol == symbol else ZERO
            stressed_value = current_value * (ONE + shock)
            stressed_position_value += stressed_value
            position_values.append((symbol, stressed_value))
            scenario_positions.append({
                "symbol": symbol,
                "shock_fraction": str(shock),
                "current_market_value": str(current_value),
                "stressed_market_value": str(stressed_value),
                "modeled_pnl_delta": str(stressed_value - current_value),
            })

        stressed_equity = snapshot.cash + stressed_position_value
        pnl_delta = stressed_equity - snapshot.equity
        daily_pnl = stressed_equity - baseline.daily_start_equity
        daily_loss_fraction = max(ZERO, -daily_pnl / baseline.daily_start_equity) if baseline.daily_start_equity > ZERO else ZERO
        drawdown_fraction = max(ZERO, (baseline.peak_observed_equity - stressed_equity) / baseline.peak_observed_equity) if baseline.peak_observed_equity > ZERO else ONE
        exposure_fraction = stressed_position_value / stressed_equity if stressed_equity > ZERO else ONE
        reasons: list[str] = []
        if daily_pnl <= -(baseline.daily_start_equity * policy.max_daily_loss_fraction):
            reasons.append("daily_loss_limit_reached_or_exceeded_under_stress")
        if drawdown_fraction >= policy.max_drawdown_fraction:
            reasons.append("maximum_drawdown_reached_or_exceeded_under_stress")
        if exposure_fraction > policy.max_portfolio_exposure_fraction:
            reasons.append("portfolio_exposure_limit_exceeded_under_stress")
        if stressed_equity <= ZERO:
            reasons.append("non_positive_equity_under_stress")
        for symbol, market_value in position_values:
            position_fraction = market_value / stressed_equity if stressed_equity > ZERO else ONE
            if position_fraction > policy.max_position_fraction:
                reasons.append(f"position_cap_exceeded_under_stress:{symbol}")

        stress_results.append({
            "scenario_id": scenario.scenario_id,
            "interpretation": scenario.interpretation,
            "shock_fraction": str(scenario.shock_fraction),
            "target_symbol": scenario.target_symbol,
            "status": "BREACH" if reasons else "WITHIN_LIMITS",
            "current_equity": str(snapshot.equity),
            "stressed_equity": str(stressed_equity),
            "pnl_delta": str(pnl_delta),
            "loss_fraction_of_current_equity": str(max(ZERO, -pnl_delta / snapshot.equity)),
            "daily_pnl_after_stress": str(daily_pnl),
            "daily_loss_fraction_after_stress": str(daily_loss_fraction),
            "drawdown_fraction_from_observed_peak": str(drawdown_fraction),
            "stressed_position_value": str(stressed_position_value),
            "stressed_exposure_fraction": str(exposure_fraction),
            "breach_reasons": reasons,
            "positions": scenario_positions,
        })

    breached = [row for row in stress_results if row["status"] == "BREACH"]
    if baseline.status == "BLOCK":
        overall_status = "BASELINE_BLOCKED"
    elif breached:
        overall_status = "STRESS_BREACH"
    else:
        overall_status = "WITHIN_TESTED_LIMITS"

    payload: dict[str, object] = {
        "schema_version": 1,
        "report_type": "paper_portfolio_stress_audit",
        "mode": "offline_paper_risk_diagnostic",
        "live_orders_submitted": False,
        "execution_enabled": False,
        "account_id": snapshot.account_id,
        "account_currency": snapshot.account_currency,
        "monetary_values_currency": snapshot.account_currency,
        "amount_contract": f"all monetary figures use {snapshot.account_currency}; FX conversion is disabled",
        "evaluated_at_utc": snapshot.recorded_at.isoformat(),
        "risk_day_timezone": risk_day_timezone,
        "status": overall_status,
        "current_portfolio_audit": baseline.to_dict(),
        "scenario_count": len(stress_results),
        "breached_scenario_count": len(breached),
        "worst_scenario_id": min(stress_results, key=lambda row: _finite_decimal_string(row["stressed_equity"], "stressed_equity"))["scenario_id"],
        "scenarios": stress_results,
        "policy": {
            "max_daily_loss_fraction": str(policy.max_daily_loss_fraction),
            "max_drawdown_fraction": str(policy.max_drawdown_fraction),
            "max_portfolio_exposure_fraction": str(policy.max_portfolio_exposure_fraction),
            "max_position_fraction": str(policy.max_position_fraction),
        },
        "methodology": {
            "systematic_shocks": [str(scenario.shock_fraction) for scenario in scenario_list],
            "single_asset_shock_fraction": str(single_asset_shock),
            "cash_shock": "0; cash held constant",
            "position_revaluation": "caller-supplied mark and position quantity multiplied by (1 + shock)",
            "monetary_unit": snapshot.account_currency,
            "fx_conversion_enabled": False,
            "scenario_probabilities": None,
            "fees_funding_and_future_execution_costs_included": False,
        },
        "limitations": [
            "Shocks are transparent deterministic stress assumptions, not forecasts or probabilities.",
            "Correlation, liquidity gaps, liquidation costs, funding, and stop slippage are not modeled in this market-mark stress layer.",
            "Marks are caller supplied; their freshness and source cannot be independently verified here.",
            "Daily-loss baseline uses the configured IANA risk-day timezone; it is not automatically the exchange session calendar.",
            "Stress breaches are diagnostic and do not automatically trip or clear the account kill switch.",
            "An in-limit result covers only the tested scenarios and does not establish safety or profitability.",
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    payload["report_fingerprint_sha256"] = fingerprint
    return payload
