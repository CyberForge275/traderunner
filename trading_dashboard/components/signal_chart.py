"""Signal inspector chart helpers."""
from __future__ import annotations

from typing import Iterable, Mapping, Optional, Tuple
import logging
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

_MOTHER_KEYS = ["dbg_mother_ts", "sig_mother_ts", "mother_ts"]
_INSIDE_KEYS = ["dbg_inside_ts", "sig_inside_ts", "inside_ts"]
_EXIT_KEYS = ["exit_ts", "dbg_valid_to_ts_utc", "dbg_exit_ts_utc", "dbg_valid_to_ts"]


def _coerce_ts(value: object) -> Optional[pd.Timestamp]:
    if value is None or value == "":
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    return ts if pd.notna(ts) else None


def infer_mother_ts(row: Mapping[str, object]) -> Optional[pd.Timestamp]:
    for key in _MOTHER_KEYS:
        if key in row and row.get(key):
            ts = _coerce_ts(row.get(key))
            if ts is not None:
                return ts
    return None


def infer_inside_ts(row: Mapping[str, object]) -> Optional[pd.Timestamp]:
    for key in _INSIDE_KEYS:
        if key in row and row.get(key):
            ts = _coerce_ts(row.get(key))
            if ts is not None:
                return ts
    return None


def infer_exit_ts(row: Mapping[str, object]) -> Optional[pd.Timestamp]:
    for key in _EXIT_KEYS:
        if key in row and row.get(key):
            ts = _coerce_ts(row.get(key))
            if ts is not None:
                return ts
    return None


def _find_nearest_previous_index(ts_series: pd.Series, target: pd.Timestamp) -> int:
    candidates = ts_series[ts_series <= target]
    if candidates.empty:
        return 0
    return int(candidates.index[-1])


def _find_nearest_previous_row(
    bars: pd.DataFrame, target: pd.Timestamp
) -> Optional[pd.Series]:
    if bars.empty or "timestamp" not in bars.columns:
        return None
    ts_series = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
    idx = _find_nearest_previous_index(ts_series, target)
    if idx < 0 or idx >= len(bars):
        return None
    return bars.iloc[idx]


def resolve_marker_price(
    bars_window_df: pd.DataFrame,
    ts: Optional[pd.Timestamp],
    price_col: str = "high",
) -> Optional[float]:
    if ts is None or bars_window_df.empty or price_col not in bars_window_df.columns:
        return None
    row = _find_nearest_previous_row(bars_window_df, ts)
    if row is None:
        return None
    try:
        return float(row[price_col])
    except Exception:
        return None


def align_marker_ts(bars_window_df: pd.DataFrame, ts: Optional[pd.Timestamp]) -> Optional[pd.Timestamp]:
    """Align a marker timestamp to nearest previous bar in the current window."""
    if ts is None or bars_window_df.empty or "timestamp" not in bars_window_df.columns:
        return None
    row = _find_nearest_previous_row(bars_window_df, ts)
    if row is None:
        return None
    try:
        return pd.to_datetime(row["timestamp"], utc=True, errors="coerce")
    except Exception:
        return None


def resolve_inspector_timestamps(row: Mapping[str, object]) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """Resolve mother/inside/exit timestamps with stable priority for inspector."""
    mother_ts = infer_mother_ts(row)
    inside_ts = infer_inside_ts(row)
    exit_ts = infer_exit_ts(row)
    return mother_ts, inside_ts, exit_ts


def compute_bars_window(
    bars_df: pd.DataFrame,
    mother_ts: pd.Timestamp,
    exit_ts: Optional[pd.Timestamp],
    pre_bars: int = 5,
    post_bars: int = 5,
) -> Tuple[pd.DataFrame, dict]:
    if bars_df.empty:
        return bars_df, {"reason": "empty_bars_df"}

    if "timestamp" not in bars_df.columns:
        return pd.DataFrame(), {"reason": "missing_timestamp_col"}

    bars = bars_df.sort_values("timestamp").reset_index(drop=True)
    ts_series = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
    anchor_idx = _find_nearest_previous_index(ts_series, mother_ts)

    if exit_ts is None:
        exit_idx = anchor_idx
    else:
        exit_idx = _find_nearest_previous_index(ts_series, exit_ts)

    start_idx = max(anchor_idx - pre_bars, 0)
    end_idx = min(exit_idx + post_bars, len(bars) - 1)

    window = bars.iloc[start_idx : end_idx + 1].copy()
    meta = {
        "reason": "ok",
        "anchor_idx": anchor_idx,
        "exit_idx": exit_idx,
        "start_ts": window["timestamp"].iloc[0] if not window.empty else None,
        "end_ts": window["timestamp"].iloc[-1] if not window.empty else None,
    }
    return window, meta


