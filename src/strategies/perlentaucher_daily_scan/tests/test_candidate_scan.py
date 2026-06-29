from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.candidate_scan import scan_candidate_dates


def _build_symbol_frame(
    symbol: str,
    dates: pd.DatetimeIndex,
    *,
    base_close: float,
    last_closes: list[float],
    base_volume: float,
    last_volumes: list[float],
) -> pd.DataFrame:
    closes = [base_close] * (len(dates) - len(last_closes)) + list(last_closes)
    volumes = [base_volume] * (len(dates) - len(last_volumes)) + list(last_volumes)
    lows = [c - 0.5 for c in closes]
    opens = [c - 0.1 for c in closes]
    highs = [c + 0.2 for c in closes]
    return pd.DataFrame(
        {
            "symbol": symbol,
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def test_scan_candidate_dates_returns_candidate_symbols_for_each_trading_day() -> None:
    dates = pd.date_range("2026-01-01", periods=70, freq="B", tz="America/New_York")
    passed = _build_symbol_frame(
        "PASS",
        dates,
        base_close=5.0,
        last_closes=[6.0, 6.2, 6.5, 7.0, 7.5, 8.5, 9.5],
        base_volume=200_000.0,
        last_volumes=[650_000.0, 670_000.0, 690_000.0, 710_000.0, 730_000.0, 750_000.0, 770_000.0],
    )
    blocked = _build_symbol_frame(
        "BLOCKED",
        dates,
        base_close=20.0,
        last_closes=[20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7],
        base_volume=300_000.0,
        last_volumes=[900_000.0, 920_000.0, 940_000.0, 960_000.0, 980_000.0, 1_000_000.0, 1_020_000.0],
    )

    out = scan_candidate_dates(
        pd.concat([passed, blocked], ignore_index=True),
        valid_from="2026-04-07",
        valid_to="2026-04-08",
    )

    assert list(out["as_of_date"]) == ["2026-04-07", "2026-04-08"]
    assert list(out["symbol_count"]) == [1, 1]
    assert list(out["symbols_csv"]) == ["PASS", "PASS"]
