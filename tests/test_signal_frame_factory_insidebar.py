import pandas as pd

from axiom_bt.pipeline.signal_frame_factory import build_signal_frame


def _bars():
    ts = pd.date_range("2025-01-01 14:00:00", periods=10, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.0] * 10,
            "volume": [100] * 10,
        }
    )

    # Mother bar (idx=1), inside bar (idx=2), breakout (idx=3)
    df.loc[1, ["open", "high", "low", "close"]] = [100.0, 105.0, 95.0, 102.0]
    df.loc[2, ["open", "high", "low", "close"]] = [101.0, 104.0, 96.0, 101.5]
    df.loc[3, ["open", "high", "low", "close"]] = [103.0, 108.0, 102.0, 106.0]
    return df


def test_insidebar_signal_frame_builds():
    bars = _bars()
    params = {
        "symbol": "TEST",
        "timeframe": "M5",
        "timeframe_minutes": 5,
        "inside_bar_definition_mode": "mb_high__ib_high_and_close_in_mb_range",
        "atr_period": 3,
        "min_mother_bar_size": 0.0,
        "min_mother_body_fraction": 0.0,
        "min_inside_body_fraction": 0.0,
        "breakout_confirmation": True,
        "inside_bar_mode": "inclusive",
        "session_timezone": "Europe/Berlin",
        "session_filter": ["15:00-16:00", "16:00-17:00"],
    }
    df, _schema = build_signal_frame(bars, "insidebar_intraday", "1.0.0", params)

    assert not df.empty
    required = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "symbol",
        "timeframe",
        "strategy_id",
        "strategy_version",
        "strategy_tag",
        "atr",
        "inside_bar",
        "mother_high",
        "mother_low",
        "mother_body_fraction",
        "inside_body_fraction",
        "inside_bar_reject_reason",
        "breakout_long",
        "breakout_short",
        "signal_side",
        "signal_reason",
        "entry_price",
        "stop_price",
        "take_profit_price",
        "template_id",
    }
    assert required.issubset(df.columns)
    assert df["timestamp"].dt.tz is not None
    assert (df["symbol"] == "TEST").all()
    assert (df["timeframe"] == "M5").all()
    assert (df["strategy_id"] == "insidebar_intraday").all()
    assert (df["strategy_version"] == "1.0.0").all()
    assert df["atr"].isna().sum() == 0
    assert (df["atr"] >= 0).all()

    signal_rows = df[df["signal_side"].notna()]
    assert len(signal_rows) >= 1
    assert df["stop_price"].notna().any()
    assert df["take_profit_price"].notna().any()
