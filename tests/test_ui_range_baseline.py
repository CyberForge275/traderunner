from datetime import date

import pytest

from trading_dashboard.callbacks.run_backtest_callback import _resolve_ui_backtest_range


def test_days_back_mode_30_days_parity():
    start_date, end_date = _resolve_ui_backtest_range(
        date_mode="days_back",
        anchor_date="2026-02-11",
        days_back=30,
        explicit_start=None,
        explicit_end=None,
    )
    assert start_date == date(2026, 1, 12)
    assert end_date == date(2026, 2, 11)


def test_days_back_mode_300_days_parity():
    start_date, end_date = _resolve_ui_backtest_range(
        date_mode="days_back",
        anchor_date="2026-02-11",
        days_back=300,
        explicit_start=None,
        explicit_end=None,
    )
    assert start_date == date(2025, 4, 17)
    assert end_date == date(2026, 2, 11)


def test_explicit_mode_parity():
    start_date, end_date = _resolve_ui_backtest_range(
        date_mode="explicit",
        anchor_date=None,
        days_back=None,
        explicit_start="2026-01-13",
        explicit_end="2026-02-11",
    )
    assert start_date == date(2026, 1, 13)
    assert end_date == date(2026, 2, 11)


def test_invalid_iso_date_raises_value_error():
    with pytest.raises(ValueError):
        _resolve_ui_backtest_range(
            date_mode="days_back",
            anchor_date="2026-99-11",
            days_back=30,
            explicit_start=None,
            explicit_end=None,
        )
