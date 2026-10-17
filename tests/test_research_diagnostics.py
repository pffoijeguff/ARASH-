"""Regression tests for ARASH's selection-bias and return-uncertainty diagnostics."""
from __future__ import annotations

import math

import pytest

from arash.research.pbo import estimate_probability_of_backtest_overfitting
from arash.research.return_statistics import bootstrap_return_statistics


def candidate_returns() -> dict[str, list[float]]:
    values = [
        0.003, -0.001, 0.002, -0.004, 0.005, -0.002, 0.001, -0.003,
        -0.002, 0.004, -0.001, 0.003, 0.002, -0.005, 0.006, -0.001,
    ]
    return {
        "trend": values,
        "reversion": [-value * 0.8 + 0.0002 for value in values],
        "noisy": [((index * 7) % 11 - 5) / 1000 for index in range(len(values))],
    }


def valid_returns() -> list[float]:
    return [((index * 7) % 19 - 9) / 10_000 for index in range(40)]


def test_pbo_report_is_bounded_and_non_executable() -> None:
    report = estimate_probability_of_backtest_overfitting(
        candidate_returns(), blocks=4
    )
    assert report["status"] == "COMPLETED_DIAGNOSTIC"
    assert report["candidate_count"] == 3
    assert report["observation_count_per_candidate"] == 16
    assert report["split_count"] == 6
    assert 0.0 <= report["pbo_fraction"] <= 1.0
    assert math.isclose(sum(report["in_sample_selection_frequency"].values()), 1.0)
    assert report["trade_action"] == "NONE"
    assert report["execution_enabled"] is False


def test_pbo_is_deterministic_for_identical_inputs() -> None:
    returns = candidate_returns()
    assert estimate_probability_of_backtest_overfitting(returns, blocks=4) == (
        estimate_probability_of_backtest_overfitting(returns, blocks=4)
    )


def test_pbo_rejects_unaligned_candidate_series() -> None:
    returns = candidate_returns()
    returns["short"] = [0.01] * 15
    with pytest.raises(ValueError, match="same number"):
        estimate_probability_of_backtest_overfitting(returns, blocks=4)


def test_pbo_rejects_non_finite_returns() -> None:
    returns = candidate_returns()
    returns["trend"][0] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        estimate_probability_of_backtest_overfitting(returns, blocks=4)


def test_pbo_enforces_work_budget() -> None:
    with pytest.raises(ValueError, match="work budget"):
        estimate_probability_of_backtest_overfitting(
            candidate_returns(), blocks=4, max_work_units=1
        )


def test_bootstrap_report_is_reproducible_and_bounded() -> None:
    values = valid_returns()
    first = bootstrap_return_statistics(
        values, iterations=250, block_length=4, seed=71, periods_per_year=252
    )
    second = bootstrap_return_statistics(
        values, iterations=250, block_length=4, seed=71, periods_per_year=252
    )
    assert first == second
    assert first["status"] == "COMPLETED_DIAGNOSTIC"
    assert first["observation_count"] == len(values)
    assert len(first["bootstrap"]["mean_return_interval"]) == 2
    assert first["bootstrap"]["annualized_sharpe_like_interval"] is not None
    assert first["trade_action"] == "NONE"
    assert first["execution_enabled"] is False


def test_bootstrap_rejects_too_few_returns() -> None:
    with pytest.raises(ValueError, match="at least 20"):
        bootstrap_return_statistics([0.01] * 19, iterations=200)


@pytest.mark.parametrize("bad_value", [True, float("nan"), float("inf")])
def test_bootstrap_rejects_invalid_return_values(bad_value: object) -> None:
    values: list[object] = valid_returns()
    values[3] = bad_value
    with pytest.raises(ValueError):
        bootstrap_return_statistics(values, iterations=200)


def test_bootstrap_enforces_work_budget() -> None:
    with pytest.raises(ValueError, match="work budget"):
        bootstrap_return_statistics(valid_returns() * 6, iterations=50_000)
