"""Strict offline OHLCV CSV ingestion for research and simulation only."""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from arash.data.validation import DataValidationError, validate_candle_series
from arash.domain.models import Candle

REQUIRED_COLUMNS = {
    "timestamp", "symbol", "interval", "open", "high", "low", "close", "volume"
}


class CSVIngestionError(ValueError):
    """Raised when an OHLCV CSV is invalid or incomplete."""


def load_candles_csv(path: str | Path) -> list[Candle]:
    csv_path = Path(path)
    if not csv_path.is_file():
        raise CSVIngestionError(f"CSV file does not exist: {csv_path}")

    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise CSVIngestionError("CSV is empty or has no header row")
            normalized_headers = {name.strip().lower() for name in reader.fieldnames if name}
            missing = REQUIRED_COLUMNS - normalized_headers
            if missing:
                raise CSVIngestionError(
                    "CSV is missing required columns: " + ", ".join(sorted(missing))
                )

            candles: list[Candle] = []
            for line_number, raw_row in enumerate(reader, start=2):
                row = {
                    (key.strip().lower() if key else ""): (value.strip() if value else "")
                    for key, value in raw_row.items()
                }
                if not any(row.values()):
                    continue
                try:
                    timestamp_text = row["timestamp"].replace("Z", "+00:00")
                    timestamp = datetime.fromisoformat(timestamp_text)
                    decimal_values = {
                        field: Decimal(row[field])
                        for field in ("open", "high", "low", "close", "volume")
                    }
                    candle = Candle(
                        symbol=row["symbol"],
                        interval=row["interval"],
                        timestamp=timestamp,
                        **decimal_values,
                    )
                except (ValueError, InvalidOperation, KeyError) as exc:
                    raise CSVIngestionError(f"Invalid row at line {line_number}: {exc}") from exc
                candles.append(candle)
    except UnicodeDecodeError as exc:
        raise CSVIngestionError("CSV must be UTF-8 encoded") from exc
    except OSError as exc:
        raise CSVIngestionError(f"Could not read CSV: {exc}") from exc

    try:
        return validate_candle_series(candles)
    except DataValidationError as exc:
        raise CSVIngestionError(f"CSV time-series validation failed: {exc}") from exc
