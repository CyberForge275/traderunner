"""Signal inspector chart helpers."""
from __future__ import annotations

from typing import Iterable, Mapping, Optional, Tuple, Sequence
import logging
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

_MOTHER_KEYS = ["dbg_mother_ts", "sig_mother_ts", "mother_ts"]
_INSIDE_KEYS = ["dbg_inside_ts", "sig_inside_ts", "inside_ts"]
_EXIT_KEYS = ["order_valid_to_ts", "exit_ts", "dbg_valid_to_ts_utc", "dbg_exit_ts_utc", "dbg_valid_to_ts"]
_SIGNAL_KEYS = ["signal_ts", "dbg_trigger_ts"]


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


def infer_signal_ts(row: Mapping[str, object]) -> Optional[pd.Timestamp]:
    for key in _SIGNAL_KEYS:
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
    ts_series = ts_series.reset_index(drop=True)
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


def _align_ts_to_bars(
    bars_df: pd.DataFrame, ts: Optional[pd.Timestamp]
) -> Tuple[Optional[pd.Timestamp], str]:
    if ts is None:
        return None, "parse_failed"
    if bars_df.empty or "timestamp" not in bars_df.columns:
        return None, "no_bars"
    ts_series = pd.to_datetime(bars_df["timestamp"], utc=True, errors="coerce")
    ts_series = ts_series.dropna()
    if ts_series.empty:
        return None, "no_bars"
    if ts < ts_series.min() or ts > ts_series.max():
        return None, "out_of_dataset"
    idx = _find_nearest_previous_index(ts_series, ts)
    if idx < 0 or idx >= len(ts_series):
        return None, "out_of_dataset"
    return pd.to_datetime(ts_series.iloc[idx], utc=True, errors="coerce"), "ok"


def compute_bars_window_union(
    bars_df: pd.DataFrame,
    timestamps: Sequence[Optional[pd.Timestamp]],
    pre_bars: int = 5,
    post_bars: int = 5,
) -> Tuple[pd.DataFrame, dict]:
    if bars_df.empty:
        return bars_df, {"reason": "empty_bars_df"}
    if "timestamp" not in bars_df.columns:
        return pd.DataFrame(), {"reason": "missing_timestamp_col"}
    bars = bars_df.sort_values("timestamp").reset_index(drop=True)
    ts_series = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
    aligned = []
    for ts in timestamps:
        aligned_ts, reason = _align_ts_to_bars(bars, ts)
        if aligned_ts is not None:
            aligned.append(aligned_ts)
        else:
            logger.info(
                "actions: inspector_marker_skip reason=%s wanted_ts=%s",
                reason,
                ts,
            )
    if not aligned:
        return pd.DataFrame(), {"reason": "no_aligned_timestamps"}
    min_ts = min(aligned)
    max_ts = max(aligned)
    start_idx = _find_nearest_previous_index(ts_series, min_ts)
    end_idx = _find_nearest_previous_index(ts_series, max_ts)
    start_idx = max(start_idx - pre_bars, 0)
    end_idx = min(end_idx + post_bars, len(bars) - 1)
    window = bars.iloc[start_idx : end_idx + 1].copy()
    meta = {
        "reason": "ok",
        "start_ts": window["timestamp"].iloc[0] if not window.empty else None,
        "end_ts": window["timestamp"].iloc[-1] if not window.empty else None,
    }
    return window, meta


def compute_trade_chart_window(
    bars_df: pd.DataFrame,
    anchor_ts: Optional[pd.Timestamp],
    exit_ts: Optional[pd.Timestamp],
    pre_bars: int = 10,
    post_bars: int = 5,
) -> Tuple[pd.DataFrame, dict]:
    if bars_df.empty or "timestamp" not in bars_df.columns:
        return pd.DataFrame(), {"reason": "empty_bars_df"}
    if anchor_ts is None:
        return pd.DataFrame(), {"reason": "missing_anchor_ts"}

    bars = bars_df.sort_values("timestamp").reset_index(drop=True)
    ts_series = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
    if ts_series.isna().all():
        return pd.DataFrame(), {"reason": "missing_timestamp_col"}

    anchor_idx = int(ts_series.searchsorted(anchor_ts, side="left"))
    anchor_idx = max(min(anchor_idx, len(bars) - 1), 0)
    start_idx = max(anchor_idx - pre_bars, 0)

    if exit_ts is not None and not pd.isna(exit_ts):
        exit_idx = int(ts_series.searchsorted(exit_ts, side="left"))
        exit_idx = max(min(exit_idx, len(bars) - 1), 0)
    else:
        exit_idx = anchor_idx

    end_idx = min(exit_idx + post_bars, len(bars) - 1)
    window = bars.iloc[start_idx : end_idx + 1].copy()

    meta = {
        "reason": "ok",
        "start_idx": start_idx,
        "exit_idx": exit_idx,
        "end_idx": end_idx,
        "start_ts": window["timestamp"].iloc[0] if not window.empty else None,
        "end_ts": window["timestamp"].iloc[-1] if not window.empty else None,
    }
    return window, meta


