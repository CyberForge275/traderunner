from __future__ import annotations

from datetime import date

from strategies.perlentaucher_daily_scan.marketdata_request import (
    DEFAULT_MIN_FETCH_CALENDAR_DAYS,
    DEFAULT_MIN_HISTORY_DAYS,
    build_stock_universe_request,
)


def test_build_stock_universe_request_enforces_default_min_history_days() -> None:
    req = build_stock_universe_request(
        date_from="2026-04-21",
        date_to="2026-04-21",
        params={"min_history_days": DEFAULT_MIN_HISTORY_DAYS},
    )

    assert req.market == "US"
    assert req.asset_class == "stock"
    assert req.date_to == date(2026, 4, 21)
    assert req.lookback_days == DEFAULT_MIN_HISTORY_DAYS
    assert req.fetch_calendar_days == 177
    assert req.date_from == date(2025, 10, 27)


def test_build_stock_universe_request_allows_only_longer_history() -> None:
    req = build_stock_universe_request(
        date_from="2026-04-21",
        date_to="2026-04-21",
        params={"min_history_days": 140},
    )

    assert req.lookback_days == 140
    assert req.fetch_calendar_days == 231
    assert req.date_from == date(2025, 9, 3)


def test_build_stock_universe_request_rejects_shorter_history_than_floor() -> None:
    try:
        build_stock_universe_request(
            date_from="2026-04-21",
            date_to="2026-04-21",
            params={"min_history_days": 90},
        )
    except ValueError as exc:
        assert "min_history_days must be int >=" in str(exc)
    else:
        raise AssertionError("expected ValueError for too-short history window")
