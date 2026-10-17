"""Causality-aware candle-based execution simulator for paper research.

The model is deterministic and offline. A simulated fill at a bar's open may only use
volume from the latest fully completed prior bar. It does not read an order book,
submit orders, or mutate a paper-account ledger.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from arash.data.snapshots import INTERVAL_SECONDS
from arash.data.validation import validate_candle_series
from arash.domain.models import Candle

ZERO = Decimal("0")
ONE = Decimal("1")
EXECUTION_MODEL_VERSION = "CAUSAL_PRIOR_BAR_VOLUME_V2"


def _finite_decimal(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    return value


def _nonnegative(value: Decimal, name: str) -> Decimal:
    _finite_decimal(value, name)
    if value < ZERO:
        raise ValueError(f"{name} must be non-negative")
    return value


def _fraction(value: Decimal, name: str, *, allow_zero: bool = True) -> Decimal:
    _finite_decimal(value, name)
    invalid_lower_bound = value < ZERO if allow_zero else value <= ZERO
    if invalid_lower_bound:
        comparator = "between 0 and 1 inclusive" if allow_zero else "greater than 0 and at most 1"
        raise ValueError(f"{name} must be {comparator}")
    if value > ONE:
        raise ValueError(f"{name} must be at most 1")
    return value


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    fee_rate: Decimal = Decimal("0.001")
    slippage_rate: Decimal = Decimal("0.0005")
    spread_rate: Decimal = Decimal("0.001")
    market_impact_rate: Decimal = Decimal("0.002")
    max_participation_rate: Decimal = Decimal("0.10")
    max_bars: int = 20

    def __post_init__(self) -> None:
        for name in ("fee_rate", "slippage_rate", "spread_rate", "market_impact_rate"):
            _nonnegative(getattr(self, name), name)
            if getattr(self, name) >= ONE:
                raise ValueError(f"{name} must be less than 1")
        _fraction(self.max_participation_rate, "max_participation_rate", allow_zero=False)
        if not isinstance(self.max_bars, int) or isinstance(self.max_bars, bool) or not 1 <= self.max_bars <= 5000:
            raise ValueError("max_bars must be an integer between 1 and 5000")
        if self.slippage_rate + self.spread_rate / Decimal("2") + self.market_impact_rate >= ONE:
            raise ValueError("combined adverse execution rate must be less than 1")

    def to_dict(self) -> dict[str, object]:
        return {
            "fee_rate": str(self.fee_rate),
            "slippage_rate": str(self.slippage_rate),
            "spread_rate_full": str(self.spread_rate),
            "market_impact_rate_at_100pct_participation": str(self.market_impact_rate),
            "max_participation_rate_per_completed_prior_bar": str(self.max_participation_rate),
            "max_bars": self.max_bars,
        }


@dataclass(frozen=True, slots=True)
class SimulatedFill:
    candle_timestamp: datetime
    capacity_reference_timestamp: datetime
    side: str
    quantity: Decimal
    reference_price: Decimal
    fill_price: Decimal
    notional: Decimal
    fee: Decimal
    slippage_cost: Decimal
    spread_cost: Decimal
    market_impact_cost: Decimal
    candle_volume: Decimal
    capacity_reference_volume: Decimal
    participation_rate: Decimal

    def to_dict(self) -> dict[str, str]:
        return {
            "timestamp_utc": self.candle_timestamp.isoformat(),
            "capacity_reference_timestamp_utc": self.capacity_reference_timestamp.isoformat(),
            "side": self.side,
            "quantity": str(self.quantity),
            "reference_price": str(self.reference_price),
            "fill_price": str(self.fill_price),
            "notional": str(self.notional),
            "fee": str(self.fee),
            "slippage_cost": str(self.slippage_cost),
            "spread_cost": str(self.spread_cost),
            "market_impact_cost": str(self.market_impact_cost),
            "execution_bar_volume_post_event_diagnostic": str(self.candle_volume),
            "capacity_reference_volume": str(self.capacity_reference_volume),
            "participation_rate_of_completed_prior_bar": str(self.participation_rate),
        }


@dataclass(frozen=True, slots=True)
class ExecutionSimulationResult:
    simulation_id: str
    dataset_sha256: str
    symbol: str
    interval: str
    side: str
    order_type: str
    requested_quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    status: str
    eligible_bars_examined: int
    zero_volume_bars_skipped: int
    nonmarketable_limit_bars_skipped: int
    no_completed_capacity_reference_bars_skipped: int
    average_fill_price: Decimal | None
    total_notional: Decimal
    total_fees: Decimal
    total_slippage_cost: Decimal
    total_spread_cost: Decimal
    total_market_impact_cost: Decimal
    fills: tuple[SimulatedFill, ...]
    policy: ExecutionPolicy
    limitations: tuple[str, ...]

    @property
    def total_modeled_costs(self) -> Decimal:
        return self.total_fees + self.total_slippage_cost + self.total_spread_cost + self.total_market_impact_cost

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "execution_model_version": EXECUTION_MODEL_VERSION,
            "mode": "offline_execution_simulation_only",
            "live_orders_submitted": False,
            "simulation_id": self.simulation_id,
            "dataset_sha256": self.dataset_sha256,
            "symbol": self.symbol,
            "interval": self.interval,
            "side": self.side,
            "order_type": self.order_type,
            "requested_quantity": str(self.requested_quantity),
            "filled_quantity": str(self.filled_quantity),
            "remaining_quantity": str(self.remaining_quantity),
            "fill_fraction": str(self.filled_quantity / self.requested_quantity),
            "status": self.status,
            "eligible_bars_examined": self.eligible_bars_examined,
            "zero_volume_capacity_reference_bars_skipped": self.zero_volume_bars_skipped,
            "nonmarketable_limit_bars_skipped": self.nonmarketable_limit_bars_skipped,
            "no_completed_capacity_reference_bars_skipped": self.no_completed_capacity_reference_bars_skipped,
            "average_fill_price": str(self.average_fill_price) if self.average_fill_price is not None else None,
            "total_notional": str(self.total_notional),
            "total_fees": str(self.total_fees),
            "total_slippage_cost": str(self.total_slippage_cost),
            "total_spread_cost": str(self.total_spread_cost),
            "total_market_impact_cost": str(self.total_market_impact_cost),
            "total_modeled_costs": str(self.total_modeled_costs),
            "policy": self.policy.to_dict(),
            "fills": [fill.to_dict() for fill in self.fills],
            "limitations": list(self.limitations),
        }


def _dataset_digest(candles: list[Candle]) -> str:
    payload = [
        {
            "timestamp": c.timestamp.isoformat(), "open": str(c.open), "high": str(c.high),
            "low": str(c.low), "close": str(c.close), "volume": str(c.volume),
            "symbol": c.symbol, "interval": c.interval,
        }
        for c in candles
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def simulate_execution(
    candles: list[Candle],
    *,
    side: Literal["buy", "sell"],
    quantity: Decimal,
    submitted_at: datetime,
    order_type: Literal["market", "limit"] = "market",
    limit_price: Decimal | None = None,
    policy: ExecutionPolicy | None = None,
) -> ExecutionSimulationResult:
    """Simulate an order only on bars strictly later than submission time.

    Market orders use each eligible bar's open price, but capacity is capped from the
    latest fully closed prior bar's volume. The execution bar's eventual total volume
    is never used to decide its opening fill. An order with no prior closed volume
    observation receives no fill on that bar. This conservative model still cannot infer
    intrabar queue position or true executable depth from OHLCV.
    """
    items = validate_candle_series(candles)
    if side not in ("buy", "sell"):
        raise ValueError("side must be 'buy' or 'sell'")
    if order_type not in ("market", "limit"):
        raise ValueError("order_type must be 'market' or 'limit'")
    _finite_decimal(quantity, "quantity")
    if quantity <= ZERO:
        raise ValueError("quantity must be greater than zero")
    if submitted_at.tzinfo is None or submitted_at.utcoffset() is None:
        raise ValueError("submitted_at must be timezone-aware")
    submitted_utc = submitted_at.astimezone(timezone.utc)
    if order_type == "limit":
        if limit_price is None:
            raise ValueError("limit_price is required for limit orders")
        _finite_decimal(limit_price, "limit_price")
        if limit_price <= ZERO:
            raise ValueError("limit_price must be greater than zero")
    elif limit_price is not None:
        raise ValueError("limit_price must only be used with order_type='limit'")

    interval_seconds = INTERVAL_SECONDS.get(items[0].interval.lower())
    if interval_seconds is None:
        raise ValueError(f"execution simulation requires a known interval duration, got {items[0].interval!r}")
    from datetime import timedelta
    bar_duration = timedelta(seconds=interval_seconds)
    for previous, current in zip(items, items[1:]):
        if current.timestamp < previous.timestamp + bar_duration:
            raise ValueError("overlapping candles are invalid under BAR_OPEN_PLUS_INTERVAL_V1 semantics")

    policy = policy or ExecutionPolicy()
    eligible_pairs = [(index, candle) for index, candle in enumerate(items) if candle.timestamp > submitted_utc]
    eligible_pairs = eligible_pairs[:policy.max_bars]
    remaining = quantity
    fills: list[SimulatedFill] = []
    zero_volume_skips = 0
    limit_skips = 0
    missing_capacity_skips = 0
    bars_examined = 0

    for index, candle in eligible_pairs:
        bars_examined += 1
        if order_type == "limit":
            marketable = candle.low <= limit_price if side == "buy" else candle.high >= limit_price
            if not marketable:
                limit_skips += 1
                continue
        if index == 0:
            # No prior observation means no defensible capacity estimate at this bar open.
            missing_capacity_skips += 1
            continue
        reference_candle = items[index - 1]
        if reference_candle.timestamp + bar_duration > candle.timestamp:
            # Defensive invariant; overlap was rejected above, but keep the guard explicit.
            missing_capacity_skips += 1
            continue
        capacity_volume = reference_candle.volume
        if capacity_volume <= ZERO:
            zero_volume_skips += 1
            continue

        capacity = capacity_volume * policy.max_participation_rate
        fill_qty = min(remaining, capacity)
        if fill_qty <= ZERO:
            continue
        reference_price = candle.open if order_type == "market" else limit_price
        if order_type == "market":
            participation = fill_qty / capacity_volume
            impact_rate = policy.market_impact_rate * participation.sqrt()
            slippage_rate = policy.slippage_rate
            spread_rate = policy.spread_rate / Decimal("2")
            adverse_rate = slippage_rate + spread_rate + impact_rate
            fill_price = reference_price * (ONE + adverse_rate if side == "buy" else ONE - adverse_rate)
            slippage = reference_price * fill_qty * slippage_rate
            spread = reference_price * fill_qty * spread_rate
            impact = reference_price * fill_qty * impact_rate
        else:
            participation = fill_qty / capacity_volume
            # No price improvement assumed; fill never exceeds the limit price.
            fill_price = limit_price
            slippage = spread = impact = ZERO

        notional = fill_price * fill_qty
        fee = notional * policy.fee_rate
        fills.append(SimulatedFill(
            candle_timestamp=candle.timestamp,
            capacity_reference_timestamp=reference_candle.timestamp,
            side=side,
            quantity=fill_qty,
            reference_price=reference_price,
            fill_price=fill_price,
            notional=notional,
            fee=fee,
            slippage_cost=slippage,
            spread_cost=spread,
            market_impact_cost=impact,
            candle_volume=candle.volume,
            capacity_reference_volume=capacity_volume,
            participation_rate=participation,
        ))
        remaining -= fill_qty
        if remaining <= ZERO:
            remaining = ZERO
            break

    filled = quantity - remaining
    total_notional = sum((fill.notional for fill in fills), ZERO)
    average = total_notional / filled if filled > ZERO else None
    status = "FILLED" if remaining == ZERO else "PARTIALLY_FILLED" if filled > ZERO else "UNFILLED"
    dataset_sha = _dataset_digest(items)
    payload = {
        "execution_model_version": EXECUTION_MODEL_VERSION,
        "dataset_sha256": dataset_sha,
        "symbol": items[0].symbol,
        "interval": items[0].interval,
        "side": side,
        "order_type": order_type,
        "quantity": str(quantity),
        "submitted_at": submitted_utc.isoformat(),
        "limit_price": str(limit_price) if limit_price is not None else None,
        "policy": policy.to_dict(),
    }
    simulation_id = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ExecutionSimulationResult(
        simulation_id=simulation_id,
        dataset_sha256=dataset_sha,
        symbol=items[0].symbol,
        interval=items[0].interval,
        side=side,
        order_type=order_type,
        requested_quantity=quantity,
        filled_quantity=filled,
        remaining_quantity=remaining,
        status=status,
        eligible_bars_examined=bars_examined,
        zero_volume_bars_skipped=zero_volume_skips,
        nonmarketable_limit_bars_skipped=limit_skips,
        no_completed_capacity_reference_bars_skipped=missing_capacity_skips,
        average_fill_price=average,
        total_notional=total_notional,
        total_fees=sum((fill.fee for fill in fills), ZERO),
        total_slippage_cost=sum((fill.slippage_cost for fill in fills), ZERO),
        total_spread_cost=sum((fill.spread_cost for fill in fills), ZERO),
        total_market_impact_cost=sum((fill.market_impact_cost for fill in fills), ZERO),
        fills=tuple(fills),
        policy=policy,
        limitations=(
            "Uses OHLCV bars, not live order-book depth or venue matching-engine data",
            "Opening fill capacity uses only the latest fully completed prior bar volume; current-bar final volume is not used to determine fills",
            "If no completed prior bar is available, the bar is skipped rather than inventing capacity",
            "Queue position, order latency, adverse selection and partial fills within a bar are not directly observed",
            "Limit orders fill conservatively at the limit if the eligible bar touches it; a touch does not guarantee a real fill",
            "This report does not update a paper account ledger and never sends live orders",
        ),
    )
