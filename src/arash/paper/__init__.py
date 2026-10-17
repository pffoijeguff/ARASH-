"""Offline-only paper trading simulation; no exchange adapters live here."""

from arash.paper.broker import PaperBroker

__all__ = ["PaperBroker"]
