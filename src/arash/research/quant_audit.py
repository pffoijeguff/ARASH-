"""Quantitative sanity audits for backtest outcomes; not proof of strategy edge."""
from __future__ import annotations
from decimal import Decimal
from typing import Any
from arash.research.backtest import BacktestResult

ZERO=Decimal("0")
HUNDRED=Decimal("100")

def audit_backtest_result(result: BacktestResult) -> dict[str, Any]:
    trades=list(result.trades)
    pnl=[t.net_pnl for t in trades]
    wins=[v for v in pnl if v>ZERO]
    losses=[v for v in pnl if v<ZERO]
    total=sum(pnl,ZERO)
    gross_profit=sum(wins,ZERO)
    gross_loss=-sum(losses,ZERO)
    abs_total=sum((abs(v) for v in pnl),ZERO)
    concentration=max((abs(v) for v in pnl),default=ZERO)/abs_total if abs_total>ZERO else None
    streak=best_streak=loss_streak=worst_loss_streak=0
    for value in pnl:
        if value>ZERO:
            streak=streak+1 if streak>0 else 1
            best_streak=max(best_streak,streak)
            loss_streak=0
        elif value<ZERO:
            streak=loss_streak-1 if loss_streak<0 else -1
            worst_loss_streak=max(worst_loss_streak,abs(streak))
            loss_streak=streak
            if streak==-1: pass
            best_streak=max(best_streak,0)
        else:
            streak=0;loss_streak=0
    equity=[value for _,value in result.equity_curve]
    peaks=[];peak=equity[0] if equity else result.config.initial_cash
    for value in equity:
        peak=max(peak,value);peaks.append(peak)
    recovered_drawdown_bars=0
    longest_underwater=0
    current_underwater=0
    for value, high in zip(equity,peaks):
        if value < high:
            current_underwater+=1
            longest_underwater=max(longest_underwater,current_underwater)
        else:
            current_underwater=0
    if trades:
        avg_win=sum(wins,ZERO)/Decimal(len(wins)) if wins else None
        avg_loss=sum(losses,ZERO)/Decimal(len(losses)) if losses else None
        payoff=(avg_win/abs(avg_loss)) if avg_win is not None and avg_loss not in (None,ZERO) else None
    else:
        avg_win=avg_loss=payoff=None
    profit_factor=gross_profit/gross_loss if gross_loss>ZERO else (None if gross_profit==ZERO else Decimal("Infinity"))
    warnings=[]
    if len(trades)<30: warnings.append("Fewer than 30 closed trades: trade-level estimates are highly sample-sensitive.")
    if concentration is not None and concentration>Decimal("0.5"): warnings.append("One trade contributes more than half of absolute trade P&L; investigate result concentration.")
    if not losses and wins: warnings.append("No losing closed trades in this sample; this does not establish low risk.")
    if result.zero_volume_fills: warnings.append("One or more simulated fills used zero-volume candles; execution cost assumptions deserve review.")
    if result.high_participation_fills: warnings.append("One or more modeled fills exceeded the configured liquidity-warning threshold.")
    return {
      "schema_version":1,"report_type":"backtest_quantitative_sanity_audit",
      "strategy":result.strategy,"symbol":result.symbol,"interval":result.interval,
      "dataset_sha256":result.dataset_sha256,"status":"REVIEW_REQUIRED" if warnings else "NO_HEURISTIC_WARNING_DETECTED",
      "metrics":{
        "closed_trade_count":len(trades),"wins":len(wins),"losses":len(losses),"flats":len(trades)-len(wins)-len(losses),
        "gross_profit_from_winning_trades":str(gross_profit),"gross_loss_magnitude":str(gross_loss),
        "profit_factor":str(profit_factor) if profit_factor is not None else None,
        "average_winning_trade_net_pnl":str(avg_win) if avg_win is not None else None,
        "average_losing_trade_net_pnl":str(avg_loss) if avg_loss is not None else None,
        "payoff_ratio_mean_win_to_absolute_mean_loss":str(payoff) if payoff is not None else None,
        "largest_trade_share_of_absolute_trade_pnl":str(concentration) if concentration is not None else None,
        "longest_positive_trade_streak":best_streak,
        "longest_negative_trade_streak":worst_loss_streak,
        "longest_underwater_curve_run_bars":longest_underwater,
        "max_drawdown_pct":str(result.max_drawdown_pct),
        "return_pct":str(result.return_pct),
      },
      "warnings":warnings,
      "limitations":[
        "These descriptive heuristics are not formal tests of statistical significance.",
        "Profit factor may be undefined when the sample has no losses.",
        "Trade outcomes can be dependent, and the number of trades can be much smaller than the number of candles.",
        "No claim about future returns, investability, or profitability is made.",
      ],
      "trade_action":"NONE","execution_enabled":False,
    }
