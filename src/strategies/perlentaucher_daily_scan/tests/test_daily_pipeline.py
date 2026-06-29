from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.daily_pipeline import (
    filter_daily_frame_to_candidates,
    normalize_daily_ohlcv_frame,
    run_sweet_spot_daily_pipeline,
    select_prefilter_candidate_symbols,
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
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "adj_close": closes,
            "source": "test",
        }
    )


def test_normalize_daily_ohlcv_frame_prunes_and_sorts_columns() -> None:
    raw = pd.DataFrame(
        {
            "symbol": ["msft", "aapl"],
            "date": ["2026-04-22", "2026-04-21"],
            "open": [2, 1],
            "high": [3, 2],
            "low": [1, 0.5],
            "close": [2.5, 1.5],
            "volume": [200, 100],
            "adj_close": [2.5, 1.5],
            "source": ["x", "y"],
        }
    )

    out = normalize_daily_ohlcv_frame(raw)

    assert list(out.columns) == ["symbol", "timestamp", "open", "high", "low", "close", "volume"]
    assert list(out["symbol"]) == ["AAPL", "MSFT"]
    assert str(out["timestamp"].dtype) == "datetime64[ns, UTC]"


def test_select_prefilter_candidate_symbols_returns_metrics_and_symbols() -> None:
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

    daily_df = normalize_daily_ohlcv_frame(pd.concat([passed, blocked], ignore_index=True))
    metrics, symbols = select_prefilter_candidate_symbols(daily_df, as_of_date="2026-04-08")

    assert set(metrics["symbol"]) == {"PASS", "BLOCKED"}
    assert symbols == ["PASS"]


def test_filter_daily_frame_to_candidates_restricts_symbol_set() -> None:
    raw = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "AAPL"],
            "timestamp": pd.to_datetime(
                ["2026-04-21T00:00:00Z", "2026-04-21T00:00:00Z", "2026-04-22T00:00:00Z"],
                utc=True,
            ),
            "open": [1.0, 2.0, 1.1],
            "high": [1.2, 2.2, 1.3],
            "low": [0.9, 1.8, 1.0],
            "close": [1.1, 2.1, 1.2],
            "volume": [100, 200, 110],
        }
    )

    out = filter_daily_frame_to_candidates(raw, ["AAPL"])

    assert list(out["symbol"].unique()) == ["AAPL"]
    assert len(out) == 2

def test_run_sweet_spot_daily_pipeline_builds_ranked_matches_from_feature_history() -> None:
    dates = pd.date_range("2025-10-01", periods=140, freq="B", tz="UTC")
    shared_last_closes = [6.0, 6.2, 6.5, 7.0, 7.5, 8.5, 9.5]
    shared_last_volumes = [650_000.0, 670_000.0, 690_000.0, 710_000.0, 730_000.0, 750_000.0, 770_000.0]

    aapl = _build_symbol_frame(
        "AAPL",
        dates,
        base_close=5.0,
        last_closes=shared_last_closes,
        base_volume=200_000.0,
        last_volumes=shared_last_volumes,
    )
    msft = _build_symbol_frame(
        "MSFT",
        dates,
        base_close=5.0,
        last_closes=[5.0, 5.1, 5.3, 5.6, 6.0, 6.5, 7.1],
        base_volume=200_000.0,
        last_volumes=[650_000.0, 660_000.0, 670_000.0, 680_000.0, 690_000.0, 700_000.0, 710_000.0],
    )
    ionq = _build_symbol_frame(
        "IONQ",
        dates,
        base_close=20.0,
        last_closes=[c + 15.0 for c in shared_last_closes],
        base_volume=200_000.0,
        last_volumes=shared_last_volumes,
    )

    raw = pd.concat([aapl, msft, ionq], ignore_index=True)
    as_of_date = str(dates[-1].date())
    reference_dates = [str(dates[-offset].date()) for offset in (3, 2, 1)]

    out = run_sweet_spot_daily_pipeline(
        raw,
        as_of_date=as_of_date,
        sweet_spot_pairs=[("IONQ", value) for value in reference_dates],
        match_mode="price_vol",
        max_candidates=10,
    )

    assert out.candidate_symbols == ["AAPL", "MSFT"]
    assert set(reference_dates).issubset(set(out.feature_history_df["as_of_date"]))
    assert list(out.reference_feature_df["symbol"]) == ["IONQ", "IONQ", "IONQ"]

    aapl_row = out.matched_df.loc[out.matched_df["symbol"] == "AAPL"].iloc[0]
    msft_row = out.matched_df.loc[out.matched_df["symbol"] == "MSFT"].iloc[0]

    assert aapl_row["eligibility_reason"] == "MATCHED"
    assert aapl_row["candidate_rank"] == 1.0
    assert msft_row["eligibility_reason"] == "NO_MATCH"
