import pandas as pd

from trading_dashboard.components.signal_chart import (
    build_candlestick_figure,
    compute_bars_window,
    compute_bars_window_union,
    resolve_inspector_timestamps,
    build_marker,
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


def test_compute_bars_window_basic():
    bars = _make_bars()
    anchor_ts = bars["timestamp"].iloc[50]
    exit_ts = bars["timestamp"].iloc[70]

    window, meta = compute_bars_window(bars, anchor_ts, exit_ts, pre_bars=20, post_bars=5)

    assert window["timestamp"].iloc[0] == bars["timestamp"].iloc[30]
    assert window["timestamp"].iloc[-1] == bars["timestamp"].iloc[75]
    assert meta["reason"] == "ok"


def test_compute_bars_window_fallback_exit_none():
    bars = _make_bars()
    anchor_ts = bars["timestamp"].iloc[10]

    window, _meta = compute_bars_window(bars, anchor_ts, None, pre_bars=5, post_bars=3)

    assert window["timestamp"].iloc[0] == bars["timestamp"].iloc[5]
    assert window["timestamp"].iloc[-1] == bars["timestamp"].iloc[13]


def test_compute_bars_window_nearest_previous_anchor():
    bars = _make_bars()
    anchor_ts = bars["timestamp"].iloc[20] + pd.Timedelta(seconds=30)
    exit_ts = bars["timestamp"].iloc[22] + pd.Timedelta(seconds=15)

    window, _meta = compute_bars_window(bars, anchor_ts, exit_ts, pre_bars=2, post_bars=1)

    assert window["timestamp"].iloc[0] == bars["timestamp"].iloc[18]
    assert window["timestamp"].iloc[-1] == bars["timestamp"].iloc[23]


def test_resolve_inspector_timestamps_priority():
    row = {
        "dbg_mother_ts": "2025-01-01 14:30:00+00:00",
        "dbg_inside_ts": "2025-01-01 14:35:00+00:00",
        "exit_ts": "2025-01-01 15:00:00+00:00",
    }
    mother_ts, inside_ts, exit_ts = resolve_inspector_timestamps(row)
    assert mother_ts is not None
    assert inside_ts is not None
    assert exit_ts is not None


def test_marker_alignment_non_exact_timestamp_floor_to_previous_bar():
    bars = _make_bars()
    ts_between = bars["timestamp"].iloc[10] + pd.Timedelta(seconds=30)
    window, _meta = compute_bars_window_union(bars, [ts_between], pre_bars=0, post_bars=0)
    marker = build_marker(window, "test", ts_between, "high", "#000000", "triangle-down", "M")
    assert marker is not None
    assert marker["ts"] == bars["timestamp"].iloc[10]


def test_window_includes_all_markers_union_logic():
    bars = _make_bars()
    ts_a = bars["timestamp"].iloc[10]
    ts_b = bars["timestamp"].iloc[40]
    window, _meta = compute_bars_window_union(bars, [ts_a, ts_b], pre_bars=5, post_bars=5)
    assert window["timestamp"].iloc[0] == bars["timestamp"].iloc[5]
    assert window["timestamp"].iloc[-1] == bars["timestamp"].iloc[45]


def test_marker_skip_out_of_dataset_returns_none():
    bars = _make_bars()
    window, _meta = compute_bars_window_union(bars, [bars["timestamp"].iloc[20]], pre_bars=0, post_bars=0)
    ts_outside = bars["timestamp"].iloc[0] - pd.Timedelta(minutes=10)
    marker = build_marker(window, "test", ts_outside, "high", "#000000", "triangle-down", "M")
    assert marker is None


def test_build_candlestick_figure_empty():
    fig = build_candlestick_figure(pd.DataFrame())
    assert fig.layout.title.text == "No bars available"
    assert fig.layout.annotations
