"""Contract and integration tests for public market-data parsing and rolling features."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from arash.data.streaming import (
    BookLevel,
    OrderBookSnapshot,
    PublicMarketStreamError,
    PublicTrade,
    parse_public_orderbook_message,
    parse_public_trade_message,
)
from arash.research.streaming_features import StreamingMicrostructureFeatures


UTC = timezone.utc
RECEIVED = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)


def _frame(channel: str, payload: dict[str, object], offset: int = 1) -> str:
    return json.dumps({
        "push": {
            "channel": channel,
            "pub": {"data": json.dumps(payload), "offset": offset},
        }
    })


def _epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _book(*, when: datetime = RECEIVED) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        symbol="BTCIRT",
        source="test-fixture",
        exchange_timestamp=when,
        received_at=when + timedelta(milliseconds=10),
        bids=(BookLevel(Decimal("99"), Decimal("2")),),
        asks=(BookLevel(Decimal("101"), Decimal("3")),),
        last_trade_price=Decimal("100"),
        update_offset=1,
    )


def _trade(
    side: str,
    price: str,
    volume: str,
    *,
    when: datetime = RECEIVED,
    offset: int = 1,
) -> PublicTrade:
    return PublicTrade(
        symbol="BTCIRT",
        exchange_timestamp=when,
        received_at=when + timedelta(milliseconds=5),
        side=side,
        price=Decimal(price),
        volume=Decimal(volume),
        update_offset=offset,
    )


def test_parse_public_orderbook_matches_documented_centrifugo_envelope() -> None:
    payload = {
        "bids": [["99", "2"], ["98", "4"]],
        "asks": [["101", "3"], ["102", "5"]],
        "lastTradePrice": "100",
        "lastUpdate": _epoch_ms(RECEIVED),
    }
    event = parse_public_orderbook_message(
        "BTCIRT", _frame("public:orderbook-BTCIRT", payload, offset=42),
        received_at=RECEIVED + timedelta(milliseconds=20),
    )
    assert event is not None
    assert event.symbol == "BTCIRT"
    assert event.best_bid == Decimal("99")
    assert event.best_ask == Decimal("101")
    assert event.update_offset == 42
    assert event.to_dict()["read_only"] is True
    assert event.to_dict()["orders_submitted"] is False


def test_parse_public_trade_uses_reported_side_and_provider_units() -> None:
    payload = {
        "price": "100",
        "time": _epoch_ms(RECEIVED),
        "type": "buy",
        "volume": "0.5",
    }
    event = parse_public_trade_message(
        "BTCIRT", _frame("public:trades-BTCIRT", payload, offset=7),
        received_at=RECEIVED + timedelta(milliseconds=15),
    )
    assert event is not None
    assert event.side == "buy"
    assert event.quote_notional == Decimal("50.0")
    assert event.update_offset == 7


def test_parser_ignores_heartbeats_and_unrelated_channels() -> None:
    assert parse_public_orderbook_message("BTCIRT", "{}", received_at=RECEIVED) is None
    unrelated = _frame(
        "public:orderbook-ETHUSDT",
        {"bids": [["99", "2"]], "asks": [["101", "3"]], "lastUpdate": _epoch_ms(RECEIVED)},
    )
    assert parse_public_orderbook_message(
        "BTCIRT", unrelated, received_at=RECEIVED
    ) is None


def test_parser_rejects_crossed_books_and_unknown_trade_side() -> None:
    crossed = {
        "bids": [["101", "2"]],
        "asks": [["101", "3"]],
        "lastUpdate": _epoch_ms(RECEIVED),
    }
    with pytest.raises(PublicMarketStreamError, match="crossed or locked"):
        parse_public_orderbook_message(
            "BTCIRT", _frame("public:orderbook-BTCIRT", crossed), received_at=RECEIVED
        )
    bad_trade = {
        "price": "100",
        "time": _epoch_ms(RECEIVED),
        "type": "unknown",
        "volume": "0.5",
    }
    with pytest.raises(PublicMarketStreamError, match="trade type"):
        parse_public_trade_message(
            "BTCIRT", _frame("public:trades-BTCIRT", bad_trade), received_at=RECEIVED
        )


def test_streaming_features_aggregate_trades_and_enrich_with_book() -> None:
    engine = StreamingMicrostructureFeatures(window_seconds=60, depth_limit=1)
    book_report = engine.observe(_book())
    assert book_report["microstructure_features"]["latest_orderbook"]["best_bid"] == "99"

    buy_report = engine.observe(_trade("buy", "100", "2", offset=2))
    sell_report = engine.observe(_trade(
        "sell", "110", "1", when=RECEIVED + timedelta(seconds=1), offset=3
    ))
    features = sell_report["microstructure_features"]
    assert features["trade_count"] == 2
    assert features["reported_buy_volume_base"] == "2"
    assert features["reported_sell_volume_base"] == "1"
    assert Decimal(features["reported_buy_notional_quote"]) == Decimal("200")
    assert Decimal(features["reported_sell_notional_quote"]) == Decimal("110")
    assert Decimal(features["rolling_trade_vwap"]) == Decimal(310) / Decimal(3)
    assert features["signal_generated"] is False
    assert sell_report["orders_submitted"] is False
    assert buy_report["interpretation_boundary"]


def test_streaming_features_prune_trades_outside_window() -> None:
    engine = StreamingMicrostructureFeatures(window_seconds=5, depth_limit=1)
    engine.observe(_trade("buy", "100", "2", when=RECEIVED))
    report = engine.observe(_trade(
        "sell", "101", "1", when=RECEIVED + timedelta(seconds=7), offset=2
    ))
    features = report["microstructure_features"]
    assert features["trade_count"] == 1
    assert features["reported_buy_volume_base"] == "0"
    assert features["reported_sell_volume_base"] == "1"
    assert features["trade_events_pruned_by_window_or_capacity"] == 1
