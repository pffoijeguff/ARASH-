"""Chronological, fixed-configuration holdout evaluation for offline baselines."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence
from arash.domain.models import Candle
from arash.research.backtest import BacktestConfig, BacktestResult, StrategyName, run_backtest

@dataclass(frozen=True, slots=True)
class ChronologicalEvaluation:
    split_index: int
    split_timestamp_utc: str
    in_sample: BacktestResult
    out_of_sample: BacktestResult
    joined_data_sha256: str
    interpretation: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "evaluation_method": "single_chronological_holdout_fixed_parameters",
            "split_index": self.split_index,
            "split_timestamp_utc": self.split_timestamp_utc,
            "in_sample": self.in_sample.to_dict(include_trades=False),
            "out_of_sample": self.out_of_sample.to_dict(include_trades=True),
            "source_dataset_sha256": self.joined_data_sha256,
            "interpretation": self.interpretation,
            "limitations": [
                "Parameters are fixed before this split; this function does not perform a search.",
                "The two windows are independently initialized simulations, so state is not carried across the split.",
                "One holdout window is not enough to establish generalization across market regimes.",
                "Returns and fills are modeled from OHLCV rather than observed live executions.",
            ],
            "trade_action": "NONE",
            "execution_enabled": False,
        }

def evaluate_chronological_holdout(
    candles: list[Candle], *, strategy: StrategyName,
    config: BacktestConfig | None = None, train_fraction: Decimal = Decimal("0.70"),
) -> ChronologicalEvaluation:
    from arash.data.validation import validate_candle_series
    import hashlib
    items = validate_candle_series(candles)
    if not isinstance(train_fraction, Decimal) or not train_fraction.is_finite() or not Decimal("0.5") <= train_fraction <= Decimal("0.9"):
        raise ValueError("train_fraction must be a Decimal between 0.5 and 0.9")
    cfg = config or BacktestConfig()
    split = int(Decimal(len(items)) * train_fraction)
    minimum = max(2, cfg.long_window + 2 if strategy == "sma-crossover" else 2)
    if split < minimum or len(items) - split < minimum:
        raise ValueError(f"both chronological windows must contain at least {minimum} candles")
    training, testing = items[:split], items[split:]
    in_sample = run_backtest(training, strategy=strategy, config=cfg)
    out_sample = run_backtest(testing, strategy=strategy, config=cfg)
    digest = hashlib.sha256((in_sample.dataset_sha256 + out_sample.dataset_sha256).encode()).hexdigest()
    return ChronologicalEvaluation(
        split_index=split, split_timestamp_utc=testing[0].timestamp.isoformat(),
        in_sample=in_sample, out_of_sample=out_sample, joined_data_sha256=digest,
        interpretation="Describes a fixed, predeclared baseline on a chronological holdout; it is not a trained-model validation or a profitability guarantee.",
    )
