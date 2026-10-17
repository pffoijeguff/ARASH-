"""Bounded experiment-grid runner with explicit multiple-comparison disclosure."""
from __future__ import annotations
import hashlib, json
from dataclasses import replace
from decimal import Decimal
from itertools import product
from typing import Any, Iterable
from arash.domain.models import Candle
from arash.research.backtest import BacktestConfig, StrategyName, run_backtest

def run_experiment_grid(
    candles: list[Candle], *, strategies: Iterable[StrategyName] = ("buy-hold","sma-crossover"),
    short_windows: Iterable[int] = (5,), long_windows: Iterable[int] = (20,),
    position_fractions: Iterable[Decimal] = (Decimal("0.10"),),
    initial_config: BacktestConfig | None = None, max_candidates: int = 100,
) -> dict[str, Any]:
    cfg = initial_config or BacktestConfig()
    strategies = tuple(strategies); shorts=tuple(short_windows); longs=tuple(long_windows); fractions=tuple(position_fractions)
    if not strategies or not shorts or not longs or not fractions:
        raise ValueError("experiment candidate sets must be non-empty")
    if not isinstance(max_candidates,int) or isinstance(max_candidates,bool) or not 1 <= max_candidates <= 1000:
        raise ValueError("max_candidates must be an integer from 1 to 1000")
    candidate_count = len(strategies) * len(shorts) * len(longs) * len(fractions)
    if candidate_count > max_candidates:
        raise ValueError(f"candidate family has {candidate_count} entries, exceeding cap {max_candidates}")
    candidates=[]
    for strategy, short, long, fraction in product(strategies,shorts,longs,fractions):
        if strategy not in ("buy-hold","sma-crossover"):
            raise ValueError(f"unsupported strategy: {strategy}")
        config=replace(cfg, short_window=short, long_window=long, position_fraction=fraction)
        result=run_backtest(candles,strategy=strategy,config=config)
        row=result.to_dict(include_trades=False)
        metrics=row["metrics"]
        identity={"strategy":strategy,"short_window":short,"long_window":long,"position_fraction":str(fraction),"dataset_sha256":result.dataset_sha256}
        fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        candidates.append({"candidate_id":fingerprint,"candidate":identity,"metrics":metrics})
    # No ranking, best-candidate selection or deployment recommendation is emitted.
    return {
        "schema_version":1,"report_type":"research_experiment_grid","candidate_count":len(candidates),
        "declared_candidate_family":{"strategies":list(strategies),"short_windows":list(shorts),
        "long_windows":list(longs),"position_fractions":[str(v) for v in fractions]},
        "candidates":candidates,
        "multiple_comparison_warning":"All candidate outputs are returned without declaring a winner. Choosing a maximum after inspecting this grid introduces selection bias; assess on a separate chronological holdout and account for the full tested family.",
        "dataset_sha256":candidates[0]["candidate"]["dataset_sha256"] if candidates else None,
        "trade_action":"NONE","execution_enabled":False,
    }
