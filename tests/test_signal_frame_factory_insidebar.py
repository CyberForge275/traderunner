import pandas as pd

from axiom_bt.pipeline.signal_frame_factory import build_signal_frame


def _bars():
    ts = pd.date_range("2025-01-01", periods=10, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": range(10),
            "high": [v + 0.5 for v in range(10)],
            "low": [v - 0.5 for v in range(10)],
            "close": [v + 0.1 for v in range(10)],
            "volume": [100] * 10,
        }
    )


def test_insidebar_signal_frame_builds():
    bars = _bars()
    params = {"symbol": "TEST", "timeframe": "M5"}
    df = build_signal_frame(bars, "insidebar_intraday", "1.0.0", params)

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
