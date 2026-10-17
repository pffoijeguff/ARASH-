"""Deterministic, offline-only baseline backtesting.

Signals use observed closes and are executed at the following candle's open.
Fills are modeled estimates; no exchange connection or order placement exists here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from arash.data.validation import validate_candle_series
from arash.domain.models import Candle, ClosedPaperTrade, Direction, require_non_negative, require_positive

StrategyName = Literal["buy-hold", "sma-crossover"]
ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    initial_cash: Decimal = Decimal("10000")
    position_fraction: Decimal = Decimal("0.10")
    fee_rate: Decimal = Decimal("0.001")
    slippage_rate: Decimal = Decimal("0.0005")
    spread_rate: Decimal = ZERO
    market_impact_rate: Decimal = ZERO
    liquidity_warning_threshold: Decimal = Decimal("0.10")
    short_window: int = 5
    long_window: int = 20

    def __post_init__(self) -> None:
        require_positive(self.initial_cash, "initial_cash")
        require_positive(self.position_fraction, "position_fraction")
        if self.position_fraction > ONE:
            raise ValueError("position_fraction must be in (0, 1]; leverage is not supported")
        for name in ("fee_rate", "slippage_rate", "spread_rate", "market_impact_rate"):
            require_non_negative(getattr(self, name), name)
            if getattr(self, name) >= ONE:
                raise ValueError(f"{name} must be less than 1")
        if self.slippage_rate + self.spread_rate / Decimal("2") + self.market_impact_rate >= ONE:
            raise ValueError("combined maximum adverse execution rate must be less than 1")
        if not self.liquidity_warning_threshold.is_finite() or not ZERO < self.liquidity_warning_threshold <= ONE:
            raise ValueError("liquidity_warning_threshold must be in (0, 1]")
        if type(self.short_window) is not int or type(self.long_window) is not int:
            raise ValueError("SMA windows must be integers")
        if self.short_window < 1 or self.long_window < 2 or self.short_window >= self.long_window:
            raise ValueError("require 1 <= short_window < long_window and long_window >= 2")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    strategy: StrategyName
    symbol: str
    interval: str
    candle_count: int
    dataset_sha256: str
    start: str
    end: str
    config: BacktestConfig
    final_equity: Decimal
    net_pnl: Decimal
    return_pct: Decimal
    max_drawdown_pct: Decimal
    max_drawdown_duration_bars: int
    current_drawdown_duration_bars: int
    gross_pnl: Decimal
    fees: Decimal
    estimated_slippage_cost: Decimal
    estimated_spread_cost: Decimal
    estimated_market_impact_cost: Decimal
    high_participation_fills: int
    zero_volume_fills: int
    completed_trades: int
    winning_trades: int
    losing_trades: int
    flat_trades: int
    win_rate_pct: Decimal | None
    trades: tuple[ClosedPaperTrade, ...]
    equity_curve: tuple[tuple[str | None, Decimal], ...]

    def to_dict(self, *, include_trades: bool = True, include_equity_curve: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": 2,
            "mode": "offline_research_simulation",
            "strategy": self.strategy,
            "symbol": self.symbol,
            "interval": self.interval,
            "data": {
                "candle_count": self.candle_count, "sha256": self.dataset_sha256,
                "start_utc": self.start, "end_utc": self.end,
            },
            "parameters": {
                "initial_cash": str(self.config.initial_cash),
                "position_fraction": str(self.config.position_fraction),
                "fee_rate_per_side": str(self.config.fee_rate),
                "slippage_rate_per_side": str(self.config.slippage_rate),
                "spread_rate_full": str(self.config.spread_rate),
                "market_impact_rate_at_full_candle_volume": str(self.config.market_impact_rate),
                "liquidity_warning_threshold": str(self.config.liquidity_warning_threshold),
                "short_window": self.config.short_window, "long_window": self.config.long_window,
                "leverage": "not_supported",
                "execution": "signal_on_close_execute_next_bar_open; end_close_liquidation",
            },
            "metrics": {
                "final_equity": str(self.final_equity), "net_pnl": str(self.net_pnl),
                "return_pct": str(self.return_pct), "max_drawdown_pct": str(self.max_drawdown_pct),
                "max_drawdown_duration_bars": self.max_drawdown_duration_bars,
                "current_drawdown_duration_bars": self.current_drawdown_duration_bars,
                "gross_pnl": str(self.gross_pnl), "fees": str(self.fees),
                "estimated_slippage_cost": str(self.estimated_slippage_cost),
                "estimated_spread_cost": str(self.estimated_spread_cost),
                "estimated_market_impact_cost": str(self.estimated_market_impact_cost),
                "high_participation_fills": self.high_participation_fills,
                "zero_volume_fills": self.zero_volume_fills,
                "completed_trades": self.completed_trades, "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades, "flat_trades": self.flat_trades,
                "win_rate_pct": str(self.win_rate_pct) if self.win_rate_pct is not None else None,
            },
            "limitations": [
                "Offline simulation only; no exchange connection or order placement.",
                "Historical or synthetic backtests do not establish future performance.",
                "Costs are approximate candle-volume estimates rather than observed fills.",
                "Full fills are assumed; queue priority, latency and partial fills are not modeled.",
                "Open positions are liquidated at the final candle close under the configured cost assumptions.",
            ],
            "trade_action": "NONE",
            "execution_enabled": False,
            "orders_submitted": False,
        }
        if include_equity_curve:
            payload["equity_curve"] = [{"timestamp_utc": timestamp, "equity": str(value)} for timestamp, value in self.equity_curve]
        if include_trades:
            payload["trades"] = [
                {
                    "trade_id": trade.trade_id, "direction": trade.direction.value,
                    "quantity": str(trade.quantity), "entry_price": str(trade.entry_price),
                    "exit_price": str(trade.exit_price), "entry_fee": str(trade.entry_fee),
                    "exit_fee": str(trade.exit_fee), "gross_pnl": str(trade.gross_pnl),
                    "net_pnl": str(trade.net_pnl), "opened_at_utc": trade.opened_at.isoformat(),
                    "closed_at_utc": trade.closed_at.isoformat(),
                }
                for trade in self.trades
            ]
        return payload


@dataclass(slots=True)
class _OpenPosition:
    quantity: Decimal
    entry_price: Decimal
    entry_fee: Decimal
    opened_at: object


def _decimal_canonical(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("dataset prices and volumes must be finite")
    text = format(value.normalize(), "f")
    return "0" if text in ("", "-0") else text


def dataset_fingerprint(candles: list[Candle]) -> str:
    """Hash normalized candle content, independent of Decimal trailing zeroes."""
    lines = []
    for candle in candles:
        values = [
            candle.symbol, candle.interval, candle.timestamp.isoformat(),
            _decimal_canonical(candle.open), _decimal_canonical(candle.high),
            _decimal_canonical(candle.low), _decimal_canonical(candle.close),
            _decimal_canonical(candle.volume),
        ]
        lines.append("|".join(values))
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def _execution_components(raw_price: Decimal, quantity: Decimal, candle: Candle, config: BacktestConfig) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    if candle.volume <= ZERO:
        participation = ONE
    else:
        participation = min(ONE, quantity / candle.volume)
    impact = config.market_impact_rate * participation.sqrt()
    half_spread = config.spread_rate / Decimal("2")
    adverse = config.slippage_rate + half_spread + impact
    return adverse, config.slippage_rate, half_spread, impact


def _sma_cross_signals(closes: list[Decimal], short_window: int, long_window: int) -> list[int]:
    short_sma, long_sma = _rolling_sma(closes, short_window), _rolling_sma(closes, long_window)
    signals = [0] * len(closes)
    for index in range(1, len(closes)):
        ps, pl, cs, cl = short_sma[index - 1], long_sma[index - 1], short_sma[index], long_sma[index]
        if None in (ps, pl, cs, cl):
            continue
        if ps <= pl and cs > cl:
            signals[index] = 1
        elif ps >= pl and cs < cl:
            signals[index] = -1
    return signals


def _rolling_sma(values: list[Decimal], window: int) -> list[Decimal | None]:
    output: list[Decimal | None] = []
    running = ZERO
    for index, value in enumerate(values):
        running += value
        if index >= window:
            running -= values[index - window]
        output.append(running / Decimal(window) if index >= window - 1 else None)
    return output


def _liquidation_equity(cash: Decimal, position: _OpenPosition | None, candle: Candle, config: BacktestConfig) -> Decimal:
    if position is None:
        return cash
    adverse, _, _, _ = _execution_components(candle.close, position.quantity, candle, config)
    liquidation_price = candle.close * (ONE - adverse)
    liquidation_notional = position.quantity * liquidation_price
    return cash + liquidation_notional - liquidation_notional * config.fee_rate


def run_backtest(source_candles: list[Candle], *, strategy: StrategyName, config: BacktestConfig | None = None) -> BacktestResult:
    """Run the baseline buy-and-hold or SMA-crossover portfolio simulation."""
    cfg = config or BacktestConfig()
    if strategy not in ("buy-hold", "sma-crossover"):
        raise ValueError(f"unsupported research baseline: {strategy}")
    candles = validate_candle_series(source_candles)
    if len(candles) < 2:
        raise ValueError("at least two candles are required for a backtest")
    if strategy == "sma-crossover" and len(candles) < cfg.long_window + 2:
        raise ValueError(f"sma-crossover needs at least {cfg.long_window + 2} candles")
    cash = cfg.initial_cash
    position: _OpenPosition | None = None
    closed: list[ClosedPaperTrade] = []
    equity_curve: list[tuple[str | None, Decimal]] = [(None, cash)]
    slippage_total = spread_total = impact_total = ZERO
    high_participation = zero_volume = 0

    def record_costs(raw_price: Decimal, qty: Decimal, candle: Candle) -> Decimal:
        nonlocal slippage_total, spread_total, impact_total, high_participation, zero_volume
        adverse, slippage_rate, spread_rate, impact_rate = _execution_components(raw_price, qty, candle, cfg)
        if candle.volume <= ZERO:
            zero_volume += 1
        elif qty / candle.volume > cfg.liquidity_warning_threshold:
            high_participation += 1
        reference_notional = raw_price * qty
        slippage_total += reference_notional * slippage_rate
        spread_total += reference_notional * spread_rate
        impact_total += reference_notional * impact_rate
        return adverse

    def enter(candle: Candle) -> None:
        nonlocal cash, position
        if position is not None or cash <= ZERO:
            return
        raw = candle.open
        budget = cash * cfg.position_fraction
        qty = budget / (raw * (ONE + cfg.fee_rate))
        for _ in range(4):
            adverse, _, _, _ = _execution_components(raw, qty, candle, cfg)
            fill = raw * (ONE + adverse)
            qty = budget / (fill * (ONE + cfg.fee_rate))
        adverse = record_costs(raw, qty, candle)
        fill = raw * (ONE + adverse)
        notional = qty * fill
        fee = notional * cfg.fee_rate
        if notional + fee > cash:
            qty = cash / (fill * (ONE + cfg.fee_rate))
            adverse = record_costs(raw, qty, candle)
            fill = raw * (ONE + adverse)
            notional = qty * fill
            fee = notional * cfg.fee_rate
        cash -= notional + fee
        position = _OpenPosition(qty, fill, fee, candle.timestamp)

    def exit(candle: Candle, raw_price: Decimal) -> None:
        nonlocal cash, position
        if position is None:
            return
        current = position
        adverse = record_costs(raw_price, current.quantity, candle)
        fill = raw_price * (ONE - adverse)
        proceeds = current.quantity * fill
        fee = proceeds * cfg.fee_rate
        cash += proceeds - fee
        closed.append(ClosedPaperTrade(
            trade_id=f"{strategy}-{len(closed)+1:05d}", symbol=candles[0].symbol,
            direction=Direction.LONG, quantity=current.quantity, entry_price=current.entry_price,
            exit_price=fill, entry_fee=current.entry_fee, exit_fee=fee,
            opened_at=current.opened_at, closed_at=candle.timestamp,  # type: ignore[arg-type]
        ))
        position = None

    if strategy == "buy-hold":
        enter(candles[0])
        for candle in candles:
            equity_curve.append((candle.timestamp.isoformat(), _liquidation_equity(cash, position, candle, cfg)))
        exit(candles[-1], candles[-1].close)
        equity_curve[-1] = (candles[-1].timestamp.isoformat(), cash)
    else:
        closes = [candle.close for candle in candles]
        signals = _sma_cross_signals(closes, cfg.short_window, cfg.long_window)
        equity_curve.append((candles[0].timestamp.isoformat(), _liquidation_equity(cash, position, candles[0], cfg)))
        for execution_index in range(1, len(candles)):
            signal = signals[execution_index - 1]
            candle = candles[execution_index]
            if signal == 1 and position is None:
                enter(candle)
            elif signal == -1 and position is not None:
                exit(candle, candle.open)
            equity_curve.append((candle.timestamp.isoformat(), _liquidation_equity(cash, position, candle, cfg)))
        if position is not None:
            exit(candles[-1], candles[-1].close)
            equity_curve[-1] = (candles[-1].timestamp.isoformat(), cash)

    gross_pnl = sum((trade.gross_pnl for trade in closed), ZERO)
    fees = sum((trade.fees for trade in closed), ZERO)
    final_equity = cash
    net_pnl = final_equity - cfg.initial_cash
    ledger_pnl = sum((trade.net_pnl for trade in closed), ZERO)
    if abs(net_pnl - ledger_pnl) > max(Decimal("1e-18"), abs(cfg.initial_cash) * Decimal("1e-24")):
        raise ArithmeticError("backtest accounting failed to reconcile")

    peak = equity_curve[0][1]
    max_dd, duration, max_duration = ZERO, 0, 0
    for _, equity in equity_curve[1:]:
        if equity >= peak:
            peak, duration = equity, 0
        else:
            duration += 1
            max_duration = max(max_duration, duration)
        if peak > ZERO:
            max_dd = max(max_dd, (peak - equity) / peak * HUNDRED)
    wins = sum(1 for trade in closed if trade.net_pnl > ZERO)
    losses = sum(1 for trade in closed if trade.net_pnl < ZERO)
    flats = len(closed) - wins - losses
    win_rate = Decimal(wins) / Decimal(len(closed)) * HUNDRED if closed else None
    return BacktestResult(
        strategy=strategy, symbol=candles[0].symbol, interval=candles[0].interval,
        candle_count=len(candles), dataset_sha256=dataset_fingerprint(candles),
        start=candles[0].timestamp.isoformat(), end=candles[-1].timestamp.isoformat(),
        config=cfg, final_equity=final_equity, net_pnl=net_pnl,
        return_pct=net_pnl / cfg.initial_cash * HUNDRED, max_drawdown_pct=max_dd,
        max_drawdown_duration_bars=max_duration, current_drawdown_duration_bars=duration,
        gross_pnl=gross_pnl, fees=fees, estimated_slippage_cost=slippage_total,
        estimated_spread_cost=spread_total, estimated_market_impact_cost=impact_total,
        high_participation_fills=high_participation, zero_volume_fills=zero_volume,
        completed_trades=len(closed), winning_trades=wins, losing_trades=losses,
        flat_trades=flats, win_rate_pct=win_rate, trades=tuple(closed),
        equity_curve=tuple(equity_curve),
    )
