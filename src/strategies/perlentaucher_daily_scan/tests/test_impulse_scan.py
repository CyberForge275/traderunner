from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.impulse_scan import (
    FINAL_TRIGGER_MODE,
    FIRST_TRIGGER_MODE,
    ImpulseScanCriteria,
    build_impulse_scan_artifacts,
)


def _build_impulse_symbol_frame(
    symbol: str,
    dates: pd.DatetimeIndex,
    *,
    breakout_close: float,
    breakout_volume: float,
    confirm_close: float,
    confirm_volume: float,
    breakout_open: float = 3.2,
    breakout_high: float = 4.2,
    breakout_low: float = 3.1,
    confirm_open: float = 3.6,
    confirm_high: float = 4.3,
    confirm_low: float = 3.4,
) -> pd.DataFrame:
    pre_closes = [2.5 + 0.02 * idx for idx in range(30)]
    pre_volumes = [180_000.0 + 1_000.0 * idx for idx in range(30)]
    closes = pre_closes + [breakout_close, confirm_close]
    volumes = pre_volumes + [breakout_volume, confirm_volume]

    opens = [close_value - 0.05 for close_value in pre_closes]
    highs = [close_value + 0.10 for close_value in pre_closes]
    lows = [close_value - 0.10 for close_value in pre_closes]

    opens += [breakout_open, confirm_open]
    highs += [breakout_high, confirm_high]
    lows += [breakout_low, confirm_low]

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


def _criteria() -> ImpulseScanCriteria:
    return ImpulseScanCriteria(
        dataset_path=None,
        pre_window=30,
        confirm_offset=1,
        trim_top_n=1,
        trim_bottom_n=1,
        cold_phase_price_min=2.0,
        cold_phase_price_max=9.0,
        cold_phase_mean_volume_min=100_000.0,
        cold_phase_mean_volume_max=1_500_000.0,
        cold_phase_median_volume_min=80_000.0,
        cold_phase_median_volume_max=1_200_000.0,
        min_price_lr_trimmed=-0.1,
        min_vol_lr_trimmed=-100_000.0,
        min_price_ratio_prev_to_breakout=1.172897,
        min_volume_ratio_prev_to_breakout=19.617994,
        min_price_ratio_prev_to_confirm=1.158879,
        min_volume_ratio_prev_to_confirm=3.01405,
        require_breakout_green=False,
        min_confirm_close_vs_breakout_close=0.9,
        min_confirm_close_position_in_range=0.5,
        min_pre_max_drawdown=-0.6,
        max_pre_gap_down_count=8,
        invalid_symbols=frozenset({"TERN"}),
    )


def test_build_impulse_scan_artifacts_returns_first_trigger_candidates_by_day() -> None:
    dates = pd.date_range("2026-01-01", periods=32, freq="B", tz="UTC")
    breakout_date = str(dates[30].date())

    passed = _build_impulse_symbol_frame(
        "PASS",
        dates,
        breakout_close=4.00,
        breakout_volume=5_000_000.0,
        confirm_close=4.20,
        confirm_volume=900_000.0,
    )
    first_only = _build_impulse_symbol_frame(
        "FIRST",
        dates,
        breakout_close=4.00,
        breakout_volume=5_000_000.0,
        confirm_close=3.70,
        confirm_volume=300_000.0,
        confirm_high=3.85,
    )
    invalid = _build_impulse_symbol_frame(
        "TERN",
        dates,
        breakout_close=4.10,
        breakout_volume=5_500_000.0,
        confirm_close=4.30,
        confirm_volume=900_000.0,
    )

    raw_df = pd.concat([passed, first_only, invalid], ignore_index=True)
    artifacts = build_impulse_scan_artifacts(
        raw_daily_df=raw_df,
        valid_from=breakout_date,
        valid_to=breakout_date,
        trigger_mode=FIRST_TRIGGER_MODE,
        criteria=_criteria(),
    )

    assert list(artifacts.summary_df["as_of_date"]) == [breakout_date]
    assert artifacts.summary_df.iloc[0]["symbol_count"] == 2
    assert artifacts.summary_df.iloc[0]["symbols_csv"] == "FIRST,PASS"
    assert artifacts.summary_df.iloc[0]["entry_dates_csv"] == f"{dates[31].date()},{dates[31].date()}"
    assert artifacts.summary_df.iloc[0]["entry_prices_csv"] == "3.60,3.60"
    assert set(artifacts.detail_df["symbol"]) == {"FIRST", "PASS"}
    assert artifacts.detail_df["first_trigger_passed"].all()
    assert artifacts.detail_df.loc[artifacts.detail_df["symbol"] == "FIRST", "final_trigger_passed"].item() is False


def test_build_impulse_scan_artifacts_returns_only_confirmed_candidates_for_final_trigger() -> None:
    dates = pd.date_range("2026-01-01", periods=32, freq="B", tz="UTC")
    breakout_date = str(dates[30].date())

    passed = _build_impulse_symbol_frame(
        "PASS",
        dates,
        breakout_close=4.00,
        breakout_volume=5_000_000.0,
        confirm_close=4.20,
        confirm_volume=900_000.0,
    )
    first_only = _build_impulse_symbol_frame(
        "FIRST",
        dates,
        breakout_close=4.00,
        breakout_volume=5_000_000.0,
        confirm_close=3.70,
        confirm_volume=300_000.0,
        confirm_high=3.85,
    )

    raw_df = pd.concat([passed, first_only], ignore_index=True)
    artifacts = build_impulse_scan_artifacts(
        raw_daily_df=raw_df,
        valid_from=breakout_date,
        valid_to=breakout_date,
        trigger_mode=FINAL_TRIGGER_MODE,
        criteria=_criteria(),
    )

    assert list(artifacts.summary_df["as_of_date"]) == [breakout_date]
    assert artifacts.summary_df.iloc[0]["symbol_count"] == 1
    assert artifacts.summary_df.iloc[0]["symbols_csv"] == "PASS"
    assert artifacts.summary_df.iloc[0]["entry_dates_csv"] == str(dates[31].date())
    assert artifacts.summary_df.iloc[0]["entry_prices_csv"] == "3.60"
    assert list(artifacts.detail_df["symbol"]) == ["PASS"]
    assert artifacts.detail_df["final_trigger_passed"].all()
