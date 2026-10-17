"""Bounded retry policy for transient market-data connector failures."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 2.0

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        if not 0 <= self.base_delay_seconds <= 5:
            raise ValueError("base_delay_seconds must be between 0 and 5")
        if not 0 <= self.max_delay_seconds <= 10:
            raise ValueError("max_delay_seconds must be between 0 and 10")


def retry_call(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    is_retryable: Callable[[Exception], bool],
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[T, int]:
    """Run an operation under an explicit, capped retry budget; return value and attempts."""
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation(), attempt
        except Exception as exc:
            if attempt >= policy.max_attempts or not is_retryable(exc):
                raise
            delay = min(
                policy.base_delay_seconds * (2 ** (attempt - 1)),
                policy.max_delay_seconds,
            )
            if delay > 0:
                sleep(delay)
    raise RuntimeError("retry loop exited unexpectedly")


def is_retryable_public_market_error(error: Exception) -> bool:
    """Retry only transport failures and temporary HTTP responses, never bad payloads."""
    # Import here to keep generic retry utilities independent of a specific provider.
    from arash.integrations.nobitex.public_market import (
        PublicMarketConnectionError,
        PublicMarketHTTPError,
    )

    if isinstance(error, PublicMarketConnectionError):
        return True
    if isinstance(error, (TimeoutError, ConnectionError, OSError)):
        return True
    if isinstance(error, PublicMarketHTTPError):
        return error.status_code in (408, 425, 429) or 500 <= error.status_code <= 599
    return False
