"""Selection-bias warnings for repeated backtest searches.

This module reports how large a candidate family is and how concentrated its outcomes
are. It intentionally avoids assigning a false statistical guarantee to a best result.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any, Iterable

ZERO=Decimal("0")

def audit_candidate_family(
    candidate_returns_pct:Iterable[Decimal], *, declared_candidate_count:int|None=None,
    minimum_candidate_count:int=1,
)->dict[str,Any]:
    values=tuple(candidate_returns_pct)
    if not values: raise ValueError("candidate_returns_pct must contain at least one candidate")
    if any(not isinstance(value,Decimal) or not value.is_finite() for value in values):
        raise ValueError("candidate returns must be finite Decimal values")
    if type(minimum_candidate_count) is not int or minimum_candidate_count<1:
        raise ValueError("minimum_candidate_count must be a positive integer")
    actual=len(values)
    if declared_candidate_count is None: declared=actual
    else:
        if type(declared_candidate_count) is not int or declared_candidate_count<actual:
            raise ValueError("declared_candidate_count must be an integer at least as large as supplied outcomes")
        declared=declared_candidate_count
    ordered=sorted(values)
    wins=sum(v>ZERO for v in values)
    mean=sum(values,ZERO)/Decimal(actual)
    median_value=ordered[actual//2] if actual%2 else (ordered[actual//2-1]+ordered[actual//2])/Decimal(2)
    spread=ordered[-1]-ordered[0]
    warnings=[]
    if declared>1: warnings.append("Selecting the highest result from multiple candidates creates a winner's-curse risk.")
    if declared>10: warnings.append("Large candidate families substantially increase the opportunity to find an attractive result by chance.")
    if actual<minimum_candidate_count: warnings.append("Fewer candidate outcomes were supplied than the requested audit threshold.")
    if actual<30: warnings.append("Candidate-level summary is descriptive; this function does not estimate effective independent trials.")
    return {
      "schema_version":1,"report_type":"candidate_family_selection_bias_audit",
      "actual_candidate_results":actual,"declared_candidate_count":declared,
      "outcome_coverage_fraction":str(Decimal(actual)/Decimal(declared)),
      "summary":{"mean_return_pct":str(mean),"median_return_pct":str(median_value),
                 "minimum_return_pct":str(ordered[0]),"maximum_return_pct":str(ordered[-1]),
                 "best_minus_worst_pct_points":str(spread),"positive_candidate_fraction":str(Decimal(wins)/Decimal(actual))},
      "warnings":warnings,
      "not_estimated":["probability that the best candidate is a false discovery","effective number of independent candidates",
                       "deflated Sharpe ratio","probability of backtest overfitting"],
      "limitations":["Candidate returns alone do not reveal dependence between candidates.",
                     "The full searched candidate family must be reported, including failed and discarded trials.",
                     "A positive best backtest is not an estimate of future return."],
      "trade_action":"NONE","execution_enabled":False,
    }
