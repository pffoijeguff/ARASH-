"""Combinatorial Symmetric Cross-Validation diagnostics for candidate backtests.

Inputs are aligned per-period net-return series for the same evaluation calendar.
This is a model-selection diagnostic, not a guarantee of future performance.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import combinations
from math import comb, isfinite, sqrt
from statistics import fmean
from typing import Any

try:
    from decimal import Decimal
except ImportError:  # pragma: no cover - Decimal is part of every supported Python.
    Decimal = None  # type: ignore[assignment,misc]


def _coerce_series(candidate: str, values: Sequence[object]) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError(f"returns for candidate {candidate!r} must be a numeric sequence")
    if len(values) == 0:
        raise ValueError(f"returns for candidate {candidate!r} cannot be empty")
    parsed: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError(
                f"return at index {index} for candidate {candidate!r} must be numeric"
            )
        number = float(value)
        if not isfinite(number):
            raise ValueError(
                f"return at index {index} for candidate {candidate!r} must be finite"
            )
        parsed.append(number)
    return tuple(parsed)


def _sharpe_like(values: Sequence[float]) -> float:
    """Non-annualized mean/sample-standard-deviation score with a defined zero-variance case."""
    mean = fmean(values)
    if len(values) < 2:
        raise ValueError("each validation partition must contain at least two observations")
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    deviation = sqrt(variance)
    if deviation == 0.0:
        if mean > 0.0:
            return float("inf")
        if mean < 0.0:
            return float("-inf")
        return 0.0
    return mean / deviation


def _average_ranks(values: Sequence[float]) -> list[float]:
    """Return ascending ranks (1 = worst, N = best), averaging exact ties."""
    ordered = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][0] == ordered[start][0]:
            end += 1
        average_rank = ((start + 1) + end) / 2.0
        for position in range(start, end):
            ranks[ordered[position][1]] = average_rank
        start = end
    return ranks


def estimate_probability_of_backtest_overfitting(
    candidate_returns: Mapping[str, Sequence[object]],
    *,
    blocks: int = 8,
    max_work_units: int = 20_000_000,
) -> dict[str, Any]:
    """Estimate PBO with CSCV over a matrix of aligned per-period candidate returns.

    The supplied returns should already reflect the transaction-cost assumptions under
    evaluation. Each key identifies a candidate; each sequence must contain the same
    time-aligned observations. Returns are fractions (for example, 0.01 means 1%),
    not percentages. The data are split into equal contiguous blocks. Every combination
    of half the blocks is in-sample and the complementary blocks are out-of-sample.

    A candidate is selected by the highest in-sample Sharpe-like score. PBO is the
    fraction of split selections whose selected candidate ranks below the median among
    all candidates on the complementary out-of-sample data. Exact in-sample ties share
    selection weight; exact out-of-sample ties receive average rank.
    """
    if not isinstance(candidate_returns, Mapping) or len(candidate_returns) < 2:
        raise ValueError("candidate_returns must contain at least two candidate series")
    if type(blocks) is not int or blocks < 4 or blocks > 14 or blocks % 2:
        raise ValueError("blocks must be an even integer between 4 and 14")
    if type(max_work_units) is not int or max_work_units < 1:
        raise ValueError("max_work_units must be a positive integer")

    names = sorted(candidate_returns)
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("candidate identifiers must be non-empty strings")
    series = {name: _coerce_series(name, candidate_returns[name]) for name in names}
    lengths = {len(values) for values in series.values()}
    if len(lengths) != 1:
        raise ValueError("all candidate return series must have the same number of observations")
    period_count = lengths.pop()
    if period_count < blocks * 2:
        raise ValueError(
            f"at least {blocks * 2} observations are required for {blocks} blocks"
        )
    if period_count % blocks:
        raise ValueError("observation count must divide evenly into the requested blocks")

    split_count = comb(blocks, blocks // 2)
    work_units = split_count * len(names) * period_count
    if work_units > max_work_units:
        raise ValueError(
            "requested CSCV analysis exceeds the bounded work budget; use fewer candidates, "
            "fewer observations or fewer blocks"
        )

    block_size = period_count // blocks
    block_indices = [
        tuple(range(block * block_size, (block + 1) * block_size))
        for block in range(blocks)
    ]
    split_loss_weight = 0.0
    selected_weight: dict[str, float] = {name: 0.0 for name in names}

    for in_sample_blocks in combinations(range(blocks), blocks // 2):
        in_sample_set = set(in_sample_blocks)
        out_sample_blocks = tuple(
            index for index in range(blocks) if index not in in_sample_set
        )
        in_indices = tuple(
            index for block in in_sample_blocks for index in block_indices[block]
        )
        out_indices = tuple(
            index for block in out_sample_blocks for index in block_indices[block]
        )

        in_scores = {
            name: _sharpe_like(tuple(series[name][index] for index in in_indices))
            for name in names
        }
        best_score = max(in_scores.values())
        winners = [name for name in names if in_scores[name] == best_score]
        per_winner_weight = 1.0 / len(winners)

        out_scores = [
            _sharpe_like(tuple(series[name][index] for index in out_indices))
            for name in names
        ]
        ranks = _average_ranks(out_scores)
        rank_by_name = {name: ranks[index] for index, name in enumerate(names)}

        for winner in winners:
            selected_weight[winner] += per_winner_weight
            omega = rank_by_name[winner] / (len(names) + 1.0)
            if omega < 0.5:
                split_loss_weight += per_winner_weight

    pbo_fraction = split_loss_weight / split_count
    frequencies = {
        name: round(selected_weight[name] / split_count, 8)
        for name in names
    }
    return {
        "schema_version": 1,
        "report_type": "combinatorial_probability_of_backtest_overfitting",
        "method": "Combinatorial Symmetric Cross-Validation (CSCV)",
        "status": "COMPLETED_DIAGNOSTIC",
        "candidate_count": len(names),
        "observation_count_per_candidate": period_count,
        "block_count": blocks,
        "observations_per_block": block_size,
        "split_count": split_count,
        "objective": "non-annualized mean divided by sample standard deviation",
        "pbo_fraction": round(pbo_fraction, 8),
        "pbo_percent": round(pbo_fraction * 100.0, 4),
        "below_median_selection_weight": round(split_loss_weight, 8),
        "in_sample_selection_frequency": frequencies,
        "interpretation": (
            "Fraction of CSCV selections where the in-sample-selected candidate ranked "
            "below the median candidate on the complementary out-of-sample blocks. "
            "Higher values indicate greater selection-instability in this candidate family."
        ),
        "warnings": [
            "PBO is a historical model-selection diagnostic, not a probability of future loss.",
            "CSCV does not replace a final chronological holdout that remains untouched during research.",
            "Candidate returns must be aligned by period, universe and cost assumptions.",
            "A score is only as credible as its data, return construction and execution-cost model.",
            "This implementation uses a Sharpe-like selection objective; it is not a Deflated Sharpe Ratio calculation.",
        ],
        "trade_action": "NONE",
        "execution_enabled": False,
    }
