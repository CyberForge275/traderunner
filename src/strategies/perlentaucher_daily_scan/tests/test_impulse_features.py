from __future__ import annotations

import math

import pandas as pd

from strategies.perlentaucher_daily_scan.impulse_features import (
    build_impulse_features,
    compute_trimmed_window_lr,
    compute_window_lr,
)


def _build_symbol_frame(
    symbol: str,
    dates: pd.DatetimeIndex,
    *,
    closes: list[float],
    volumes: list[float],
) -> pd.DataFrame:
    session_ts = dates + pd.Timedelta(hours=20)
    return pd.DataFrame(
        {
            "symbol": symbol,
            "timestamp": session_ts,
            "open": [close - 0.05 for close in closes],
            "high": [close + 0.10 for close in closes],
            "low": [close - 0.10 for close in closes],
            "close": closes,
            "volume": volumes,
        }
    )


def test_compute_window_lr_returns_last_window_slope() -> None:
    values = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = compute_window_lr(values, window=5)
    assert math.isclose(out, 1.0)


def test_compute_trimmed_window_lr_reduces_spike_influence() -> None:
    values = pd.Series([10.0, 11.0, 12.0, 40.0, 14.0, 15.0, 16.0])
    raw = compute_window_lr(values, window=7)
    trimmed = compute_trimmed_window_lr(values, window=7, trim_top_n=1, trim_bottom_n=1)
    assert not math.isclose(trimmed, raw)
    assert math.isclose(trimmed, 1.3)
    assert trimmed > 0.0


def test_build_impulse_features_returns_prev_breakout_confirm_ratios() -> None:
    dates = pd.date_range("2025-08-01", periods=35, freq="B", tz="UTC")
    closes = [2.0] * 32 + [2.14, 2.51, 2.48]
    volumes = [200_000.0] * 32 + [226_554.0, 4_444_535.0, 682_845.0]
    daily_df = _build_symbol_frame("AXTI", dates, closes=closes, volumes=volumes)

    out = build_impulse_features(
        daily_df,
        symbol="AXTI",
        breakout_date=str(dates[-2].date()),
        pre_window=30,
        confirm_offset=1,
        trim_top_n=1,
        trim_bottom_n=1,
    )

    assert out["symbol"] == "AXTI"
    assert out["breakout_date"] == str(dates[-2].date())
    assert out["previous_date"] == str(dates[-3].date())
    assert out["confirm_date"] == str(dates[-1].date())
    assert math.isclose(out["price_ratio_prev_to_breakout"], 2.51 / 2.14)
    assert math.isclose(out["volume_ratio_prev_to_breakout"], 4_444_535.0 / 226_554.0)
    assert math.isclose(out["price_ratio_prev_to_confirm"], 2.48 / 2.14)
    assert math.isclose(out["volume_ratio_prev_to_confirm"], 682_845.0 / 226_554.0)
    assert out["breakout_green"] is True
    assert math.isclose(out["breakout_close_position_in_range"], (2.51 - (2.51 - 0.10)) / ((2.51 + 0.10) - (2.51 - 0.10)))
    assert math.isclose(out["confirm_close_vs_breakout_close"], 2.48 / 2.51)
    assert math.isclose(out["confirm_close_position_in_range"], (2.48 - (2.48 - 0.10)) / ((2.48 + 0.10) - (2.48 - 0.10)))
    assert math.isclose(out["confirm_vol_vs_breakout_vol"], 682_845.0 / 4_444_535.0)
    assert math.isclose(out["pre_max_drawdown"], (2.14 / 2.14) - 1.0)
    assert out["pre_gap_down_count"] == 0
    assert pd.notna(out["price_lr_raw"])
    assert pd.notna(out["price_lr_trimmed"])
    assert out["pre_window"] == 30


def test_build_impulse_features_handles_missing_confirm_day() -> None:
    dates = pd.date_range("2025-08-01", periods=34, freq="B", tz="UTC")
    closes = [2.0] * 32 + [2.14, 2.51]
    volumes = [200_000.0] * 32 + [226_554.0, 4_444_535.0]
    daily_df = _build_symbol_frame("AXTI", dates, closes=closes, volumes=volumes)

    out = build_impulse_features(
        daily_df,
        symbol="AXTI",
        breakout_date=str(dates[-1].date()),
        pre_window=30,
        confirm_offset=1,
    )

    assert out["confirm_date"] is None
    assert pd.isna(out["price_ratio_prev_to_confirm"])
    assert pd.isna(out["volume_ratio_prev_to_confirm"])


def test_build_impulse_features_keeps_marketdata_stream_daily_dates_stable() -> None:
    daily_df = pd.DataFrame(
        {
            "symbol": ["AXTI"] * 4,
            "timestamp": pd.to_datetime(
                [
                    "2026-06-08T00:00:00Z",
                    "2026-06-09T00:00:00Z",
                    "2026-06-10T00:00:00Z",
                    "2026-06-11T00:00:00Z",
                ],
                utc=True,
            ),
            "open": [8.9, 9.9, 14.5, 15.5],
            "high": [9.2, 10.2, 15.2, 16.2],
            "low": [8.8, 9.8, 14.4, 15.4],
            "close": [9.0, 10.0, 15.0, 16.0],
            "volume": [90_000.0, 100_000.0, 300_000.0, 250_000.0],
        }
    )

    out = build_impulse_features(
        daily_df,
        symbol="AXTI",
        breakout_date="2026-06-10",
        pre_window=2,
        confirm_offset=1,
        trim_top_n=0,
        trim_bottom_n=0,
    )

    assert out["previous_date"] == "2026-06-09"
    assert out["breakout_date"] == "2026-06-10"
    assert out["confirm_date"] == "2026-06-11"
    assert math.isclose(out["price_ratio_prev_to_breakout"], 1.5)
