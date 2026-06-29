from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.match_scan import scan_match_artifacts, scan_match_dates


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


def test_scan_match_dates_returns_final_matches_per_trading_day() -> None:
    dates = pd.date_range("2025-10-01", periods=140, freq="B", tz="UTC")
    shared_last_closes = [6.0, 6.2, 6.5, 7.0, 7.5, 8.5, 9.5]
    shared_last_volumes = [650_000.0, 670_000.0, 690_000.0, 710_000.0, 730_000.0, 750_000.0, 770_000.0]

    axti = _build_symbol_frame(
        "AXTI",
        dates,
        base_close=20.0,
        last_closes=[value + 15.0 for value in shared_last_closes],
        base_volume=200_000.0,
        last_volumes=shared_last_volumes,
    )
    passed = _build_symbol_frame(
        "PASS",
        dates,
        base_close=5.0,
        last_closes=shared_last_closes,
        base_volume=200_000.0,
        last_volumes=shared_last_volumes,
    )
    miss = _build_symbol_frame(
        "MISS",
        dates,
        base_close=5.0,
        last_closes=[5.0, 5.1, 5.3, 5.6, 6.0, 6.5, 7.1],
        base_volume=200_000.0,
        last_volumes=[650_000.0, 660_000.0, 670_000.0, 680_000.0, 690_000.0, 700_000.0, 710_000.0],
    )

    as_of_date = str(dates[-1].date())
    out = scan_match_dates(
        pd.concat([axti, passed, miss], ignore_index=True),
        valid_from=as_of_date,
        valid_to=as_of_date,
        sweet_spot_pairs=[("AXTI", as_of_date)],
        match_mode="price_vol",
        max_candidates=25,
    )

    assert list(out["as_of_date"]) == [as_of_date]
    assert list(out["symbol_count"]) == [1]
    assert list(out["symbols_csv"]) == ["PASS"]
    assert list(out["closest_miss_symbols_csv"]) == ["MISS"]
    assert out.loc[0, "closest_miss_scores_csv"] != ""


def test_scan_match_artifacts_provides_feature_deltas_for_top_miss() -> None:
    dates = pd.date_range("2025-10-01", periods=140, freq="B", tz="UTC")
    shared_last_closes = [6.0, 6.2, 6.5, 7.0, 7.5, 8.5, 9.5]
    shared_last_volumes = [650_000.0, 670_000.0, 690_000.0, 710_000.0, 730_000.0, 750_000.0, 770_000.0]

    axti = _build_symbol_frame(
        "AXTI",
        dates,
        base_close=20.0,
        last_closes=[value + 15.0 for value in shared_last_closes],
        base_volume=200_000.0,
        last_volumes=shared_last_volumes,
    )
    passed = _build_symbol_frame(
        "PASS",
        dates,
        base_close=5.0,
        last_closes=shared_last_closes,
        base_volume=200_000.0,
        last_volumes=shared_last_volumes,
    )
    miss = _build_symbol_frame(
        "MISS",
        dates,
        base_close=5.0,
        last_closes=[5.0, 5.1, 5.3, 5.6, 6.0, 6.5, 7.1],
        base_volume=200_000.0,
        last_volumes=[650_000.0, 660_000.0, 670_000.0, 680_000.0, 690_000.0, 700_000.0, 710_000.0],
    )

    as_of_date = str(dates[-1].date())
    out = scan_match_artifacts(
        pd.concat([axti, passed, miss], ignore_index=True),
        valid_from=as_of_date,
        valid_to=as_of_date,
        sweet_spot_pairs=[("AXTI", as_of_date)],
        match_mode="price_vol",
        max_candidates=25,
    )

    assert list(out.summary_df["closest_miss_symbols_csv"]) == ["MISS"]
    assert list(out.detail_df["symbol"]) == ["MISS"]
    assert list(out.detail_df["closest_reference_symbol"]) == ["AXTI"]
    assert "delta_price_short" in out.detail_df.columns
    assert out.detail_df.loc[0, "delta_price_short"] < 0
