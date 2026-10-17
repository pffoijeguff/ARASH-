"""Deterministic execution-cost and liquidity sensitivity scenarios.

These scenarios are stress assumptions, not fitted market forecasts or trade signals.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Sequence

from arash.domain.models import Candle
from arash.paper.execution import ExecutionPolicy, simulate_execution

ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class ExecutionStressScenario:
    scenario_id: str
    cost_multiplier: Decimal
    participation_multiplier: Decimal
    interpretation: str

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.scenario_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError("scenario_id must be a non-empty simple identifier")
        if not self.cost_multiplier.is_finite() or self.cost_multiplier < ONE:
            raise ValueError("cost_multiplier must be finite and at least 1")
        if not self.participation_multiplier.is_finite() or not ZERO < self.participation_multiplier <= ONE:
            raise ValueError("participation_multiplier must be in (0, 1]")


DEFAULT_EXECUTION_STRESS_SCENARIOS: tuple[ExecutionStressScenario, ...] = (
    ExecutionStressScenario("base", Decimal("1"), Decimal("1"), "Configured baseline; not a best-case claim."),
    ExecutionStressScenario("adverse", Decimal("2"), Decimal("0.5"), "Costs doubled; allowed participation cut in half."),
    ExecutionStressScenario("severe", Decimal("3"), Decimal("0.25"), "Costs tripled; allowed participation cut to one quarter."),
)


def run_execution_stress_suite(
    candles: list[Candle],
    *,
    side: Literal["buy", "sell"],
    quantity: Decimal,
    submitted_at: datetime,
    order_type: Literal["market", "limit"] = "market",
    limit_price: Decimal | None = None,
    base_policy: ExecutionPolicy | None = None,
    scenarios: Sequence[ExecutionStressScenario] = DEFAULT_EXECUTION_STRESS_SCENARIOS,
) -> dict[str, object]:
    """Run the same order against a small, explicit set of execution assumptions."""
    policy = base_policy or ExecutionPolicy()
    scenario_list = tuple(scenarios)
    if not scenario_list:
        raise ValueError("at least one execution stress scenario is required")
    ids = [scenario.scenario_id for scenario in scenario_list]
    if len(set(ids)) != len(ids):
        raise ValueError("scenario_id values must be unique")

    records: list[dict[str, object]] = []
    for scenario in scenario_list:
        stressed_policy = ExecutionPolicy(
            fee_rate=policy.fee_rate * scenario.cost_multiplier,
            slippage_rate=policy.slippage_rate * scenario.cost_multiplier,
            spread_rate=policy.spread_rate * scenario.cost_multiplier,
            market_impact_rate=policy.market_impact_rate * scenario.cost_multiplier,
            max_participation_rate=policy.max_participation_rate * scenario.participation_multiplier,
            max_bars=policy.max_bars,
        )
        result = simulate_execution(
            candles,
            side=side,
            quantity=quantity,
            submitted_at=submitted_at,
            order_type=order_type,
            limit_price=limit_price,
            policy=stressed_policy,
        )
        result_payload = result.to_dict()
        records.append({
            "scenario_id": scenario.scenario_id,
            "interpretation": scenario.interpretation,
            "cost_multiplier": str(scenario.cost_multiplier),
            "participation_multiplier": str(scenario.participation_multiplier),
            "filled_quantity": str(result.filled_quantity),
            "remaining_quantity": str(result.remaining_quantity),
            "fill_fraction": str(result.filled_quantity / result.requested_quantity),
            "status": result.status,
            "total_modeled_costs": str(result.total_modeled_costs),
            "total_notional": str(result.total_notional),
            "execution_report": result_payload,
        })

    payload: dict[str, object] = {
        "schema_version": 1,
        "report_type": "execution_stress_sensitivity",
        "mode": "offline_sensitivity_only",
        "live_orders_submitted": False,
        "strategy_or_order_recommendation": None,
        "symbol": candles[0].symbol,
        "interval": candles[0].interval,
        "side": side,
        "order_type": order_type,
        "requested_quantity": str(quantity),
        "submitted_at_utc": submitted_at.astimezone(timezone.utc).isoformat(),
        "scenario_count": len(records),
        "scenarios": records,
        "interpretation_warning": (
            "Scenario outcomes are conditional on explicit assumptions. They are not probability-weighted forecasts, "
            "not evidence of strategy edge, and not a ranking for choosing a trade. Lower fill quantity can lower "
            "reported costs while increasing unfilled exposure; compare fill fraction and costs together."
        ),
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    payload["report_fingerprint_sha256"] = fingerprint
    return payload
