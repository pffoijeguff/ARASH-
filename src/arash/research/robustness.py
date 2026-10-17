"""Predeclared perturbation and subperiod robustness diagnostics for simple baselines."""
from __future__ import annotations
from dataclasses import replace
from decimal import Decimal
from typing import Any, Iterable
from arash.domain.models import Candle
from arash.research.backtest import BacktestConfig, StrategyName, run_backtest

ZERO=Decimal("0")

def run_parameter_perturbations(
    candles:list[Candle], *, strategy:StrategyName, base_config:BacktestConfig|None=None,
    fee_multipliers:Iterable[Decimal]=(Decimal("1"),Decimal("1.5"),Decimal("2")),
    slippage_multipliers:Iterable[Decimal]=(Decimal("1"),Decimal("2")),
    position_fractions:Iterable[Decimal]|None=None, max_scenarios:int=60
)->dict[str,Any]:
    cfg=base_config or BacktestConfig()
    fees=tuple(fee_multipliers);slips=tuple(slippage_multipliers)
    fractions=tuple(position_fractions) if position_fractions is not None else (cfg.position_fraction,)
    if not fees or not slips or not fractions: raise ValueError("perturbation grids must be non-empty")
    if any(not x.is_finite() or x<Decimal("1") for x in fees+slips): raise ValueError("cost multipliers must be finite and at least 1")
    if any(not x.is_finite() or not ZERO<x<=Decimal("1") for x in fractions): raise ValueError("position fractions must be in (0, 1]")
    count=len(fees)*len(slips)*len(fractions)
    if not 1<=max_scenarios<=500 or count>max_scenarios: raise ValueError(f"scenario count {count} exceeds configured limit {max_scenarios}")
    rows=[]
    for fm in fees:
        for sm in slips:
            for fraction in fractions:
                stressed=replace(cfg,fee_rate=cfg.fee_rate*fm,slippage_rate=cfg.slippage_rate*sm,position_fraction=fraction)
                result=run_backtest(candles,strategy=strategy,config=stressed)
                rows.append({
                    "fee_multiplier":str(fm),"slippage_multiplier":str(sm),"position_fraction":str(fraction),
                    "net_pnl":str(result.net_pnl),"return_pct":str(result.return_pct),
                    "max_drawdown_pct":str(result.max_drawdown_pct),"closed_trades":result.completed_trades,
                    "dataset_sha256":result.dataset_sha256,
                })
    returns=[Decimal(row["return_pct"]) for row in rows]
    return {
        "schema_version":1,"report_type":"parameter_perturbation_robustness",
        "strategy":strategy,"base_dataset_sha256":rows[0]["dataset_sha256"],"scenario_count":len(rows),
        "scenarios":rows,
        "summary":{
          "positive_return_scenario_count":sum(value>ZERO for value in returns),
          "negative_return_scenario_count":sum(value<ZERO for value in returns),
          "flat_return_scenario_count":sum(value==ZERO for value in returns),
          "worst_return_pct":str(min(returns)),"best_return_pct":str(max(returns)),
        },
        "interpretation":"Parameter perturbations reveal sensitivity to declared assumptions; they do not select an optimal scenario or estimate scenario probabilities.",
        "limitations":["The tested grid is user-chosen and may omit important costs or market conditions.",
                       "A robust result on one dataset can still fail out of sample.",
                       "This routine does not tune or recommend deployment parameters."],
        "trade_action":"NONE","execution_enabled":False,
    }

def run_chronological_subperiods(
    candles:list[Candle], *, strategy:StrategyName, config:BacktestConfig|None=None,
    segments:int=4,
)->dict[str,Any]:
    from arash.data.validation import validate_candle_series
    items=validate_candle_series(candles)
    if type(segments) is not int or not 2<=segments<=12: raise ValueError("segments must be an integer from 2 to 12")
    cfg=config or BacktestConfig()
    min_bars=max(2,cfg.long_window+2 if strategy=="sma-crossover" else 2)
    if len(items)<segments*min_bars: raise ValueError(f"each segment requires at least {min_bars} candles")
    base=len(items)//segments
    rows=[]
    for i in range(segments):
        start=i*base
        end=(i+1)*base if i<segments-1 else len(items)
        section=items[start:end]
        result=run_backtest(section,strategy=strategy,config=cfg)
        rows.append({"segment":i+1,"start_utc":section[0].timestamp.isoformat(),"end_utc":section[-1].timestamp.isoformat(),
                     "candle_count":len(section),"dataset_sha256":result.dataset_sha256,
                     "return_pct":str(result.return_pct),"max_drawdown_pct":str(result.max_drawdown_pct),
                     "closed_trades":result.completed_trades})
    return {"schema_version":1,"report_type":"chronological_subperiod_robustness","strategy":strategy,
            "segments":rows,"segment_count":len(rows),
            "limitations":["Each segment starts with fresh cash and no inherited position.",
                           "Segment returns are not a continuous-compounding portfolio result.",
                           "A small number of periods provides weak evidence across changing market conditions."]}
