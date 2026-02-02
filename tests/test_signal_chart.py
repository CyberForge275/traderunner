import pandas as pd

from trading_dashboard.components.signal_chart import (
    slice_bars_window_by_count,
    build_candlestick_figure,
)


def _make_bars(count=100, start="2025-01-01 14:30:00+00:00", freq="1min"):
    ts = pd.date_range(start=start, periods=count, freq=freq, tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": range(count),
            "high": range(count),
            "low": range(count),
            "close": range(count),
        }
    )
    return df


def test_slice_bars_window_by_count_basic():
    bars = _make_bars()
    anchor_ts = bars["timestamp"].iloc[50]
    exit_ts = bars["timestamp"].iloc[70]

    window = slice_bars_window_by_count(bars, anchor_ts, exit_ts, pre_bars=20, post_bars=5)

    assert window["timestamp"].iloc[0] == bars["timestamp"].iloc[30]
    assert window["timestamp"].iloc[-1] == bars["timestamp"].iloc[75]


def test_slice_bars_window_fallback_exit_none():
    bars = _make_bars()
    anchor_ts = bars["timestamp"].iloc[10]

    window = slice_bars_window_by_count(bars, anchor_ts, None, pre_bars=5, post_bars=3)

    assert window["timestamp"].iloc[0] == bars["timestamp"].iloc[5]
    assert window["timestamp"].iloc[-1] == bars["timestamp"].iloc[13]


def test_slice_bars_window_nearest_previous_anchor():
    bars = _make_bars()
    anchor_ts = bars["timestamp"].iloc[20] + pd.Timedelta(seconds=30)
    exit_ts = bars["timestamp"].iloc[22] + pd.Timedelta(seconds=15)

    window = slice_bars_window_by_count(bars, anchor_ts, exit_ts, pre_bars=2, post_bars=1)

    assert window["timestamp"].iloc[0] == bars["timestamp"].iloc[18]
    assert window["timestamp"].iloc[-1] == bars["timestamp"].iloc[23]


def test_build_candlestick_figure_empty():
    fig = build_candlestick_figure(pd.DataFrame())
    assert fig.layout.title.text == "No bars available"
