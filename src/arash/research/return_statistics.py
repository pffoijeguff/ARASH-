"""Circular moving-block bootstrap uncertainty summaries for return series.

This module quantifies sampling uncertainty under an explicitly chosen block length.
It does not prove predictive skill, estimate future profitability, or issue trade signals.
"""
from __future__ import annotations

import math
import random
from collections.abc import Sequence
from statistics import fmean, stdev
from typing import Any


def _parse_returns(values: Sequence[object]) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError("returns must be a numeric JSON array")
    if len(values) < 20:
        raise ValueError("at least 20 return observations are required for this diagnostic")
    if len(values) > 200_000:
        raise ValueError("returns cannot contain more than 200000 observations")
    parsed: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"returns[{index}] must be a numeric fraction")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"returns[{index}] must be finite")
        parsed.append(number)
    return tuple(parsed)


def _percentile(values: Sequence[float], probability: float) -> float:
    """Linear interpolation between adjacent order statistics."""
    if not values:
        raise ValueError("percentile requires a non-empty sample")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _sharpe_like(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    deviation = stdev(values)
    if deviation == 0.0:
        return None
    return fmean(values) / deviation


def bootstrap_return_statistics(
    returns: Sequence[object],
    *,
    iterations: int = 2000,
    block_length: int = 5,
    confidence_level: float = 0.95,
    seed: int = 0,
    periods_per_year: int | None = None,
) -> dict[str, Any]:
    """Estimate block-bootstrap percentile intervals for mean return and Sharpe-like ratio.

    Returns are decimal fractions per observation (0.01 means +1% per observation).
    Circular moving blocks preserve short-range ordering within sampled blocks. The analyst
    must choose block length and the annualization convention appropriate for the dataset.
    """
    observations = _parse_returns(returns)
    count = len(observations)
    if type(iterations) is not int or not 200 <= iterations <= 50_000:
        raise ValueError("iterations must be an integer between 200 and 50000")
    if type(block_length) is not int or not 1 <= block_length <= count:
        raise ValueError("block_length must be an integer between 1 and observation count")
    if not isinstance(confidence_level, (int, float)) or isinstance(confidence_level, bool):
        raise ValueError("confidence_level must be a number")
    confidence = float(confidence_level)
    if not math.isfinite(confidence) or not 0.50 <= confidence < 1.0:
        raise ValueError("confidence_level must be finite and between 0.50 inclusive and 1 exclusive")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if periods_per_year is not None and (
        type(periods_per_year) is not int or not 1 <= periods_per_year <= 1_000_000
    ):
        raise ValueError("periods_per_year must be a positive integer when supplied")
    if count * iterations > 10_000_000:
        raise ValueError(
            "requested bootstrap exceeds the 10-million-observation work budget; "
            "reduce iterations or provide a shorter return series"
        )

    observed_mean = fmean(observations)
    observed_volatility = stdev(observations)
    observed_sharpe = (
        observed_mean / observed_volatility if observed_volatility > 0.0 else None
    )
    annualization = math.sqrt(periods_per_year) if periods_per_year is not None else None
    random_source = random.Random(seed)
    bootstrap_means: list[float] = []
    bootstrap_sharpes: list[float] = []
    zero_variance_replicates = 0

    for _ in range(iterations):
        sample: list[float] = []
        while len(sample) < count:
            start = random_source.randrange(count)
            for offset in range(block_length):
                sample.append(observations[(start + offset) % count])
                if len(sample) == count:
                    break
        bootstrap_means.append(fmean(sample))
        score = _sharpe_like(sample)
        if score is None:
            zero_variance_replicates += 1
        else:
            bootstrap_sharpes.append(score)

    tail_probability = (1.0 - confidence) / 2.0
    mean_interval = [
        _percentile(bootstrap_means, tail_probability),
        _percentile(bootstrap_means, 1.0 - tail_probability),
    ]
    sharpe_interval = None
    annualized_sharpe_interval = None
    if len(bootstrap_sharpes) >= math.ceil(iterations * 0.80):
        sharpe_interval = [
            _percentile(bootstrap_sharpes, tail_probability),
            _percentile(bootstrap_sharpes, 1.0 - tail_probability),
        ]
        if annualization is not None:
            annualized_sharpe_interval = [
                sharpe_interval[0] * annualization,
                sharpe_interval[1] * annualization,
            ]

    warnings = [
        "Block-bootstrap intervals depend on stationarity and block-length assumptions.",
        "This diagnostic does not test whether a signal predicts future returns.",
        "Confidence intervals do not correct for strategy selection or multiple testing.",
        "Return inputs must already reflect the costs and execution assumptions being evaluated.",
    ]
    if count < 100:
        warnings.append("Fewer than 100 observations: uncertainty estimates may be unstable.")
    if zero_variance_replicates:
        warnings.append("Some bootstrap samples had zero variance; Sharpe intervals may be unavailable.")
    return {
        "schema_version": 1,
        "report_type": "circular_moving_block_bootstrap_return_statistics",
        "status": "COMPLETED_DIAGNOSTIC",
        "observation_count": count,
        "return_units": "decimal fraction per observation; 0.01 equals 1%",
        "observed": {
            "mean_return_per_period": observed_mean,
            "sample_volatility_per_period": observed_volatility,
            "sharpe_like_ratio_per_period": observed_sharpe,
            "periods_per_year": periods_per_year,
            "annualized_sharpe_like_ratio": (
                observed_sharpe * annualization
                if observed_sharpe is not None and annualization is not None
                else None
            ),
        },
        "bootstrap": {
            "method": "circular_moving_block_bootstrap",
            "iterations": iterations,
            "block_length_observations": block_length,
            "confidence_level": confidence,
            "mean_return_interval": mean_interval,
            "sharpe_like_interval": sharpe_interval,
            "annualized_sharpe_like_interval": annualized_sharpe_interval,
            "valid_sharpe_replicates": len(bootstrap_sharpes),
            "zero_variance_replicates": zero_variance_replicates,
            "random_seed": seed,
        },
        "warnings": warnings,
        "trade_action": "NONE",
        "execution_enabled": False,
    }
