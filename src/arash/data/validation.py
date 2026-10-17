"""Fail-fast checks for time-series data before it reaches a strategy."""

from collections.abc import Iterable

from arash.domain.models import Candle


class DataValidationError(ValueError):
    """Raised when a candle series is internally inconsistent."""


def validate_candle_series(candles: Iterable[Candle]) -> list[Candle]:
    items = list(candles)
    if not items:
        raise DataValidationError("candle series cannot be empty")

    first = items[0]
    previous_timestamp = first.timestamp
    for index, candle in enumerate(items[1:], start=1):
        if candle.symbol != first.symbol:
            raise DataValidationError(f"mixed symbols at index {index}")
        if candle.interval != first.interval:
            raise DataValidationError(f"mixed intervals at index {index}")
        if candle.timestamp <= previous_timestamp:
            raise DataValidationError(
                f"timestamps must be strictly increasing; problem at index {index}"
            )
        previous_timestamp = candle.timestamp
    return items
