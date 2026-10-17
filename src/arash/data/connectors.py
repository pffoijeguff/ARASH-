"""Provider-neutral contracts for bounded OHLCV acquisition.

Connectors return validated candles and a digest of the normalized response. They have
no access to account credentials and no trading/order methods by design.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from arash.domain.models import Candle
from arash.integrations.nobitex.public_market import fetch_public_candles


@dataclass(frozen=True, slots=True)
class CandleRequest:
    symbol: str
    interval: str
    count: int = 100
    timeout_seconds: float = 8.0
    requested_to: datetime | None = None

    def validate(self) -> None:
        if not self.symbol.strip() or not self.symbol.isalnum():
            raise ValueError("symbol must contain only letters and digits")
        if not self.interval.strip():
            raise ValueError("interval is required")
        if not 1 <= self.count <= 500:
            raise ValueError("count must be between 1 and 500")
        if not 0.5 <= self.timeout_seconds <= 20:
            raise ValueError("timeout_seconds must be between 0.5 and 20")
        if self.requested_to is not None and (
            self.requested_to.tzinfo is None or self.requested_to.utcoffset() is None
        ):
            raise ValueError("requested_to must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CandleResponse:
    source: str
    symbol: str
    interval: str
    requested_to: datetime
    fetched_at: datetime
    candles: list[Candle]
    payload_sha256: str


class CandleConnector(Protocol):
    name: str

    def fetch(self, request: CandleRequest) -> CandleResponse: ...


class NobitexPublicConnector:
    """Read-only public candle connector for Nobitex UDF history."""

    name = "nobitex-public-udf"

    def fetch(self, request: CandleRequest) -> CandleResponse:
        request.validate()
        requested_to = (request.requested_to or datetime.now(timezone.utc)).astimezone(timezone.utc)
        candles = fetch_public_candles(
            request.symbol,
            request.interval,
            to_epoch=int(requested_to.timestamp()),
            countback=request.count,
            timeout_seconds=request.timeout_seconds,
        )
        fetched_at = datetime.now(timezone.utc)
        normalized = [
            {
                "symbol": item.symbol,
                "interval": item.interval,
                "timestamp": item.timestamp.astimezone(timezone.utc).isoformat(),
                "open": str(item.open),
                "high": str(item.high),
                "low": str(item.low),
                "close": str(item.close),
                "volume": str(item.volume),
            }
            for item in candles
        ]
        encoded = json.dumps(
            normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return CandleResponse(
            source=self.name,
            symbol=request.symbol.upper(),
            interval=request.interval.lower(),
            requested_to=requested_to,
            fetched_at=fetched_at,
            candles=candles,
            payload_sha256=hashlib.sha256(encoded).hexdigest(),
        )


class ConnectorRegistry:
    """Explicit registry of providers; unsupported providers fail closed."""

    def __init__(self) -> None:
        self._connectors: dict[str, CandleConnector] = {}

    def register(self, connector: CandleConnector) -> None:
        name = getattr(connector, "name", "")
        if not isinstance(name, str) or not name or name.strip() != name:
            raise ValueError("connector must declare a non-empty canonical name")
        if name in self._connectors:
            raise ValueError(f"connector {name!r} is already registered")
        self._connectors[name] = connector

    def resolve(self, name: str) -> CandleConnector:
        try:
            return self._connectors[name]
        except KeyError as exc:
            raise ValueError(f"unknown market-data connector {name!r}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._connectors))


def default_connector_registry() -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register(NobitexPublicConnector())
    return registry
