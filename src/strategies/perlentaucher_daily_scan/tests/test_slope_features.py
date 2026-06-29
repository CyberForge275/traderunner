from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.slope_features import (
    build_inspection_view,
    build_slope_feature_frame,
)


def _build_symbol_frame(symbol: str, dates: pd.DatetimeIndex, *, slope_scale: float) -> pd.DataFrame:
    steps = list(range(len(dates)))
    closes = [10.0 + slope_scale * step for step in steps]
    volumes = [100_000.0 + 10_000.0 * slope_scale * step for step in steps]
    return pd.DataFrame(
        {
            "symbol": symbol,
            "timestamp": dates,
            "open": [close - 0.1 for close in closes],
            "high": [close + 0.2 for close in closes],
            "low": [close - 0.3 for close in closes],
            "close": closes,
            "volume": volumes,
        }
    )


def test_build_slope_feature_frame_emits_latest_symbol_features() -> None:
    dates = pd.date_range("2025-10-01", periods=140, freq="B", tz="UTC")
    daily_df = pd.concat(
        [
            _build_symbol_frame("AAPL", dates, slope_scale=1.0),
            _build_symbol_frame("MSFT", dates, slope_scale=2.0),
        ],
        ignore_index=True,
    )

    out = build_slope_feature_frame(daily_df, as_of_date="2026-04-13")

    assert list(out.columns) == [
        "symbol",
        "as_of_date",
        "price_short",
        "price_mid",
        "price_l_long",
        "vol_short",
        "vol_mid",
        "vol_l_long",
    ]
    assert set(out["symbol"]) == {"AAPL", "MSFT"}
    assert set(out["as_of_date"]) == {"2026-04-13"}

    aapl = out.loc[out["symbol"] == "AAPL"].iloc[0]
    msft = out.loc[out["symbol"] == "MSFT"].iloc[0]
    assert msft["price_short"] > aapl["price_short"]
    assert msft["vol_short"] > aapl["vol_short"]
    assert aapl["price_l_long"] > 0
    assert aapl["vol_l_long"] > 0


def test_build_slope_feature_frame_requires_enough_history_for_long_shift() -> None:
    dates = pd.date_range("2026-01-01", periods=80, freq="B", tz="UTC")
    daily_df = _build_symbol_frame("AAPL", dates, slope_scale=1.0)

    out = build_slope_feature_frame(daily_df, as_of_date="2026-04-22")

    assert out.empty


def test_build_inspection_view_merges_latest_candidate_rows_with_features() -> None:
    candidate_daily_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "MSFT"],
            "timestamp": pd.to_datetime(
                ["2026-04-12T00:00:00Z", "2026-04-13T00:00:00Z", "2026-04-13T00:00:00Z"],
                utc=True,
            ),
            "open": [1.0, 1.1, 2.0],
            "high": [1.2, 1.3, 2.2],
            "low": [0.9, 1.0, 1.9],
            "close": [1.1, 1.2, 2.1],
            "volume": [100.0, 110.0, 200.0],
        }
    )
    feature_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT"],
            "as_of_date": ["2026-04-13", "2026-04-13"],
            "price_short": [0.1, 0.2],
            "price_mid": [0.1, 0.2],
            "price_l_long": [0.3, 0.4],
            "vol_short": [0.5, 0.6],
            "vol_mid": [0.5, 0.6],
            "vol_l_long": [0.7, 0.8],
        }
    )

    out = build_inspection_view(candidate_daily_df, feature_df, as_of_date="2026-04-13")

    assert set(out["symbol"]) == {"AAPL", "MSFT"}
    assert "price_short" in out.columns
    assert len(out) == 2