def build_candlestick_figure(
    bars_window_df: pd.DataFrame,
    tz: str = "America/New_York",
    markers: Optional[Iterable[dict]] = None,
) -> go.Figure:
    fig = go.Figure()
    if bars_window_df.empty:
        fig.update_layout(
            title="No bars available",
            xaxis={"visible": False},
            yaxis={"visible": False},
            annotations=[
                {
                    "text": "No bars available for this window",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                }
            ],
        )
        return fig

    ts = pd.to_datetime(bars_window_df["timestamp"], utc=True, errors="coerce")
    ts_local = ts.dt.tz_convert(tz)

    fig.add_trace(
        go.Candlestick(
            x=ts_local,
            open=bars_window_df["open"],
            high=bars_window_df["high"],
            low=bars_window_df["low"],
            close=bars_window_df["close"],
            name="price",
        )
    )
    if markers:
        for marker in markers:
            marker_ts = _coerce_ts(marker.get("ts"))
            if marker_ts is None:
                continue
            marker_ts_local = marker_ts.tz_convert(tz)
            fig.add_trace(
                go.Scatter(
                    x=[marker_ts_local],
                    y=[marker.get("price")],
                    mode="markers+text",
                    text=[marker.get("label", "")],
                    textposition="top center",
                    marker=dict(size=10, symbol=marker.get("symbol", "triangle-up"), color=marker.get("color", "#FF8800")),
                    name=marker.get("label", ""),
                )
            )
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title=f"Time ({tz})",
        yaxis_title="Price",
        height=420,
    )
    return fig


def log_chart_window(kind: str, template_id: object, symbol: object, anchor_ts: Optional[pd.Timestamp],
                     exit_ts: Optional[pd.Timestamp], start_ts: Optional[pd.Timestamp],
                     end_ts: Optional[pd.Timestamp], bars_count: int) -> None:
    logger.info(
        "actions: inspector_chart_window table=%s template_id=%s symbol=%s anchor_ts=%s exit_ts=%s start_ts=%s end_ts=%s bars=%s",
        kind,
        template_id,
        symbol,
        anchor_ts,
        exit_ts,
        start_ts,
        end_ts,
        bars_count,
    )


def load_bars_for_run(run_dir: Path) -> pd.DataFrame:
    bars_dir = run_dir / "bars"
    if not bars_dir.exists():
        return pd.DataFrame()

    candidates = list(bars_dir.glob("*.parquet")) + list(bars_dir.glob("*.csv"))
    if not candidates:
        return pd.DataFrame()

    parquet = [p for p in candidates if p.suffix == ".parquet"]
    csvs = [p for p in candidates if p.suffix == ".csv"]

    pick = None
    for p in parquet:
        if "bars_exec" in p.name:
            pick = p
            break
    if pick is None:
        for p in parquet:
            if "bars_signal" in p.name:
                pick = p
                break
    if pick is None and parquet:
        pick = parquet[0]
    if pick is None:
        pick = csvs[0]

    if pick.suffix == ".parquet":
        df = pd.read_parquet(pick)
    else:
        df = pd.read_csv(pick)

    df = df.rename(columns={c: c.lower() for c in df.columns})
    if "timestamp" not in df.columns:
        for col in ["ts", "datetime", "time"]:
            if col in df.columns:
                df = df.rename(columns={col: "timestamp"})
                break
    if "timestamp" not in df.columns:
        try:
            idx = pd.to_datetime(df.index, utc=True, errors="coerce")
            df = df.reset_index().rename(columns={"index": "timestamp"})
            df["timestamp"] = idx
        except Exception:
            return pd.DataFrame()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            return pd.DataFrame()

    return df
