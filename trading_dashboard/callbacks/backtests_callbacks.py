"""Backtests tab callbacks - filtering and detail view."""

from __future__ import annotations

from datetime import datetime
import logging

import pandas as pd
from dash import Input, Output, State, no_update, callback_context
from dash.exceptions import PreventUpdate
from ..config import BACKTESTS_DIR
from ..ui_ids import BT, RUN
from ..components.row_inspector import (
    INSPECT_COL,
    row_to_kv_items,
    row_to_kv_sections_orders,
    render_kv_table,
    render_kv_sections,
    log_open,
    resolve_oco_group,
    derive_long_short_levels,
    resolve_trade_oco_levels,
)
from ..components.signal_chart import (
    build_candlestick_figure,
    compute_bars_window_union,
    compute_trade_chart_window,
    resolve_inspector_timestamps,
    build_marker,
    build_vertical_marker,
    build_level_markers_at_ts,
    build_price_marker,
    infer_mother_ts,
    infer_exit_ts,
    infer_signal_ts,
    log_chart_window,
    load_bars_for_run,
)


def register_backtests_callbacks(app):
    """Register callbacks for the Backtests tab."""

    @app.callback(
        Output(BT.VERSION_PATTERN_HINT, "children"),
        Output(BT.VERSION_PATTERN_HINT, "style"),
        Input(RUN.VERSION_DROPDOWN, "value")
    )
    def validate_version_pattern(new_version):
        """Validate new version input pattern."""
        import re

        if not new_version or not new_version.strip():
            return (
                "Pattern: v#.## (e.g., v1.01, v2.00)",
                {"fontSize": "0.75em", "color": "#888", "marginBottom": "8px"}
            )

        # Pattern: v followed by number, dot, two-digit number
        pattern = r'^v\d+\.\d{2}$'
        if re.match(pattern, new_version.strip()):
            return (
                "✓ Valid version format",
                {"fontSize": "0.75em", "color": "green", "marginBottom": "8px"}
            )
        else:
            return (
                "❌ Invalid format. Use: v#.## (e.g., v1.01, v2.00)",
                {"fontSize": "0.75em", "color": "red", "marginBottom": "8px"}
            )

    @app.callback(
        Output(BT.RUN_DROPDOWN, "value"),
        Input(BT.REFRESH_BUTTON, "n_clicks"),
        State(BT.RUN_DROPDOWN, "value"),
        prevent_initial_call=True,
    )
    def select_latest_on_refresh(n_clicks, current_value):
        """Select latest backtest run when refresh button is clicked."""
        import logging
        logger = logging.getLogger(__name__)

        if n_clicks is None:
            from dash.exceptions import PreventUpdate
            raise PreventUpdate

        from ..repositories.backtests import list_backtests
        from datetime import datetime, timedelta

        # Get runs from last 7 days
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        df = list_backtests(start_date=week_ago, end_date=today)

        if df is None or df.empty:
            logger.warning("🔄 [refresh] No backtests found in last 7 days")
            from dash.exceptions import PreventUpdate
            raise PreventUpdate

        # Get latest run (first in list, already sorted by date desc)
        latest_run = df.iloc[0]["run_name"]
        logger.info(f"🔄 [refresh] Selected latest run: {latest_run}")

        # Return latest run name to update dropdown
        return latest_run


    @app.callback(
        Output(BT.DETAIL_CONTAINER, "children"),
        Input(BT.RUN_DROPDOWN, "value"),
        Input(BT.REFRESH_BUTTON, "n_clicks"),
        prevent_initial_call=False,  # Allow initial render when dropdown has default value
    )
    def update_backtests_detail(run_name, n_clicks):
        import logging
        from pathlib import Path
        logger = logging.getLogger(__name__)

        # Comprehensive logging for evidence/debugging
        logger.info(f"🔍 [backtests_detail] CALLBACK TRIGGERED: run_name={run_name}, n_clicks={n_clicks}")

        from ..services.backtest_details_service import BacktestDetailsService
        from ..repositories.backtests import (
            get_backtest_log,
            get_backtest_metrics,
            get_backtest_strategy_params,
            get_backtest_summary,
            get_backtest_equity,
            get_backtest_orders,
            get_rudometkin_candidates,
        )
        from ..layouts.backtests import create_backtest_detail

        if not run_name:
            logger.info(f"🔍 [backtests_detail] No run_name provided, returning placeholder")
            return create_backtest_detail(None, None, None)

        # Resolve run_dir and check existence
        from pathlib import Path
        run_dir = Path(BACKTESTS_DIR) / run_name
        run_dir_exists = run_dir.exists()
        logger.info(f"🔍 [backtests_detail] run_dir={run_dir}, exists={run_dir_exists}")

        # Helper: Normalize steps to dicts (Dash UI boundary - only JSON-serializable types)
        def _step_to_dict(s):
            """Convert RunStep (dataclass/pydantic) to plain dict for Dash serialization."""
            from dataclasses import asdict, is_dataclass

            if isinstance(s, dict):
                return s
            if is_dataclass(s):
                # Dataclass: convert datetime objects to ISO strings
                d = asdict(s)
                # Convert datetime to string for JSON compatibility
                if 'timestamp' in d and d['timestamp'] is not None:
                    d['timestamp'] = d['timestamp'].isoformat() if hasattr(d['timestamp'], 'isoformat') else str(d['timestamp'])
                # Rename duration_seconds to duration_s for consistency with layout
                if 'duration_seconds' in d:
                    d['duration_s'] = d.pop('duration_seconds')
                return d
            if hasattr(s, "model_dump"):  # pydantic v2
                return s.model_dump()
            if hasattr(s, "dict"):  # pydantic v1
                return s.dict()
            # Fallback: manual extraction
            return {
                "step_index": getattr(s, "step_index", None),
                "step_name": getattr(s, "step_name", ""),
                "status": getattr(s, "status", ""),
                "timestamp": getattr(s, "timestamp", None),
                "details": getattr(s, "details", None),
                "duration_s": getattr(s, "duration_seconds", getattr(s, "duration_s", None)),
            }

        # Try new-pipeline artifacts first
        details_service = BacktestDetailsService()
        details = details_service.load_summary(run_name)
        steps_raw = details_service.load_steps(run_name)

        # Normalize steps to dicts (CRITICAL: Dash requires JSON-serializable data)
        steps = [_step_to_dict(s) for s in (steps_raw or [])]

        # Log what we found
        logger.info(f"📊 [backtests_detail] Loaded details: status={details.status}, source={details.source}, symbols={details.symbols}")
        logger.info(f"📝 [backtests_detail] Loaded {len(steps)} steps from run_steps.jsonl")
        if steps_raw:
            logger.info(f"🧪 [backtests_detail] step_type_raw={type(steps_raw[0]).__name__}, step_type_normalized={type(steps[0]).__name__}")


        # Discover available files
        found_files = []
        if run_dir_exists:
            found_files = [f.name for f in run_dir.iterdir() if f.is_file()]
            logger.info(f"📂 [backtests_detail] Found files in run_dir: {', '.join(found_files[:10])}{'...' if len(found_files) > 10 else ''}")

        # If we have new-pipeline artifacts, use them
        if details.source in ["manifest", "meta+result"]:
            logger.info(f"✅ [backtests_detail] Using new-pipeline artifacts for {run_name}")
            # Create summary dict for create_backtest_detail
            summary = {
                "run_name": run_name,
                "status": details.status.lower(),
                "strategy": details.strategy_key,
                "timeframe": details.requested_tf,
                "symbols": details.symbols,
                "started_at": details.started_at,
                "finished_at": details.finished_at,
                "failure_reason": details.failure_reason,
                "steps": steps,  # Pass steps to detail view
            }

            # Still try to load legacy artifacts if they exist
            # (equity, orders, etc. - still valuable even for new runs)
            log_df = get_backtest_log(run_name)  # May be empty
            metrics = get_backtest_metrics(run_name)
            strategy_params = get_backtest_strategy_params(run_name)
            equity_df = get_backtest_equity(run_name)
            orders = get_backtest_orders(run_name)
            rk_df = get_rudometkin_candidates(run_name)

            # Log artifact counts for evidence
            equity_rows = len(equity_df) if equity_df is not None and not equity_df.empty else 0
            orders_count = len(orders.get("orders", [])) if orders.get("orders") is not None else 0
            logger.info(f"📈 [backtests_detail] Charts/Artifacts: equity_rows={equity_rows}, orders_count={orders_count}, steps_count={len(steps)}")

            return create_backtest_detail(
                run_name,
                log_df,
                metrics,
                strategy_params=strategy_params,
                summary=summary,
                equity_df=equity_df,
                orders_df=orders.get("orders"),
                fills_df=orders.get("fills"),
                trades_df=orders.get("trades"),
                rk_df=rk_df,
            )

        # Fall back to pure legacy if no new artifacts
        logger.info(f"⚠️ [backtests_detail] Falling back to legacy artifacts for {run_name}")
        log_df = get_backtest_log(run_name)
        metrics = get_backtest_metrics(run_name)
        strategy_params = get_backtest_strategy_params(run_name)
        summary = get_backtest_summary(run_name)
        equity_df = get_backtest_equity(run_name)
        orders = get_backtest_orders(run_name)
        rk_df = get_rudometkin_candidates(run_name)

        return create_backtest_detail(
            run_name,
            log_df,
            metrics,
            strategy_params=strategy_params,
            summary=summary,
            equity_df=equity_df,
            orders_df=orders.get("orders"),
            fills_df=orders.get("fills"),
            trades_df=orders.get("trades"),
            rk_df=rk_df,
        )

    @app.callback(
        Output(RUN.EQUITY_BASIS_DROPDOWN, "disabled"),
        Input(RUN.COMPOUND_TOGGLE, "value")
    )
    def toggle_equity_basis(toggle_value):
        """Enable equity basis dropdown only if compound sizing is enabled."""
        # Toggle options is checked if 'enabled' is in list
        is_enabled = "enabled" in (toggle_value or [])
        return not is_enabled  # Disabled if NOT enabled

    @app.callback(
        Output(BT.ORDERS_INSPECT_MODAL, "is_open"),
        Output(BT.ORDERS_INSPECT_TITLE, "children"),
        Output(BT.ORDERS_INSPECT_BODY, "children"),
        Output(BT.ORDERS_INSPECT_CHART, "figure"),
        Input(BT.ORDERS_TABLE, "active_cell"),
        Input(BT.ORDERS_INSPECT_CLOSE, "n_clicks"),
        State(BT.ORDERS_TABLE, "derived_viewport_data"),
        State(BT.ORDERS_TABLE, "data"),
        State(BT.RUN_DROPDOWN, "value"),
        prevent_initial_call=True,
    )
    def open_orders_inspector(active_cell, close_clicks, viewport_rows, all_rows, run_name):
        logger = logging.getLogger(__name__)
        if not callback_context.triggered:
            raise PreventUpdate
        trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == BT.ORDERS_INSPECT_CLOSE:
            return False, no_update, no_update, no_update

        if not active_cell or active_cell.get("column_id") != INSPECT_COL:
            return no_update, no_update, no_update, no_update

        rows = viewport_rows or all_rows or []
        row_index = active_cell.get("row")
        if row_index is None or row_index >= len(rows):
            return no_update, no_update, no_update, no_update

        row = rows[row_index]
        group_rows = resolve_oco_group(all_rows or [], row.get("template_id"))
        sections = row_to_kv_sections_orders(row, group_rows=group_rows)
        oco_group_id = row.get("oco_group_id") or (group_rows[0].get("oco_group_id") if group_rows else "")
        title = f"Order Inspector — {row.get('template_id', '')} (OCO: {oco_group_id})"
        body = render_kv_sections(sections)
        log_open("orders", row.get("template_id"), row.get("symbol"), row.get("signal_ts"))

        fig = build_candlestick_figure(pd.DataFrame())
        if run_name:
            from pathlib import Path
            bars_df = load_bars_for_run(Path(BACKTESTS_DIR) / run_name)
            if not bars_df.empty:
                mother_ts, inside_ts, exit_ts = resolve_inspector_timestamps(row)
                if mother_ts is None:
                    mother_ts = pd.to_datetime(row.get("signal_ts"), utc=True, errors="coerce")
                signal_ts = infer_signal_ts(row)
                if signal_ts is None:
                    logger.warning(
                        "actions: inspector_marker_missing_signal_ts template_id=%s oco_group_id=%s dbg_inside_ts=%s",
                        row.get("template_id"),
                        row.get("oco_group_id"),
                        row.get("dbg_inside_ts"),
                    )
                timestamps = [mother_ts, inside_ts, signal_ts, exit_ts]
                window, meta = compute_bars_window_union(bars_df, timestamps, pre_bars=5, post_bars=5)
                markers = []
                if not window.empty:
                    m = build_marker(window, "mother", mother_ts, "high", "#1f77b4", "triangle-down", "M")
                    if m:
                        markers.append(m)
                    ib = build_marker(window, "inside", inside_ts, "high", "#000000", "triangle-down", "IB")
                    if ib:
                        markers.append(ib)
                    levels = derive_long_short_levels(group_rows or [row])
                    logger.info(
                        "actions: inspector_marker_ts template_id=%s oco_group_id=%s signal_ts=%s dbg_inside_ts=%s chosen_ts=%s",
                        row.get("template_id"),
                        row.get("oco_group_id"),
                        signal_ts,
                        row.get("dbg_inside_ts"),
                        signal_ts,
                    )
                    if signal_ts is not None and pd.notna(signal_ts):
                        markers.extend(build_level_markers_at_ts(signal_ts, levels["long"], levels["short"]))
                        v = build_vertical_marker(signal_ts, label="signal_ts", color="#888888")
                        if v:
                            markers.append(v)
                x_range = None
                if signal_ts is not None and pd.notna(signal_ts) and not window.empty:
                    start_ts = pd.to_datetime(meta.get("start_ts"), utc=True, errors="coerce")
                    end_ts = pd.to_datetime(meta.get("end_ts"), utc=True, errors="coerce")
                    if pd.notna(start_ts) and pd.notna(end_ts):
                        x_min = min(start_ts, signal_ts)
                        x_max = max(end_ts, signal_ts)
                        x_range = (x_min, x_max)
                fig = build_candlestick_figure(window, markers=markers, x_range=x_range)
                start_ts = meta.get("start_ts")
                end_ts = meta.get("end_ts")
                log_chart_window(
                    "orders",
                        row.get("template_id"),
                        row.get("symbol"),
                        mother_ts,
                        exit_ts,
                        pd.to_datetime(start_ts, utc=True, errors="coerce") if start_ts is not None else None,
                        pd.to_datetime(end_ts, utc=True, errors="coerce") if end_ts is not None else None,
                        len(window),
                    )
        return True, title, body, fig

    @app.callback(
        Output(BT.TRADES_INSPECT_MODAL, "is_open"),
        Output(BT.TRADES_INSPECT_TITLE, "children"),
        Output(BT.TRADES_INSPECT_BODY, "children"),
        Output(BT.TRADES_INSPECT_CHART, "figure"),
        Input(BT.TRADES_TABLE, "active_cell"),
        Input(BT.TRADES_INSPECT_CLOSE, "n_clicks"),
        State(BT.TRADES_TABLE, "derived_viewport_data"),
        State(BT.TRADES_TABLE, "data"),
        State(BT.ORDERS_TABLE, "data"),
        State(BT.RUN_DROPDOWN, "value"),
        prevent_initial_call=True,
    )
    def open_trades_inspector(active_cell, close_clicks, viewport_rows, all_rows, orders_rows, run_name):
        if not callback_context.triggered:
            raise PreventUpdate
        trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == BT.TRADES_INSPECT_CLOSE:
            return False, no_update, no_update, no_update

        if not active_cell or active_cell.get("column_id") != INSPECT_COL:
            return no_update, no_update, no_update, no_update

        rows = viewport_rows or all_rows or []
        row_index = active_cell.get("row")
        if row_index is None or row_index >= len(rows):
            return no_update, no_update, no_update, no_update

        row = rows[row_index]
        oco = resolve_trade_oco_levels(row, orders_rows or [])
        signal_ts = oco.get("signal_ts")
        levels = oco.get("levels") or {"long": {}, "short": {}}
        oco_group_id = oco.get("oco_group_id")

        title = f"Trade Inspector — {row.get('template_id', '')} ({row.get('symbol', '')})"
        if oco_group_id:
            title = f"{title} (OCO: {oco_group_id})"

        sections = [
            {
                "title": "Trade",
                "items": [
                    {"key": "template_id", "value": row.get("template_id", "")},
                    {"key": "oco_group_id", "value": oco_group_id or "—"},
                    {"key": "symbol", "value": row.get("symbol", "")},
                    {"key": "side", "value": row.get("side", "")},
                    {"key": "signal_ts", "value": signal_ts or "—"},
                    {"key": "entry_ts", "value": row.get("entry_ts", "")},
                    {"key": "entry_price", "value": row.get("entry_price", "")},
                    {"key": "exit_ts", "value": row.get("exit_ts", "")},
                    {"key": "exit_price", "value": row.get("exit_price", "")},
                    {"key": "exit_reason", "value": row.get("reason", "")},
                ],
            },
            {
                "title": "Levels (OCO)",
                "items": [
                    {"key": "LONG entry", "value": levels.get("long", {}).get("entry") or "—"},
                    {"key": "LONG stop", "value": levels.get("long", {}).get("stop") or "—"},
                    {"key": "LONG tp", "value": levels.get("long", {}).get("tp") or "—"},
                    {"key": "SHORT entry", "value": levels.get("short", {}).get("entry") or "—"},
                    {"key": "SHORT stop", "value": levels.get("short", {}).get("stop") or "—"},
                    {"key": "SHORT tp", "value": levels.get("short", {}).get("tp") or "—"},
                ],
            },
        ]
        if signal_ts is None or pd.isna(signal_ts):
            sections.append(
                {
                    "title": "Warning",
                    "items": [{"key": "signal_ts missing", "value": "OCO level markers skipped"}],
                }
            )
        body = render_kv_sections(sections)
        log_open("trades", row.get("template_id"), row.get("symbol"), row.get("entry_ts"))

        fig = build_candlestick_figure(pd.DataFrame())
        if run_name:
            from pathlib import Path
            bars_df = load_bars_for_run(Path(BACKTESTS_DIR) / run_name)
            if not bars_df.empty:
                mother_ts = None
                inside_ts = None
                if orders_rows and row.get("template_id") is not None:
                    for order_row in orders_rows:
                        if order_row.get("template_id") == row.get("template_id"):
                            mother_ts, inside_ts, _ = resolve_inspector_timestamps(order_row)
                            break
                if mother_ts is None:
                    mother_ts = pd.to_datetime(row.get("entry_ts"), utc=True, errors="coerce")
                exit_ts = pd.to_datetime(row.get("exit_ts"), utc=True, errors="coerce")
                entry_ts = pd.to_datetime(row.get("entry_ts"), utc=True, errors="coerce")
                anchor_ts = signal_ts if signal_ts is not None and not pd.isna(signal_ts) else entry_ts
                window, meta = compute_trade_chart_window(bars_df, anchor_ts, exit_ts, pre_bars=10, post_bars=5)
                markers = []
                if not window.empty:
                    m = build_marker(window, "mother", mother_ts, "high", "#1f77b4", "triangle-down", "M")
                    if m:
                        markers.append(m)
                    ib = build_marker(window, "inside", inside_ts, "high", "#000000", "triangle-down", "IB")
                    if ib:
                        markers.append(ib)
                    if signal_ts is not None and pd.notna(signal_ts):
                        markers.extend(build_level_markers_at_ts(signal_ts, levels["long"], levels["short"]))
                    entry_price = pd.to_numeric(row.get("entry_price"), errors="coerce")
                    exit_price = pd.to_numeric(row.get("exit_price"), errors="coerce")
                    en = build_price_marker(entry_ts, entry_price, "E", "#2ca02c", "triangle-up")
                    if en:
                        markers.append(en)
                    ex_label = f"X ({row.get('reason', '')})" if row.get("reason") else "X"
                    ex = build_price_marker(exit_ts, exit_price, ex_label, "#d62728", "x")
                    if ex:
                        markers.append(ex)
                fig = build_candlestick_figure(window, markers=markers)
                start_ts = meta.get("start_ts")
                end_ts = meta.get("end_ts")
                log_chart_window(
                    "trades",
                        row.get("template_id"),
                        row.get("symbol"),
                        mother_ts,
                        exit_ts,
                        pd.to_datetime(start_ts, utc=True, errors="coerce") if start_ts is not None else None,
                        pd.to_datetime(end_ts, utc=True, errors="coerce") if end_ts is not None else None,
                        len(window),
                    )
                logger = logging.getLogger(__name__)
                logger.info(
                    "actions: trade_inspector_marker_ts template_id=%s oco_group_id=%s signal_ts=%s entry_ts=%s exit_ts=%s exit_reason=%s",
                    row.get("template_id"),
                    oco_group_id,
                    signal_ts,
                    entry_ts,
                    exit_ts,
                    row.get("reason"),
                )
                logger.info(
                    "actions: trade_inspector_window template_id=%s start_idx=%s exit_idx=%s end_idx=%s start_ts=%s end_ts=%s",
                    row.get("template_id"),
                    meta.get("start_idx"),
                    meta.get("exit_idx"),
                    meta.get("end_idx"),
                    start_ts,
                    end_ts,
                )
        return True, title, body, fig
