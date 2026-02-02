"""Signal inspector chart helpers."""
from __future__ import annotations

from typing import Iterable, Mapping, Optional
import logging
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

_MOTHER_KEYS = ["dbg_mother_ts", "mother_ts", "sig_mother_ts", "dbg_inside_ts", "signal_ts"]
_EXIT_KEYS = ["exit_ts", "dbg_valid_to_ts_utc", "dbg_valid_to_ts"]


def infer_mother_ts(row: Mapping[str, object]) -> Optional[pd.Timestamp]:
    for key in _MOTHER_KEYS:
        if key in row and row.get(key):
            ts = pd.to_datetime(row.get(key), utc=True, errors="coerce")
            if pd.notna(ts):
                return ts
    return None


def infer_exit_ts(row: Mapping[str, object]) -> Optional[pd.Timestamp]:
    for key in _EXIT_KEYS:
        if key in row and row.get(key):
            ts = pd.to_datetime(row.get(key), utc=True, errors="coerce")
            if pd.notna(ts):
                return ts
    return None


def _find_nearest_previous_index(ts_series: pd.Series, target: pd.Timestamp) -> int:
    candidates = ts_series[ts_series <= target]
    if candidates.empty:
        return 0
    return int(candidates.index[-1])


def slice_bars_window_by_count(
    bars_df: pd.DataFrame,
    anchor_ts: pd.Timestamp,
    exit_ts: Optional[pd.Timestamp],
    pre_bars: int = 20,
    post_bars: int = 5,
) -> pd.DataFrame:
    if bars_df.empty:
        return bars_df

    if "timestamp" not in bars_df.columns:
        return pd.DataFrame()

    bars = bars_df.sort_values("timestamp").reset_index(drop=True)
    ts_series = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
    anchor_idx = _find_nearest_previous_index(ts_series, anchor_ts)

    if exit_ts is None:
        exit_idx = anchor_idx
    else:
        exit_idx = _find_nearest_previous_index(ts_series, exit_ts)

    start_idx = max(anchor_idx - pre_bars, 0)
    end_idx = min(exit_idx + post_bars, len(bars) - 1)

    return bars.iloc[start_idx : end_idx + 1].copy()


def build_candlestick_figure(bars_window_df: pd.DataFrame, tz: str = "America/New_York") -> go.Figure:
    fig = go.Figure()
    if bars_window_df.empty:
        fig.update_layout(title="No bars available")
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

    if "timestamp" not in df.columns:
        for col in ["ts", "datetime", "time"]:
            if col in df.columns:
                df = df.rename(columns={col: "timestamp"})
                break
    if "timestamp" not in df.columns:
        return pd.DataFrame()

    return df
