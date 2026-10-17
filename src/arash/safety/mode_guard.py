"""Strict operating-mode allowlist for the research-first foundation."""

from enum import StrEnum


class OperatingMode(StrEnum):
    RESEARCH = "research"
    PAPER = "paper"


class UnsafeModeError(ValueError):
    """Raised when an unsupported operating mode is requested."""


def parse_mode(value: str) -> OperatingMode:
    normalized = value.strip().lower()
    try:
        return OperatingMode(normalized)
    except ValueError as exc:
        raise UnsafeModeError(
            f"Mode {value!r} is blocked. Foundation permits only: research, paper."
        ) from exc
