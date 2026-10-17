"""Explicit, dependency-free market session calendars for candle-gap audits.

Session windows are local wall-clock intervals. Overnight windows are intentionally
unsupported: represent them as two windows on adjacent weekdays to avoid ambiguity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Mapping, Sequence

SessionWindow = tuple[time, time]


@dataclass(frozen=True, slots=True)
class MarketSessionCalendar:
    """A declared weekly schedule plus full-day closures, not an exchange data feed.

    ``weekly_sessions`` maps Python weekdays (Monday=0 ... Sunday=6) to local
    start/end windows. Windows are start-inclusive and end-exclusive. An empty
    or omitted weekday is closed. ``holidays`` contains ISO dates in calendar timezone.
    """

    name: str
    timezone_name: str
    weekly_sessions: Mapping[int, Sequence[SessionWindow]]
    holidays: frozenset[str] = frozenset()
    source: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("calendar name cannot be empty")
        if not self.timezone_name.strip():
            raise ValueError("calendar timezone must be a non-empty IANA name")
        try:
            ZoneInfo(self.timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown IANA calendar timezone: {self.timezone_name!r}") from exc
        for weekday, windows in self.weekly_sessions.items():
            if isinstance(weekday, bool) or weekday not in range(7):
                raise ValueError("calendar weekday keys must be integers from 0 (Mon) to 6 (Sun)")
            previous_end: time | None = None
            for window in windows:
                if len(window) != 2 or not all(isinstance(item, time) for item in window):
                    raise ValueError("each session window must contain start and end time values")
                start, end = window
                if start.tzinfo is not None or end.tzinfo is not None:
                    raise ValueError("session wall-clock times must be timezone-naive")
                if start >= end:
                    raise ValueError("overnight/empty sessions are unsupported; split across weekdays")
                if previous_end is not None and start < previous_end:
                    raise ValueError("session windows must be sorted and non-overlapping")
                previous_end = end
        for holiday in self.holidays:
            try:
                parsed_holiday = date.fromisoformat(holiday)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid holiday date: {holiday!r}; expected YYYY-MM-DD") from exc
            if parsed_holiday.isoformat() != holiday:
                raise ValueError(f"holiday date must be canonical YYYY-MM-DD: {holiday!r}")
        if self.source is not None:
            required_source_fields = {"provider", "url", "retrieved_at_utc", "content_sha256"}
            if set(self.source) != required_source_fields:
                raise ValueError(
                    "calendar source must contain exactly provider, url, retrieved_at_utc, content_sha256"
                )
            if not self.source["provider"].strip():
                raise ValueError("calendar source provider cannot be empty")
            parsed_url = urlparse(self.source["url"])
            if parsed_url.scheme != "https" or not parsed_url.netloc:
                raise ValueError("calendar source URL must be an absolute HTTPS URL")
            try:
                retrieved_at = datetime.fromisoformat(
                    self.source["retrieved_at_utc"].replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise ValueError("calendar source retrieved_at_utc must be an ISO-8601 timestamp") from exc
            if retrieved_at.tzinfo is None or retrieved_at.utcoffset() != timezone.utc.utcoffset(retrieved_at):
                raise ValueError("calendar source retrieved_at_utc must include UTC timezone")
            digest = self.source["content_sha256"]
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
                raise ValueError("calendar source content_sha256 must be a 64-character SHA-256 hex digest")

    def is_open_at(self, timestamp: datetime) -> bool:
        """Return whether a candle-open timestamp falls inside a declared session."""
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("calendar timestamp must be timezone-aware")
        local = timestamp.astimezone(ZoneInfo(self.timezone_name))
        if local.date().isoformat() in self.holidays:
            return False
        wall_time = local.timetz().replace(tzinfo=None)
        return any(
            start <= wall_time < end
            for start, end in self.weekly_sessions.get(local.weekday(), ())
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "timezone": self.timezone_name,
            "weekly_sessions": {
                str(day): [[start.isoformat(), end.isoformat()] for start, end in windows]
                for day, windows in sorted(self.weekly_sessions.items())
            },
            "holidays": sorted(self.holidays),
            "overnight_sessions_supported": False,
            "source": dict(self.source) if self.source is not None else None,
            "source_status": "DECLARED_UNVERIFIED" if self.source is not None else "NO_SOURCE_DECLARED",
            "source_note": (
                "Source metadata is user-declared; content hash and URL are not independently verified."
                if self.source is not None
                else "User-declared schedule; not automatically verified against an exchange calendar."
            ),
        }


def load_market_calendar(path: str | Path) -> MarketSessionCalendar:
    """Load a bounded JSON calendar definition from a local file.

    Schema: {name, timezone, weekly_sessions: {"0": [["09:00", "17:00"]]},
    holidays: ["YYYY-MM-DD"]}. Unknown fields are rejected to avoid silent policy drift.
    """
    source = Path(path)
    if source.stat().st_size > 256_000:
        raise ValueError("calendar JSON exceeds the 256 KB safety limit")
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key!r}")
            result[key] = value
        return result

    try:
        payload = json.loads(
            source.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("calendar file must contain valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("calendar JSON root must be an object")
    allowed = {"name", "timezone", "weekly_sessions", "holidays", "source"}
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"unknown calendar JSON fields: {', '.join(sorted(unknown))}")
    if not {"name", "timezone", "weekly_sessions"}.issubset(payload):
        raise ValueError("calendar JSON requires name, timezone, and weekly_sessions")
    weekly = payload["weekly_sessions"]
    if not isinstance(weekly, dict):
        raise ValueError("weekly_sessions must be an object keyed by weekday number")
    parsed: dict[int, tuple[SessionWindow, ...]] = {}
    for day_text, windows in weekly.items():
        try:
            day = int(day_text)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid weekday key: {day_text!r}") from exc
        if str(day) != day_text or day not in range(7):
            raise ValueError(f"weekday key must be canonical text '0' through '6': {day_text!r}")
        if not isinstance(windows, list):
            raise ValueError(f"sessions for weekday {day} must be a list")
        day_windows: list[SessionWindow] = []
        for window in windows:
            if not isinstance(window, list) or len(window) != 2 or not all(isinstance(v, str) for v in window):
                raise ValueError("each session must be a two-string list: [start, end]")
            try:
                day_windows.append((time.fromisoformat(window[0]), time.fromisoformat(window[1])))
            except ValueError as exc:
                raise ValueError(f"invalid session time in weekday {day}") from exc
        parsed[day] = tuple(day_windows)
    holidays = payload.get("holidays", [])
    if not isinstance(holidays, list) or any(not isinstance(item, str) for item in holidays):
        raise ValueError("holidays must be a list of ISO date strings")
    if len(set(holidays)) != len(holidays):
        raise ValueError("holidays must not contain duplicate dates")
    source_metadata = payload.get("source")
    if source_metadata is not None:
        if not isinstance(source_metadata, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in source_metadata.items()
        ):
            raise ValueError("source must be an object containing string values")
    if not isinstance(payload["name"], str) or not isinstance(payload["timezone"], str):
        raise ValueError("calendar name and timezone must be strings")
    return MarketSessionCalendar(
        name=payload["name"], timezone_name=payload["timezone"],
        weekly_sessions=parsed, holidays=frozenset(holidays), source=source_metadata,
    )
