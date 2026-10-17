"""Read-only access to Nobitex public market statistics and OHLC candles.

No account credentials are accepted or used. Network calls are explicit and bounded.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from arash.domain.models import Candle
from arash.data.validation import validate_candle_series

DEFAULT_BASE_URL = "https://apiv2.nobitex.ir"
DEFAULT_OHLC_BASE_URL = "https://apiv2.nobitex.ir"
MAX_RESPONSE_BYTES = 2_000_000
MAX_CANDLES_PER_REQUEST = 500


class PublicMarketConnectionError(ValueError):
    """A transport-level error that is safe to retry with a bounded policy."""


class PublicMarketHTTPError(ValueError):
    """HTTP error from public market data; only selected status codes are retryable."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"Nobitex public endpoint returned HTTP {status_code}")

# Resolutions documented by Nobitex's public UDF history endpoint.
NOBITEX_RESOLUTIONS: dict[str, str] = {
    "1m": "1", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "3h": "180", "4h": "240", "6h": "360",
    "12h": "720", "1d": "D", "2d": "2D", "3d": "3D",
}


@dataclass(frozen=True, slots=True)
class PublicTicker:
    symbol: str
    latest: Decimal
    best_buy: Decimal | None
    best_sell: Decimal | None
    day_change_percent: Decimal | None
    source: str


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Nobitex returned a non-numeric ticker field") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("Nobitex returned an invalid negative or non-finite ticker field")
    return parsed


def parse_stats(
    payload: object,
    symbol: str,
    source: str = DEFAULT_BASE_URL,
    *,
    stats_key: str | None = None,
) -> PublicTicker:
    """Parse documented-style stats payloads while rejecting ambiguous/malformed data."""
    if not isinstance(payload, dict):
        raise ValueError("Nobitex response must be a JSON object")
    if payload.get("status") == "failed":
        raise ValueError("Nobitex reported a failed public market-data request")
    stats = payload.get("stats", payload)
    if not isinstance(stats, dict):
        raise ValueError("Nobitex response has no valid stats object")
    row = None
    for candidate in (stats_key, symbol, symbol.upper(), symbol.lower()):
        if candidate and isinstance(stats.get(candidate), dict):
            row = stats[candidate]
            break
    if not isinstance(row, dict):
        if any(key in stats for key in ("latest", "lastTradePrice", "bestBuy")):
            row = stats
        else:
            raise ValueError(f"Ticker {symbol} was not present in the Nobitex response")
    latest = _optional_decimal(row.get("latest", row.get("lastTradePrice")))
    if latest is None or latest <= 0:
        raise ValueError("Nobitex response does not contain a valid positive latest price")
    change = None
    raw_change = row.get("dayChange", row.get("dayChangePercent"))
    if raw_change not in (None, ""):
        try:
            change = Decimal(str(raw_change))
        except InvalidOperation as exc:
            raise ValueError("Nobitex returned an invalid day-change field") from exc
        if not change.is_finite():
            raise ValueError("Nobitex returned a non-finite day-change field")
    return PublicTicker(
        symbol=symbol.upper(), latest=latest,
        best_buy=_optional_decimal(row.get("bestBuy", row.get("best_buy"))),
        best_sell=_optional_decimal(row.get("bestSell", row.get("best_sell"))),
        day_change_percent=change, source=source,
    )


