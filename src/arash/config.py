"""Configuration loading with a strict simulation-only mode allowlist."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from arash.safety.mode_guard import OperatingMode, parse_mode


@dataclass(frozen=True, slots=True)
class Settings:
    name: str = "ARASH"
    version: str = "0.4.0"
    mode: OperatingMode = OperatingMode.PAPER
    timezone: str = "Asia/Tehran"
    database_path: str = "data/arash.sqlite3"
    currency_label: str = "SIMULATED_UNITS"

    @classmethod
    def from_toml(cls, path: str | Path) -> "Settings":
        with Path(path).open("rb") as file:
            raw = tomllib.load(file)
        app = raw.get("app", {})
        runtime = raw.get("runtime", {})
        storage = raw.get("storage", {})
        reporting = raw.get("reporting", {})
        return cls(
            name=str(app.get("name", "ARASH")),
            version=str(app.get("version", "0.4.0")),
            mode=parse_mode(str(runtime.get("mode", "paper"))),
            timezone=str(runtime.get("timezone", "Asia/Tehran")),
            database_path=str(storage.get("database_path", "data/arash.sqlite3")),
            currency_label=str(reporting.get("currency_label", "SIMULATED_UNITS")),
        )
