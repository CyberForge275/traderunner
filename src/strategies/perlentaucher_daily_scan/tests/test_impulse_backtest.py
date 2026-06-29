from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.impulse_backtest import (
    build_first_trigger_backtest_artifacts,
)
from strategies.perlentaucher_daily_scan.impulse_scan import ImpulseScanCriteria


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
        invalid_symbols=frozenset(),
    )


def _build_backtest_frame() -> tuple[pd.DataFrame, str]:
    dates = pd.date_range("2026-01-01", periods=90, freq="B", tz="UTC")
    pre_closes = [2.5 + 0.02 * idx for idx in range(30)]
    pre_volumes = [180_000.0 + 1_000.0 * idx for idx in range(30)]

    breakout_close = 4.00
    breakout_volume = 5_000_000.0
    confirm_open = 4.10
    confirm_close = 4.20
    confirm_volume = 900_000.0

    future_opens = [4.20 + 0.05 * idx for idx in range(58)]
    future_closes = [4.30 + 0.05 * idx for idx in range(58)]
    future_volumes = [250_000.0 + 500.0 * idx for idx in range(58)]

    opens = [value - 0.05 for value in pre_closes] + [3.2, confirm_open] + future_opens
    highs = [value + 0.10 for value in pre_closes] + [4.2, 4.3] + [value + 0.10 for value in future_closes]
    lows = [value - 0.10 for value in pre_closes] + [3.1, 4.0] + [value - 0.10 for value in future_opens]
    closes = pre_closes + [breakout_close, confirm_close] + future_closes
    volumes = pre_volumes + [breakout_volume, confirm_volume] + future_volumes

    frame = pd.DataFrame(
        {
            "symbol": "PASS",
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )
    return frame, str(dates[30].date())


def test_build_first_trigger_backtest_artifacts_returns_entry_levels_and_summary() -> None:
    raw_df, breakout_date = _build_backtest_frame()

    artifacts = build_first_trigger_backtest_artifacts(
        raw_daily_df=raw_df,
        valid_from=breakout_date,
        valid_to=breakout_date,
        criteria=_criteria(),
    )

    assert list(artifacts.summary_df["as_of_date"]) == [breakout_date]
    assert artifacts.summary_df.iloc[0]["symbols_csv"] == "PASS"
    assert artifacts.summary_df.iloc[0]["entry_dates_csv"] == "2026-02-13"
    assert artifacts.summary_df.iloc[0]["entry_prices_csv"] == "4.10"

    trade = artifacts.detail_df.iloc[0]
    assert trade["symbol"] == "PASS"
    assert trade["entry_date"] == "2026-02-13"
    assert trade["entry_price"] == 4.10
    assert trade["stop_price"] == 2.05
    assert trade["exit_reason"] == "hold_50d"
    assert trade["position_notional"] == 1000.0
    assert trade["pnl"] > 0.0

    summary = artifacts.backtest_summary
    assert summary["trade_count"] == 1
    assert summary["start_capital"] == 15000.0
    assert summary["max_open_positions"] == 1
    assert summary["end_equity"] > summary["start_capital"]
