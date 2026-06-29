from __future__ import annotations

import pandas as pd

from strategies.perlentaucher_daily_scan.impulse_inspection import (
    inspect_impulse_setup,
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


def test_inspect_impulse_setup_combines_features_and_decision() -> None:
    dates = pd.date_range("2025-08-01", periods=35, freq="B", tz="UTC")
    closes = [2.0] * 32 + [2.14, 2.51, 2.48]
    volumes = [200_000.0] * 32 + [226_554.0, 4_444_535.0, 682_845.0]
    daily_df = _build_symbol_frame("AXTI", dates, closes=closes, volumes=volumes)

    out = inspect_impulse_setup(
        daily_df,
        symbol="AXTI",
        breakout_date=str(dates[-2].date()),
        pre_window=30,
        confirm_offset=1,
        trim_top_n=1,
        trim_bottom_n=1,
        min_price_lr_trimmed=-1.0,
        min_vol_lr_trimmed=-1_000_000.0,
        min_price_ratio_prev_to_breakout=1.10,
        min_volume_ratio_prev_to_breakout=3.0,
        min_price_ratio_prev_to_confirm=1.05,
        min_volume_ratio_prev_to_confirm=1.2,
    )

    assert out["symbol"] == "AXTI"
    assert out["breakout_date"] == str(dates[-2].date())
    assert out["trigger_passed"] is True
    assert out["trigger_reason"] == "IMPULSE_CONFIRMED"
    assert out["price_ratio_prev_to_breakout"] > 1.10
    assert out["volume_ratio_prev_to_breakout"] > 3.0