def _bounded_get_json(url: str, timeout_seconds: float) -> object:
    if not 0.5 <= timeout_seconds <= 20:
        raise ValueError("timeout_seconds must be between 0.5 and 20 seconds")
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "ARASH-Research/0.9.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise ValueError(f"Nobitex public endpoint returned HTTP {status}")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise PublicMarketHTTPError(exc.code) from exc
    except URLError as exc:
        raise PublicMarketConnectionError(
            f"Could not reach Nobitex public market-data endpoint: {exc.reason}"
        ) from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Nobitex response exceeded the 2 MB safety limit")
    try:
        return json.loads(raw.decode("utf-8"), parse_float=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Nobitex returned invalid JSON") from exc


def fetch_public_ticker(
    base_currency: str, quote_currency: str = "rls", *,
    base_url: str = DEFAULT_BASE_URL, timeout_seconds: float = 8.0,
) -> PublicTicker:
    """Fetch a public ticker. No private endpoints, API keys, or order methods are used."""
    base, quote = base_currency.strip().lower(), quote_currency.strip().lower()
    if not base.isalnum() or not quote.isalnum():
        raise ValueError("currency codes must contain only letters and digits")
    normalized_base = base_url.rstrip("/")
    url = f"{normalized_base}/market/stats?{urlencode({'srcCurrency': base, 'dstCurrency': quote})}"
    payload = _bounded_get_json(url, timeout_seconds)
    # Nobitex stats uses keys like `btc-rls`, while the market symbol in its candle
    # API is `BTCIRT`. Keep those two naming conventions distinct and explicit.
    market_quote = "IRT" if quote == "rls" else quote.upper()
    market_symbol = f"{base.upper()}{market_quote}"
    return parse_stats(
        payload, market_symbol, source=normalized_base, stats_key=f"{base}-{quote}"
    )


def parse_candle_history(
    payload: object, symbol: str, interval: str,
) -> list[Candle]:
    """Parse the documented Nobitex TradingView-UDF OHLCV response into validated candles."""
    if not isinstance(payload, dict):
        raise ValueError("Nobitex OHLC response must be a JSON object")
    status = payload.get("s")
    if status == "no_data":
        return []
    if status != "ok":
        message = payload.get("errmsg", "unknown UDF response status")
        raise ValueError(f"Nobitex OHLC endpoint reported an error: {message}")
    columns = {key: payload.get(key) for key in ("t", "o", "h", "l", "c", "v")}
    if any(not isinstance(values, list) for values in columns.values()):
        raise ValueError("Nobitex OHLC response must contain list fields t/o/h/l/c/v")
    sizes = {len(values) for values in columns.values() if isinstance(values, list)}
    if len(sizes) != 1:
        raise ValueError("Nobitex OHLC arrays have inconsistent lengths")
    count = sizes.pop() if sizes else 0
    if count == 0:
        return []
    if count > MAX_CANDLES_PER_REQUEST:
        raise ValueError(f"Nobitex OHLC response exceeded {MAX_CANDLES_PER_REQUEST} candles")

    result: list[Candle] = []
    for index in range(count):
        raw_time = columns["t"][index]
        if isinstance(raw_time, bool):
            raise ValueError(f"Invalid candle timestamp at index {index}")
        try:
            epoch = int(raw_time)
            if str(raw_time).strip() not in (str(epoch), f"{epoch}.0"):
                raise ValueError
            timestamp = datetime.fromtimestamp(epoch, tz=timezone.utc)
            prices = [Decimal(str(columns[key][index])) for key in ("o", "h", "l", "c", "v")]
        except (ValueError, TypeError, OverflowError, OSError, InvalidOperation) as exc:
            raise ValueError(f"Invalid OHLCV value at index {index}") from exc
        try:
            result.append(Candle(
                symbol=symbol.upper(), interval=interval,
                timestamp=timestamp, open=prices[0], high=prices[1], low=prices[2],
                close=prices[3], volume=prices[4],
            ))
        except ValueError as exc:
            raise ValueError(f"Invalid candle at index {index}: {exc}") from exc
    try:
        return validate_candle_series(result)
    except ValueError as exc:
        raise ValueError(f"Nobitex OHLC series failed validation: {exc}") from exc


def fetch_public_candles(
    symbol: str,
    interval: str,
    *,
    to_epoch: int,
    countback: int = 100,
    from_epoch: int | None = None,
    base_url: str = DEFAULT_OHLC_BASE_URL,
    timeout_seconds: float = 8.0,
    include_incomplete: bool = False,
) -> list[Candle]:
    """Fetch up to 500 public OHLCV candles from Nobitex's documented UDF endpoint.

    By default, candles whose scheduled close is after the requested `to` time are omitted;
    this avoids treating a still-forming bar as finalized research data.
    """
    normalized_symbol = symbol.strip().upper()
    normalized_interval = interval.strip().lower()
    if not normalized_symbol or not normalized_symbol.isalnum():
        raise ValueError("symbol must contain only letters and digits, e.g. BTCIRT")
    if normalized_interval not in NOBITEX_RESOLUTIONS:
        supported = ", ".join(NOBITEX_RESOLUTIONS)
        raise ValueError(f"unsupported Nobitex interval '{interval}'; supported: {supported}")
    if isinstance(to_epoch, bool) or not isinstance(to_epoch, int) or to_epoch <= 0:
        raise ValueError("to_epoch must be a positive Unix timestamp in seconds")
    if to_epoch > int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("to_epoch cannot be in the future; future-dated market data is not admissible")
    if from_epoch is not None and (
        isinstance(from_epoch, bool) or not isinstance(from_epoch, int) or from_epoch <= 0
    ):
        raise ValueError("from_epoch must be a positive Unix timestamp in seconds")
    if from_epoch is not None and from_epoch >= to_epoch:
        raise ValueError("from_epoch must be earlier than to_epoch")
    if not 1 <= countback <= MAX_CANDLES_PER_REQUEST:
        raise ValueError(f"countback must be between 1 and {MAX_CANDLES_PER_REQUEST}")
    params: dict[str, str | int] = {
        "symbol": normalized_symbol,
        "resolution": NOBITEX_RESOLUTIONS[normalized_interval],
        "to": to_epoch,
    }
    if from_epoch is not None:
        params["from"] = from_epoch
    else:
        params["countback"] = countback
    url = f"{base_url.rstrip('/')}/market/udf/history?{urlencode(params)}"
    payload = _bounded_get_json(url, timeout_seconds)
    candles = parse_candle_history(payload, normalized_symbol, normalized_interval)
    for candle in candles:
        if int(candle.timestamp.timestamp()) > to_epoch:
            raise ValueError("Nobitex returned a candle timestamp later than the requested --to time")
    if include_incomplete:
        return candles
    interval_seconds = {
        "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
        "1h": 3600, "3h": 10800, "4h": 14400, "6h": 21600,
        "12h": 43200, "1d": 86400, "2d": 172800, "3d": 259200,
    }[normalized_interval]
    cutoff = datetime.fromtimestamp(to_epoch, tz=timezone.utc)
    return [candle for candle in candles if candle.timestamp.timestamp() + interval_seconds <= cutoff.timestamp()]
