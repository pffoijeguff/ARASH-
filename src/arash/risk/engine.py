"""Conservative long-only position sizing and circuit-breaker checks.

All percentages are represented as Decimal fractions (0.01 means 1%). This module
is deliberately independent of an exchange or broker and never submits orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal("0")
ONE = Decimal("1")


def _finite(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    return value


def _positive(value: Decimal, name: str) -> Decimal:
    _finite(value, name)
    if value <= ZERO:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _fraction(value: Decimal, name: str) -> Decimal:
    _finite(value, name)
    if not ZERO < value <= ONE:
        raise ValueError(f"{name} must be greater than 0 and at most 1 (fraction, not percent)")
    return value


def _nonnegative(value: Decimal, name: str) -> Decimal:
    _finite(value, name)
    if value < ZERO:
        raise ValueError(f"{name} must be greater than or equal to zero")
    return value


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Hard limits for a spot-like long-only portfolio."""

    risk_per_trade: Decimal = Decimal("0.01")
    max_position_fraction: Decimal = Decimal("0.20")
    max_portfolio_exposure_fraction: Decimal = Decimal("0.60")
    max_daily_loss_fraction: Decimal = Decimal("0.03")
    max_drawdown_fraction: Decimal = Decimal("0.10")
    fee_rate: Decimal = Decimal("0.001")
    slippage_rate: Decimal = Decimal("0.0005")

    def __post_init__(self) -> None:
        _fraction(self.risk_per_trade, "risk_per_trade")
        _fraction(self.max_position_fraction, "max_position_fraction")
        _fraction(self.max_portfolio_exposure_fraction, "max_portfolio_exposure_fraction")
        _fraction(self.max_daily_loss_fraction, "max_daily_loss_fraction")
        _fraction(self.max_drawdown_fraction, "max_drawdown_fraction")
        _nonnegative(self.fee_rate, "fee_rate")
        _nonnegative(self.slippage_rate, "slippage_rate")
        if self.fee_rate >= ONE or self.slippage_rate >= ONE:
            raise ValueError("fee_rate and slippage_rate must be less than 1")


@dataclass(frozen=True, slots=True)
class RiskInputs:
    """A point-in-time assessment; callers are responsible for supplying current marks."""

    equity: Decimal
    cash: Decimal
    entry_price: Decimal
    stop_price: Decimal
    current_exposure: Decimal = ZERO
    current_position_exposure: Decimal = ZERO
    daily_pnl: Decimal = ZERO
    peak_equity: Decimal | None = None
    requested_quantity: Decimal | None = None

    def __post_init__(self) -> None:
        for name in ("equity", "entry_price", "stop_price"):
            _positive(getattr(self, name), name)
        _nonnegative(self.cash, "cash")
        _nonnegative(self.current_exposure, "current_exposure")
        _nonnegative(self.current_position_exposure, "current_position_exposure")
        if self.current_position_exposure > self.current_exposure:
            raise ValueError("current_position_exposure cannot exceed current_exposure")
        _finite(self.daily_pnl, "daily_pnl")
        if self.peak_equity is not None:
            _positive(self.peak_equity, "peak_equity")
        if self.requested_quantity is not None:
            _positive(self.requested_quantity, "requested_quantity")
        if self.stop_price >= self.entry_price:
            raise ValueError("for a long-only spot position, stop_price must be below entry_price")
        if self.cash > self.equity:
            raise ValueError("cash cannot exceed equity for this long-only spot model")
        if self.current_exposure > self.equity:
            raise ValueError("current_exposure cannot exceed equity")


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    status: str
    allowed: bool
    equity: Decimal
    current_position_exposure: Decimal
    risk_budget: Decimal
    risk_per_unit_estimate: Decimal
    quantity_by_trade_risk: Decimal
    quantity_by_position_cap: Decimal
    quantity_by_portfolio_cap: Decimal
    quantity_by_available_cash: Decimal
    recommended_quantity: Decimal
    estimated_position_notional: Decimal
    estimated_loss_at_stop: Decimal
    daily_loss_limit_amount: Decimal
    drawdown_from_peak_fraction: Decimal | None
    requested_quantity: Decimal | None
    requested_quantity_allowed: bool | None
    block_reasons: tuple[str, ...]
    assumptions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        def dec(value: Decimal | None) -> str | None:
            return str(value) if value is not None else None

        return {
            "mode": "risk_analysis_only_paper_research",
            "status": self.status,
            "allowed": self.allowed,
            "equity": dec(self.equity),
            "current_position_exposure": dec(self.current_position_exposure),
            "risk_budget": dec(self.risk_budget),
            "risk_per_unit_estimate": dec(self.risk_per_unit_estimate),
            "quantity_by_trade_risk": dec(self.quantity_by_trade_risk),
            "quantity_by_position_cap": dec(self.quantity_by_position_cap),
            "quantity_by_portfolio_cap": dec(self.quantity_by_portfolio_cap),
            "quantity_by_available_cash": dec(self.quantity_by_available_cash),
            "recommended_quantity": dec(self.recommended_quantity),
            "estimated_position_notional": dec(self.estimated_position_notional),
            "estimated_loss_at_stop": dec(self.estimated_loss_at_stop),
            "daily_loss_limit_amount": dec(self.daily_loss_limit_amount),
            "drawdown_from_peak_fraction": dec(self.drawdown_from_peak_fraction),
            "requested_quantity": dec(self.requested_quantity),
            "requested_quantity_allowed": self.requested_quantity_allowed,
            "block_reasons": list(self.block_reasons),
            "assumptions": list(self.assumptions),
        }


