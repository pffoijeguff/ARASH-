"""Descriptive, causal market intelligence from locally stored OHLCV candles.

The module emits research diagnostics, not recommendations, predictions, or order signals.
All computations are deterministic and use no future data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from statistics import median
from typing import Any

from arash.data.quality import audit_candles
from arash.data.validation import validate_candle_series
from arash.domain.models import Candle
from arash.research.backtest import dataset_fingerprint
from arash.research.regimes import analyze_market_regimes

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


def _pct(current: Decimal, reference: Decimal) -> Decimal:
    if reference == ZERO:
        raise ValueError("reference price cannot be zero")
    return (current / reference - ONE) * HUNDRED


def _sma(values: list[Decimal], period: int) -> Decimal | None:
    if len(values) < period:
        return None
    return sum(values[-period:], ZERO) / Decimal(period)


def _rsi(closes: list[Decimal], period: int) -> Decimal | None:
    if len(closes) <= period:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(len(closes) - period, len(closes))]
    gains = [max(item, ZERO) for item in changes]
    losses = [max(-item, ZERO) for item in changes]
    average_gain = sum(gains, ZERO) / Decimal(period)
    average_loss = sum(losses, ZERO) / Decimal(period)
    if average_loss == ZERO:
        return Decimal("50") if average_gain == ZERO else HUNDRED
    relative_strength = average_gain / average_loss
    return HUNDRED - (HUNDRED / (ONE + relative_strength))


def _atr_pct(candles: list[Candle], period: int) -> Decimal | None:
    if len(candles) <= period:
        return None
    true_ranges: list[Decimal] = []
    for index in range(1, len(candles)):
        candle = candles[index]
        prior_close = candles[index - 1].close
        true_ranges.append(max(
            candle.high - candle.low,
            abs(candle.high - prior_close),
            abs(candle.low - prior_close),
        ))
    atr = sum(true_ranges[-period:], ZERO) / Decimal(period)
    return atr / candles[-1].close * HUNDRED


def _return_volatility_pct(closes: list[Decimal], period: int) -> Decimal | None:
    if len(closes) <= period:
        return None
    returns = [closes[i] / closes[i - 1] - ONE for i in range(len(closes) - period, len(closes))]
    mean = sum(returns, ZERO) / Decimal(len(returns))
    variance = sum(((value - mean) ** 2 for value in returns), ZERO) / Decimal(len(returns))
    return variance.sqrt() * HUNDRED


def build_market_intelligence(
    source_candles: list[Candle],
    *,
    now: datetime | None = None,
    stale_after_intervals: int = 2,
    rsi_period: int = 14,
    atr_period: int = 14,
    volume_lookback: int = 20,
    regime_lookback: int = 20,
    trend_threshold_pct: Decimal = Decimal("2.0"),
    high_volatility_threshold_pct: Decimal = Decimal("1.0"),
) -> dict[str, Any]:
    """Build a deterministic report from validated candles with an explicit no-signal policy."""
    if type(rsi_period) is not int or not 2 <= rsi_period <= 200:
        raise ValueError("rsi_period must be an integer from 2 to 200")
    if type(atr_period) is not int or not 2 <= atr_period <= 200:
        raise ValueError("atr_period must be an integer from 2 to 200")
    if type(volume_lookback) is not int or not 2 <= volume_lookback <= 500:
        raise ValueError("volume_lookback must be an integer from 2 to 500")
    if type(regime_lookback) is not int or not 3 <= regime_lookback <= 500:
        raise ValueError("regime_lookback must be an integer from 3 to 500")
    if type(stale_after_intervals) is not int or stale_after_intervals < 1:
        raise ValueError("stale_after_intervals must be a positive integer")
    if not trend_threshold_pct.is_finite() or trend_threshold_pct <= ZERO:
        raise ValueError("trend_threshold_pct must be a finite positive decimal")
    if not high_volatility_threshold_pct.is_finite() or high_volatility_threshold_pct <= ZERO:
        raise ValueError("high_volatility_threshold_pct must be a finite positive decimal")
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current_time = current_time.astimezone(timezone.utc)
    candles = validate_candle_series(source_candles)
    quality = audit_candles(candles, now=current_time, stale_after_intervals=stale_after_intervals)
    closes = [item.close for item in candles]
    volumes = [item.volume for item in candles]
    last = candles[-1]

    returns: dict[str, str | None] = {}
    for horizon in (1, 5, 20):
        returns[f"{horizon}_bar_pct"] = (
            str(_pct(closes[-1], closes[-1 - horizon])) if len(closes) > horizon else None
        )

    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    close_vs_sma20 = _pct(last.close, sma20) if sma20 is not None else None
    close_vs_sma50 = _pct(last.close, sma50) if sma50 is not None else None
    if sma20 is None or sma50 is None:
        trend_alignment = "INSUFFICIENT_HISTORY"
    elif sma20 > sma50 and last.close > sma20:
        trend_alignment = "UPWARD_ALIGNMENT"
    elif sma20 < sma50 and last.close < sma20:
        trend_alignment = "DOWNWARD_ALIGNMENT"
    else:
        trend_alignment = "MIXED_ALIGNMENT"

    rsi_value = _rsi(closes, rsi_period)
    if rsi_value is None:
        rsi_state = "INSUFFICIENT_HISTORY"
    elif rsi_value >= Decimal("70"):
        rsi_state = "HIGH_MOMENTUM_ZONE"
    elif rsi_value <= Decimal("30"):
        rsi_state = "LOW_MOMENTUM_ZONE"
    else:
        rsi_state = "MID_RANGE"

    atr_pct = _atr_pct(candles, atr_period)
    return_volatility = _return_volatility_pct(closes, min(20, max(2, len(closes) - 1)))
    reference_volumes = volumes[-(volume_lookback + 1):-1]
    baseline_volume = median(reference_volumes) if len(reference_volumes) >= volume_lookback else None
    volume_ratio = (last.volume / baseline_volume) if baseline_volume is not None and baseline_volume > ZERO else None
    if volume_ratio is None:
        volume_state = "INSUFFICIENT_BASELINE"
    elif volume_ratio >= Decimal("2"):
        volume_state = "UNUSUALLY_HIGH_VS_TRAILING_MEDIAN"
    elif volume_ratio <= Decimal("0.5"):
        volume_state = "UNUSUALLY_LOW_VS_TRAILING_MEDIAN"
    else:
        volume_state = "WITHIN_0_5X_TO_2X_TRAILING_MEDIAN"

    range_high = max(candle.high for candle in candles[-min(20, len(candles)):])
    range_low = min(candle.low for candle in candles[-min(20, len(candles)):])
    range_width = range_high - range_low
    range_location = ((last.close - range_low) / range_width * HUNDRED) if range_width > ZERO else None

    regime = None
    if len(candles) > regime_lookback:
        regime_report = analyze_market_regimes(
            candles,
            lookback=regime_lookback,
            trend_threshold_pct=trend_threshold_pct,
            high_volatility_threshold_pct=high_volatility_threshold_pct,
        )
        latest_assignment = regime_report["assignments"][-1] if regime_report["assignments"] else None
        regime = {
            "algorithm": regime_report["algorithm"],
            "lookback_candles": regime_lookback,
            "latest_causally_assigned_regime": latest_assignment["regime"] if latest_assignment else None,
            "latest_assignment_timestamp_utc": latest_assignment["timestamp_utc"] if latest_assignment else None,
            "latest_assignment_uses_only_prior_closes": True,
            "classifiable_return_count": regime_report["classifiable_return_count"],
        }

    warnings = list(quality["warnings"])
    if sma50 is None:
        warnings.append("At least 50 candles are needed for the full 20/50-SMA alignment label.")
    if len(candles) <= max(rsi_period, atr_period, volume_lookback, regime_lookback):
        warnings.append("Some indicators lack their full configured lookback; null fields mean unavailable, not zero.")
    if baseline_volume == ZERO:
        warnings.append("Trailing median volume is zero; volume ratio is unavailable.")

    if quality["status"] == "FAIL" or quality["future_candle"]:
        status = "BLOCKED"
    elif len(candles) < 3:
        status = "INSUFFICIENT_HISTORY"
    elif quality["status"] == "WARN" or sma50 is None:
        status = "DEGRADED"
    else:
        status = "READY"

    config = {
        "rsi_period": rsi_period,
        "atr_period": atr_period,
        "volume_lookback": volume_lookback,
        "regime_lookback": regime_lookback,
        "stale_after_intervals": stale_after_intervals,
        "trend_threshold_pct": str(trend_threshold_pct),
        "high_volatility_threshold_pct": str(high_volatility_threshold_pct),
    }
    return {
        "schema_version": 1,
        "engine": "ARASH Market Intelligence Engine",
        "engine_version": "9.0.0",
        "generated_at_utc": current_time.isoformat(),
        "status": status,
        "mode": "descriptive_research_only",
        "market": {"symbol": last.symbol, "interval": last.interval},
        "dataset": {
            "candle_count": len(candles),
            "first_timestamp_utc": candles[0].timestamp.isoformat(),
            "last_timestamp_utc": last.timestamp.isoformat(),
            "sha256": dataset_fingerprint(candles),
        },
        "data_quality": quality,
        "price": {
            "last_close": str(last.close),
            "returns_pct": returns,
            "sma_20": str(sma20) if sma20 is not None else None,
            "sma_50": str(sma50) if sma50 is not None else None,
            "close_vs_sma_20_pct": str(close_vs_sma20) if close_vs_sma20 is not None else None,
            "close_vs_sma_50_pct": str(close_vs_sma50) if close_vs_sma50 is not None else None,
            "trend_alignment": trend_alignment,
            "trailing_20_bar_range_high": str(range_high),
            "trailing_20_bar_range_low": str(range_low),
            "close_position_in_trailing_range_pct": str(range_location) if range_location is not None else None,
        },
        "momentum": {
            "rsi_period": rsi_period,
            "rsi": str(rsi_value) if rsi_value is not None else None,
            "rsi_state": rsi_state,
        },
        "volatility": {
            "atr_period": atr_period,
            "atr_pct_of_last_close": str(atr_pct) if atr_pct is not None else None,
            "realized_close_to_close_volatility_pct_per_bar": str(return_volatility) if return_volatility is not None else None,
            "annualization": "none; raw per-bar descriptive metric",
        },
        "volume": {
            "last_volume": str(last.volume),
            "reference_window_excludes_latest_candle": True,
            "reference_median_volume": str(baseline_volume) if baseline_volume is not None else None,
            "latest_to_reference_median_ratio": str(volume_ratio) if volume_ratio is not None else None,
            "state": volume_state,
        },
        "market_regime": regime,
        "configuration": config,
        "warnings": warnings,
        "interpretation_guardrails": [
            "Indicators are descriptive summaries of historical OHLCV, not probabilities of future price moves.",
            "Trend, momentum, volatility and volume labels are heuristic and must not be read as buy/sell/hold advice.",
            "This report has no predictive-confidence score and does not authorize trade execution.",
            "Missing indicators are represented as null; insufficient data is never silently treated as zero.",
            "Regime assignment for the latest return uses only closes known before that return starts.",
        ],
        "trade_action": "NONE",
        "execution_enabled": False,
        "orders_submitted": False,
    }
