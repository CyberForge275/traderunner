"""Rudometkin MOC strategy-specific pipeline logic.

This module contains the two-stage pipeline implementation for the Rudometkin
Market-On-Close strategy:
1. Daily universe scan and filtering
2. Signal generation and ranking
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from axiom_bt.daily import DailySpec, DailyStore, DailySourceType

try:  # Optional dependency for UI integration
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:  # pragma: no cover - exercised only in UI runtime
    HAS_STREAMLIT = False


def _show_step_message(title: str, message: str, status: str = "info") -> None:
    """Show a step message - streamlit aware when available.

    In non-Streamlit environments this is a no-op to keep the pipeline
    importable and testable without UI dependencies.
    """
    if HAS_STREAMLIT:
        with st.expander(title, expanded=True):
            st.code("(skipped)")
            display = getattr(st, status, st.info)
            display(message)


def _prepare_daily_frame(group: pd.DataFrame, target_tz: str) -> Optional[pd.DataFrame]:
    """Prepare daily OHLCV frame with timezone conversion.
    
    Args:
        group: DataFrame with daily OHLCV data
        target_tz: Target timezone string
        
    Returns:
        Prepared DataFrame or None if data is invalid
    """
    frame = group.rename(columns=str.lower).copy()
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        return None
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"])
    if frame.empty:
        return None
    frame = frame.sort_values("timestamp")
    frame["timestamp"] = frame["timestamp"].dt.tz_convert(target_tz)
    return frame[["timestamp", "open", "high", "low", "close", "volume"]]


def run_daily_scan(
    pipeline,  # PipelineConfig - avoiding import to prevent circular dependency
    max_daily_signals: int = 10,
) -> List[str]:
    """Execute daily universe scan and filtering for Rudometkin strategy.
    
    This function implements Stage 1 of the two-stage Rudometkin pipeline:
    1. Load universe data from parquet file
    2. Filter by date range and symbol constraints
    3. Run strategy signal generation on daily data
    4. Rank and filter signals by score
    5. Return filtered symbol list
    
    Args:
        pipeline: PipelineConfig containing strategy metadata and configuration
        max_daily_signals: Maximum signals per day per direction (long/short)
        
    Returns:
        List of filtered symbol strings to process in Stage 2 (intraday)
    """
    # Import here to avoid circular dependency
    from strategies import factory, registry
    
    _show_step_message("0) Daily Scan", "Starting Stage 1: Daily Universe Scan & Filter")

    strategy_config: Dict[str, Any] = {}
    if pipeline.config_payload and isinstance(pipeline.config_payload, dict):
        strategy_config = dict(pipeline.config_payload.get("strategy_config", {}) or {})
    if not strategy_config and pipeline.strategy.default_strategy_config:
        strategy_config = dict(pipeline.strategy.default_strategy_config)

    universe_path = strategy_config.get("universe_path")
    if not universe_path:
        _show_step_message(
            "0.1) universe",
            "Universe path not configured for Rudometkin strategy.",
            status="error",
        )
        return []
    universe_path = Path(universe_path)

    # Load and normalize universe via central DailyStore
    store = DailyStore(default_tz=pipeline.strategy.timezone or "Europe/Berlin")
    try:
        universe_df = store.load_universe(universe_path=universe_path, tz=pipeline.strategy.timezone)
    except Exception as exc:
        _show_step_message("0.1) Load Universe", f"Failed to load universe: {exc}", status="error")
        return []

    if universe_df.empty:
        _show_step_message("0.1) universe", "Universe parquet is empty.", status="warning")
        return []

    universe_min_ts = universe_df["timestamp"].min()
    universe_max_ts = universe_df["timestamp"].max()
    universe_min_date = universe_min_ts.date()
    universe_max_date = universe_max_ts.date()

    _show_step_message(
        "0.1) universe date range",
        f"Available data: {universe_min_date} to {universe_max_date} ({len(universe_df):,} rows)",
        status="info",
    )

    # Apply date filters with lookback buffer for indicator calculations
    # Rudometkin needs ~200 days for SMA(200), plus buffer for other indicators
    LOOKBACK_DAYS = 300

    if pipeline.fetch.start:
        requested_start = pd.Timestamp(pipeline.fetch.start).date()
        lookback_start_date = requested_start - pd.Timedelta(days=LOOKBACK_DAYS)

        # Sanity check: ensure lookback doesn't exceed available data
        if lookback_start_date < universe_min_date:
            actual_lookback_days = (requested_start - universe_min_date).days
            _show_step_message(
                "0.1) lookback adjustment",
                f"Requested {LOOKBACK_DAYS}-day lookback would go to {lookback_start_date}, "
                f"but universe starts at {universe_min_date}. "
                f"Using {actual_lookback_days} days of available history.",
                status="warning",
            )
            filter_start_date = universe_min_date
        else:
            filter_start_date = lookback_start_date

        before_filter = len(universe_df)
        universe_df = universe_df[universe_df["timestamp"].dt.date >= filter_start_date]
        _show_step_message(
            "0.1) date filter (with lookback)",
            f"Filtered from {filter_start_date} (includes {LOOKBACK_DAYS}-day buffer before {requested_start}); "
            f"rows: {before_filter} → {len(universe_df)}",
            status="info",
        )

    if pipeline.fetch.end:
        end_date = pd.Timestamp(pipeline.fetch.end).date()
        before_end = len(universe_df)
        universe_df = universe_df[universe_df["timestamp"].dt.date <= end_date]
        _show_step_message(
            "0.1) end date filter",
            f"Applied end date {end_date}; rows: {before_end} → {len(universe_df)}",
            status="info",
        )

    requested_symbols = {sym.upper() for sym in pipeline.symbols} if pipeline.symbols else set()
    if requested_symbols:
        before_sym = len(universe_df)
        universe_df = universe_df[universe_df["symbol"].isin(requested_symbols)]
        
        # Show only first 15 symbols to avoid UI slowdown
        symbol_preview = sorted(list(requested_symbols)[:15])
        suffix = f" … and {len(requested_symbols) - 15} more" if len(requested_symbols) > 15 else ""
        
        _show_step_message(
            "0.1) symbol filter",
            f"Filtering to {len(requested_symbols)} requested symbols. "
            f"Preview: {', '.join(symbol_preview)}{suffix}; rows: {before_sym} → {len(universe_df)}",
            status="info",
        )

    available_symbols = set(universe_df["symbol"].unique())
    missing_symbols = sorted((requested_symbols or set()) - available_symbols)
    if missing_symbols:
        preview = ", ".join(missing_symbols[:20])
        suffix = " …" if len(missing_symbols) > 20 else ""
        _show_step_message(
            "0.1) universe coverage",
            f"Missing daily data for {len(missing_symbols)} symbols: {preview}{suffix}",
            status="warning",
        )

    if universe_df.empty:
        _show_step_message(
            "Stage 1 Aborted",
            "No daily data available after filtering universe.",
            status="warning",
        )
        return []

    registry.auto_discover("strategies")
    try:
        rudometkin_strategy = factory.create_strategy(pipeline.strategy.strategy_name, strategy_config)
    except (ValueError, KeyError, ImportError, AttributeError) as exc:
        _show_step_message(
            "0.2) strategy",
            f"Failed to create strategy '{pipeline.strategy.strategy_name}': {type(exc).__name__}: {exc}",
            status="error"
        )
        return []

    signal_rows: List[Dict[str, Any]] = []
    failed_symbols = []
    skipped_symbols = 0  # Track skipped symbols without logging each one
    no_signal_symbols = 0  # Track symbols with no signals

    _show_step_message(
        "0.2) universe summary",
        f"Processing {len(universe_df):,} daily rows across {len(available_symbols)} symbols.",
        status="info",
    )

    for symbol, group in universe_df.groupby("symbol"):
        prepared = _prepare_daily_frame(group, pipeline.strategy.timezone)
        if prepared is None:
            skipped_symbols += 1
            continue
        try:
            signals = rudometkin_strategy.generate_signals(prepared, symbol, strategy_config)
        except (ValueError, KeyError, AttributeError, IndexError) as exc:
            # Log specific errors but continue processing other symbols
            failed_symbols.append(f"{symbol}: {type(exc).__name__}")
            continue
        if not signals:
            no_signal_symbols += 1
            continue
        for sig in signals:
            ts = pd.Timestamp(sig.timestamp)
            if ts.tzinfo is None:
                ts = ts.tz_localize(pipeline.strategy.timezone)
            else:
                ts = ts.tz_convert(pipeline.strategy.timezone)
            record = {
                "ts": ts.isoformat(),
                "Symbol": symbol,
                "long_entry": np.nan,
                "short_entry": np.nan,
                "sl_long": np.nan,
                "sl_short": np.nan,
                "tp_long": np.nan,
                "tp_short": np.nan,
                "setup": sig.metadata.get("setup"),
                "score": sig.metadata.get("score"),
            }
            direction = sig.signal_type.upper()
            if direction == "LONG":
                record["long_entry"] = sig.entry_price
            elif direction == "SHORT":
                record["short_entry"] = sig.entry_price
            signal_rows.append(record)

    # Log summary instead of individual failures
    total_processed = len(available_symbols)
    signals_generated = len(signal_rows)
    
    summary_parts = [
        f"Processed {total_processed} symbols",
        f"Generated {signals_generated} raw signals",
    ]
    if skipped_symbols > 0:
        summary_parts.append(f"Skipped {skipped_symbols} (insufficient data)")
    if no_signal_symbols > 0:
        summary_parts.append(f"{no_signal_symbols} had no signals")
    if failed_symbols:
        summary_parts.append(f"{len(failed_symbols)} failed")
        if len(failed_symbols) <= 10:
            summary_parts.append(f"Failures: {', '.join(failed_symbols)}")
        else:
            summary_parts.append(f"Failures: {', '.join(failed_symbols[:10])} ... and {len(failed_symbols)-10} more")
    
    _show_step_message(
        "0.2) Signal Generation Summary",
        "; ".join(summary_parts),
        status="info" if signals_generated > 0 else "warning"
    )

    columns = [
        "ts",
        "Symbol",
        "long_entry",
        "short_entry",
        "sl_long",
        "sl_short",
        "tp_long",
        "tp_short",
        "setup",
        "score",
    ]

    signals_df = pd.DataFrame(signal_rows, columns=columns)

    # Store per-run signals under artifacts/signals/<run_name>/ for
    # easier inspection from UI-triggered runs, while still updating the
    # strategy's current snapshot CSV for Stage 2 consumers.
    ROOT = Path(__file__).resolve().parents[3]
    run_signals_dir = ROOT / "artifacts" / "signals" / pipeline.run_name
    run_signals_dir.mkdir(parents=True, exist_ok=True)

    signals_dir = pipeline.strategy.orders_source.parent
    signals_dir.mkdir(parents=True, exist_ok=True)

    if signals_df.empty:
        empty_df = pd.DataFrame(columns=columns)
        timestamp_file = run_signals_dir / f"signals_rudometkin_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
        empty_df.to_csv(timestamp_file, index=False)
        empty_df.to_csv(pipeline.strategy.orders_source, index=False)
        _show_step_message(
            "0.3) Filter Signals",
            f"No signals generated. Empty snapshot written to {timestamp_file} and {pipeline.strategy.orders_source}.",
            status="warning",
        )
        return []

    signals_df["ts"] = pd.to_datetime(signals_df["ts"], errors="coerce", utc=True)
    signals_df = signals_df.dropna(subset=["ts"])
    signals_df["score"] = pd.to_numeric(signals_df["score"], errors="coerce")

    # Ensure ts is datetimelike before using .dt accessor to avoid
    # runtime errors with mixed or unexpected types.
    if not pd.api.types.is_datetime64_any_dtype(signals_df["ts"]):
        _show_step_message(
            "0.3) Filter Signals",
            "Signal timestamps are not datetimelike; skipping daily grouping.",
            status="error",
        )
        return []

    signals_df["date"] = signals_df["ts"].dt.date

    # IMPORTANT: Only select daily candidates within the requested
    # trading window. We still use a long lookback for indicator
    # calculations on the underlying OHLCV, but the *signals* considered
    # for Stage 2 (intraday) must be restricted to the UI's
    # start/end dates; otherwise we accumulate candidates across the
    # entire 300-day buffer and effectively revert to full-universe
    # behavior.
    requested_start_date = None
    requested_end_date = None
    if pipeline.fetch.start:
        try:
            requested_start_date = pd.Timestamp(pipeline.fetch.start).date()
        except Exception:
            requested_start_date = None
    if pipeline.fetch.end:
        try:
            requested_end_date = pd.Timestamp(pipeline.fetch.end).date()
        except Exception:
            requested_end_date = None

    before_window = len(signals_df)
    if requested_start_date is not None:
        signals_df = signals_df[signals_df["date"] >= requested_start_date]
    if requested_end_date is not None:
        signals_df = signals_df[signals_df["date"] <= requested_end_date]

    if len(signals_df) != before_window:
        _show_step_message(
            "0.3) Filter Signals Window",
            f"Restricted signals to requested window {requested_start_date} → {requested_end_date}; "
            f"rows: {before_window} → {len(signals_df)}",
            status="info",
        )

    filtered_chunks: List[pd.DataFrame] = []
    daily_details: List[str] = []

    for date, group in signals_df.groupby("date"):
        longs = group[group["long_entry"].notna()].sort_values("score", ascending=False).head(max_daily_signals)
        shorts = group[group["short_entry"].notna()].sort_values("score", ascending=False).head(max_daily_signals)

        long_syms = longs["Symbol"].tolist() if not longs.empty else []
        short_syms = shorts["Symbol"].tolist() if not shorts.empty else []

        if long_syms or short_syms:
            parts = []
            if long_syms:
                parts.append(f"LONG({len(long_syms)}): {', '.join(long_syms)}")
            if short_syms:
                parts.append(f"SHORT({len(short_syms)}): {', '.join(short_syms)}")
            daily_details.append(f"{date}: " + " | ".join(parts))

        if not longs.empty:
            filtered_chunks.append(longs)
        if not shorts.empty:
            filtered_chunks.append(shorts)

    if filtered_chunks:
        filtered_df = pd.concat(filtered_chunks).sort_values(["ts", "Symbol"]).drop(columns=["date"])
    else:
        filtered_df = pd.DataFrame(columns=columns)

    timestamp_file = run_signals_dir / f"signals_rudometkin_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filtered_df.to_csv(timestamp_file, index=False)
    filtered_df.to_csv(pipeline.strategy.orders_source, index=False)

    if filtered_df.empty:
        _show_step_message(
            "0.3) Filter Signals",
            "No signals generated after filtering (after ranking and max_daily_signals caps).",
            status="warning",
        )
        return []

    filtered_symbols = sorted(filtered_df["Symbol"].unique())
    summary_msg = (
        f"Filtered to {len(filtered_df)} signals ({len(filtered_symbols)} unique symbols). "
        f"Max/day={max_daily_signals}\n\n"
    )
    if daily_details:
        # Only show a preview of the first 15 daily candidate lines in
        # the UI to keep the pane readable, while still processing all
        # days internally.
        preview_lines = daily_details[:15]
        if len(daily_details) > 15:
            preview_lines.append(f"… and {len(daily_details) - 15} more days")
        summary_msg += "Daily Candidates (preview):\n" + "\n".join(preview_lines)
    else:
        summary_msg += "No day produced qualifying candidates."
    _show_step_message(
        "0.3) Filter Signals",
        summary_msg + f"\n\nSignals written to {timestamp_file} and {pipeline.strategy.orders_source}",
    )

    return filtered_symbols


# Register hook for central pipeline dispatch when in Streamlit context
# This conditional registration avoids circular imports and runs only when
# the lazy-import from apps/streamlit/pipeline.py executes
try:
    from strategies import strategy_hooks
    strategy_hooks.register_daily_scan("rudometkin_moc", run_daily_scan)
except ImportError:
    # Not running in Streamlit context - hook registration can be skipped
    # (e.g., during unit tests or standalone script execution)
    pass