def assess_risk(inputs: RiskInputs, policy: RiskPolicy | None = None) -> RiskAssessment:
    """Compute a conservative BUY size and evaluate the supplied size against hard limits.

    Costs include a conservative entry and exit fee/slippage allowance in the stop-risk
    estimate. The available-cash cap uses entry slippage and entry fee only. No leverage
    or short selling is modeled.
    """
    policy = policy or RiskPolicy()
    equity = inputs.equity
    entry = inputs.entry_price
    stop = inputs.stop_price

    daily_limit = equity * policy.max_daily_loss_fraction
    drawdown_fraction: Decimal | None = None
    block_reasons: list[str] = []
    if inputs.daily_pnl <= -daily_limit:
        block_reasons.append("daily_loss_limit_reached_or_exceeded")
    if inputs.peak_equity is not None:
        peak = max(inputs.peak_equity, equity)
        drawdown_fraction = (peak - equity) / peak
        if drawdown_fraction >= policy.max_drawdown_fraction:
            block_reasons.append("maximum_drawdown_reached_or_exceeded")

    risk_budget = equity * policy.risk_per_trade
    risk_per_unit = (entry - stop) + entry * (policy.fee_rate + policy.slippage_rate) * Decimal("2")
    quantity_by_risk = risk_budget / risk_per_unit
    remaining_position_capacity = max(
        ZERO, equity * policy.max_position_fraction - inputs.current_position_exposure
    )
    quantity_by_position = remaining_position_capacity / entry
    remaining_exposure_capacity = max(
        ZERO, equity * policy.max_portfolio_exposure_fraction - inputs.current_exposure
    )
    quantity_by_portfolio = remaining_exposure_capacity / entry
    simulated_buy_price = entry * (ONE + policy.slippage_rate)
    cost_per_unit = simulated_buy_price * (ONE + policy.fee_rate)
    quantity_by_cash = inputs.cash / cost_per_unit
    recommended = min(
        quantity_by_risk,
        quantity_by_position,
        quantity_by_portfolio,
        quantity_by_cash,
    )
    if block_reasons:
        recommended = ZERO
    elif recommended <= ZERO:
        block_reasons.append("no_risk_capacity_for_new_position")
    requested_ok: bool | None = None
    if inputs.requested_quantity is not None:
        requested_ok = not block_reasons and inputs.requested_quantity <= recommended
        if not requested_ok and not block_reasons:
            block_reasons.append("requested_quantity_exceeds_recommended_size")
    allowed = not block_reasons
    estimated_notional = recommended * entry
    estimated_loss = recommended * risk_per_unit
    return RiskAssessment(
        status="PASS" if allowed else "BLOCK",
        allowed=allowed,
        equity=equity,
        current_position_exposure=inputs.current_position_exposure,
        risk_budget=risk_budget,
        risk_per_unit_estimate=risk_per_unit,
        quantity_by_trade_risk=quantity_by_risk,
        quantity_by_position_cap=quantity_by_position,
        quantity_by_portfolio_cap=quantity_by_portfolio,
        quantity_by_available_cash=quantity_by_cash,
        recommended_quantity=recommended,
        estimated_position_notional=estimated_notional,
        estimated_loss_at_stop=estimated_loss,
        daily_loss_limit_amount=daily_limit,
        drawdown_from_peak_fraction=drawdown_fraction,
        requested_quantity=inputs.requested_quantity,
        requested_quantity_allowed=requested_ok,
        block_reasons=tuple(block_reasons),
        assumptions=(
            "long-only spot sizing; leverage and short selling are excluded",
            "equity, cash, portfolio exposure, same-instrument exposure, daily P&L and peak equity must be current and use one currency",
            "stop execution can gap beyond the stop; actual losses may exceed this estimate",
            "fees and slippage are assumed inputs, not live measured costs",
            "this calculation does not place, modify, or cancel an order",
        ),
    )
