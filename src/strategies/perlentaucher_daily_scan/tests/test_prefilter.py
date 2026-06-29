from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.prefilter import (
    build_volume_prefilter_metrics,
    select_volume_prefilter_candidates,
)


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
            "timestamp": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def test_volume_prefilter_metrics_flag_expected_candidate() -> None:
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
    bars = pd.concat([passed, blocked], ignore_index=True)

    metrics = build_volume_prefilter_metrics(bars, as_of_date="2026-04-08")
    candidates = select_volume_prefilter_candidates(metrics)

    assert set(metrics["symbol"]) == {"PASS", "BLOCKED"}
    pass_row = metrics.loc[metrics["symbol"] == "PASS"].iloc[0]
    blocked_row = metrics.loc[metrics["symbol"] == "BLOCKED"].iloc[0]

    assert bool(pass_row["eligible"]) is True
    assert bool(pass_row["price_in_range"]) is True
    assert bool(pass_row["volume_expansion_ok"]) is True
    assert bool(pass_row["above_sma"]) is True

    assert bool(blocked_row["eligible"]) is False
    assert bool(blocked_row["price_in_range"]) is False
    assert list(candidates["symbol"]) == ["PASS"]


def test_volume_prefilter_keeps_symbols_without_required_volume_expansion() -> None:
    dates = pd.date_range("2026-01-01", periods=70, freq="B", tz="America/New_York")
    weak = _build_symbol_frame(
        "WEAK",
        dates,
        base_close=6.0,
        last_closes=[6.0, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6],
        base_volume=200_000.0,
        last_volumes=[210_000.0, 215_000.0, 220_000.0, 225_000.0, 230_000.0, 235_000.0, 240_000.0],
    )

    metrics = build_volume_prefilter_metrics(weak, as_of_date="2026-04-08")
    row = metrics.iloc[0]

    assert bool(row["has_prior_window"]) is True
    assert bool(row["liquidity_ok"]) is True
    assert bool(row["volume_expansion_ok"]) is False
    assert bool(row["eligible"]) is True


def test_volume_prefilter_requires_standard_daily_columns() -> None:
    bars = pd.DataFrame({"symbol": ["AAPL"], "timestamp": pd.to_datetime(["2026-04-08"], utc=True)})

    try:
        build_volume_prefilter_metrics(bars, as_of_date="2026-04-08")
    except ValueError as exc:
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing columns")


def test_volume_prefilter_keeps_marketdata_stream_daily_dates_stable() -> None:
    bars = pd.DataFrame(
        {
            "symbol": ["SHIFT"] * 3,
            "timestamp": pd.to_datetime(
                [
                    "2026-06-08T00:00:00Z",
                    "2026-06-09T00:00:00Z",
                    "2026-06-10T00:00:00Z",
                ],
                utc=True,
            ),
            "low": [9.0, 19.0, 99.0],
            "close": [10.0, 20.0, 100.0],
            "volume": [100_000.0, 120_000.0, 140_000.0],
        }
    )

    metrics = build_volume_prefilter_metrics(
        bars,
        as_of_date="2026-06-09",
        sma_window=2,
        recent_days=2,
        recent_low_window=2,
    )

    row = metrics.iloc[0]
    assert row["target_close"] == 20.0


def test_volume_prefilter_excludes_stale_symbols_missing_as_of_bar() -> None:
    dates = pd.date_range("2026-01-01", periods=70, freq="B", tz="America/New_York")
    current = _build_symbol_frame(
        "CURRENT",
        dates,
        base_close=5.0,
        last_closes=[6.0, 6.2, 6.5, 7.0, 7.5, 8.5, 9.5],
        base_volume=200_000.0,
        last_volumes=[650_000.0, 670_000.0, 690_000.0, 710_000.0, 730_000.0, 750_000.0, 770_000.0],
    )
    stale = _build_symbol_frame(
        "STALE",
        dates[:-1],
        base_close=5.0,
        last_closes=[6.0, 6.2, 6.5, 7.0, 7.5, 8.5, 9.5],
        base_volume=200_000.0,
        last_volumes=[650_000.0, 670_000.0, 690_000.0, 710_000.0, 730_000.0, 750_000.0, 770_000.0],
    )
    bars = pd.concat([current, stale], ignore_index=True)

    as_of_date = str(dates[-1].date())
    metrics = build_volume_prefilter_metrics(bars, as_of_date=as_of_date)
    candidates = select_volume_prefilter_candidates(metrics)

    current_row = metrics.loc[metrics["symbol"] == "CURRENT"].iloc[0]
    stale_row = metrics.loc[metrics["symbol"] == "STALE"].iloc[0]

    assert bool(current_row["eligible"]) is True
    assert bool(current_row["has_current_bar"]) is True
    assert bool(stale_row["has_current_bar"]) is False
    assert stale_row["latest_session_date"] == str(dates[-2].date())
    assert bool(stale_row["eligible"]) is False
    assert list(candidates["symbol"]) == ["CURRENT"]