def build_marker(
    bars_window_df: pd.DataFrame,
    key: str,
    wanted_ts: Optional[pd.Timestamp],
    price_col: str,
    color: str,
    symbol: str,
    label: str,
) -> Optional[dict]:
    if wanted_ts is None:
        logger.info("actions: inspector_marker key=%s reason=parse_failed", key)
        return None
    if bars_window_df.empty or "timestamp" not in bars_window_df.columns:
        logger.info("actions: inspector_marker key=%s reason=no_window", key)
        return None
    ts_series = pd.to_datetime(bars_window_df["timestamp"], utc=True, errors="coerce")
    window_min = ts_series.iloc[0]
    window_max = ts_series.iloc[-1]
    if pd.isna(window_min) or pd.isna(window_max):
        logger.info("actions: inspector_marker key=%s reason=window_ts_invalid", key)
        return None
    if len(ts_series) <= 1:
        tolerance = None
    else:
        deltas = ts_series.diff().dropna()
        tolerance = deltas.median() if not deltas.empty else pd.Timedelta(0)
    if wanted_ts < window_min or (tolerance is not None and wanted_ts > window_max + tolerance):
        logger.info(
            "actions: inspector_marker key=%s reason=out_of_window wanted_ts=%s window_min=%s window_max=%s",
            key,
            wanted_ts,
            window_min,
            window_max,
        )
        return None
    aligned_ts = align_marker_ts(bars_window_df, wanted_ts)
    if aligned_ts is None:
        logger.info(
            "actions: inspector_marker key=%s reason=not_in_window wanted_ts=%s",
            key,
            wanted_ts,
        )
        return None
    price = resolve_marker_price(bars_window_df, aligned_ts, price_col)
    if price is None or pd.isna(price):
        logger.info(
            "actions: inspector_marker key=%s reason=no_price aligned_ts=%s",
            key,
            aligned_ts,
        )
        return None
    window_high = pd.to_numeric(bars_window_df["high"], errors="coerce").max()
    window_low = pd.to_numeric(bars_window_df["low"], errors="coerce").min()
    span = float(window_high - window_low) if pd.notna(window_high) and pd.notna(window_low) else 0.0
    offset = span * 0.02
    y = price + offset if price_col == "high" else price - offset
    logger.info(
        "actions: inspector_marker key=%s wanted_ts=%s aligned_ts=%s y=%s window_min=%s window_max=%s",
        key,
        wanted_ts,
        aligned_ts,
        y,
        bars_window_df["timestamp"].iloc[0] if not bars_window_df.empty else None,
        bars_window_df["timestamp"].iloc[-1] if not bars_window_df.empty else None,
    )
    return {"ts": aligned_ts, "price": y, "label": label, "symbol": symbol, "color": color}


def build_price_marker(
    ts: Optional[pd.Timestamp],
    price: Optional[float],
    label: str,
    color: str,
    symbol: str,
) -> Optional[dict]:
    if ts is None or price is None or pd.isna(ts) or pd.isna(price):
        return None
    return {"ts": ts, "price": float(price), "label": label, "symbol": symbol, "color": color}


def build_vertical_marker(
    ts: Optional[pd.Timestamp],
    *,
    label: str,
    color: str,
) -> Optional[dict]:
    if ts is None or pd.isna(ts):
        return None
    return {"ts": ts, "label": label, "color": color, "mode": "vertical"}


def build_level_markers_at_ts(
    signal_ts: Optional[pd.Timestamp],
    long_levels: Mapping[str, object],
    short_levels: Mapping[str, object],
    *,
    long_color: str = "#2ca02c",
    short_color: str = "#d62728",
) -> list[dict]:
    """Build entry/stop/tp markers for LONG/SHORT at a fixed signal timestamp."""
    markers: list[dict] = []
    if signal_ts is None or pd.isna(signal_ts):
        logger.info("actions: inspector_level_markers reason=missing_signal_ts")
        return markers

    ts_long = signal_ts + pd.Timedelta(seconds=15)
    ts_short = signal_ts - pd.Timedelta(seconds=15)

    def _add(ts: pd.Timestamp, price: object, label: str, color: str, symbol: str) -> None:
        if price is None or (isinstance(price, float) and pd.isna(price)):
            return
        markers.append({"ts": ts, "price": float(price), "label": label, "symbol": symbol, "color": color})

    _add(ts_long, long_levels.get("entry"), "L entry", long_color, "triangle-up")
    _add(ts_long, long_levels.get("stop"), "L stop", long_color, "triangle-down")
    _add(ts_long, long_levels.get("tp"), "L tp", long_color, "diamond")

    _add(ts_short, short_levels.get("entry"), "S entry", short_color, "triangle-up")
    _add(ts_short, short_levels.get("stop"), "S stop", short_color, "triangle-down")
    _add(ts_short, short_levels.get("tp"), "S tp", short_color, "diamond")

    logger.info(
        "actions: inspector_level_markers signal_ts=%s long=%s short=%s",
        signal_ts,
        {k: long_levels.get(k) for k in ("entry", "stop", "tp")},
        {k: short_levels.get(k) for k in ("entry", "stop", "tp")},
    )
    return markers


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
    *,
    x_range: Optional[Tuple[pd.Timestamp, pd.Timestamp]] = None,
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
            if marker.get("mode") == "vertical":
                fig.add_trace(
                    go.Scatter(
                        x=[marker_ts_local, marker_ts_local],
                        y=[bars_window_df["low"].min(), bars_window_df["high"].max()],
                        mode="lines+text",
                        line=dict(color=marker.get("color", "#AAAAAA"), width=1, dash="dot"),
                        text=[marker.get("label", "")],
                        textposition="top center",
                        name=marker.get("label", ""),
                        showlegend=False,
                    )
                )
                continue
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
    if x_range and all(x_range):
        x0, x1 = x_range
        fig.update_xaxes(range=[x0.tz_convert(tz), x1.tz_convert(tz)])
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
