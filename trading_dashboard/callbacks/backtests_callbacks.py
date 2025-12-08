"""Backtests tab callbacks - filtering and detail view."""

from __future__ import annotations

from datetime import datetime

from dash import Input, Output, State


def register_backtests_callbacks(app):
    """Register callbacks for the Backtests tab."""

    @app.callback(
        Output("backtests-table", "data"),
        Input("backtests-date-range", "start_date"),
        Input("backtests-date-range", "end_date"),
        Input("backtests-strategy-filter", "value"),
        Input("backtests-refresh-interval", "n_intervals"),  # NEW: auto-refresh
    )
    def update_backtests_table(start_date, end_date, strategy_value, n_intervals):
        from ..repositories.backtests import list_backtests

        # Convert dates
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date).date()
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date).date()

        strategy = None if strategy_value in (None, "all") else strategy_value

        df = list_backtests(start_date=start_date, end_date=end_date, strategy=strategy)
        if df is None or df.empty:
            return []
        return df.to_dict("records")

    @app.callback(
        Output("backtests-detail", "children"),
        Input("backtests-table", "derived_virtual_data"),
        Input("backtests-table", "selected_rows"),  # Use selected_rows for better scrolling support
        Input("backtests-run-select", "value"),
        Input("backtests-refresh-interval", "n_intervals"),  # Auto-refresh when jobs complete
        prevent_initial_call=False,
    )
    def update_backtests_detail(rows, selected_rows, run_dropdown_value, n_intervals):
        from ..repositories.backtests import (
            get_backtest_log,
            get_backtest_metrics,
            get_backtest_summary,
            get_backtest_equity,
            get_backtest_orders,
            get_rudometkin_candidates,
        )
        from ..layouts.backtests import create_backtest_detail

        # If user explicitly picked a run from the dropdown, use that.
        if run_dropdown_value:
            run_name = run_dropdown_value
        else:
            if not rows:
                return create_backtest_detail(None, None, None)

            # Use the selected row if available
            if selected_rows and len(selected_rows) > 0:
                idx = selected_rows[0]
            else:
                # Default to first row if nothing explicitly selected
                idx = 0

            if idx < 0 or idx >= len(rows):
                return create_backtest_detail(None, None, None)

            row = rows[idx]
            run_name = row.get("run_name")

        if not run_name:
            return create_backtest_detail(None, None, None)
        if not run_name:
            return create_backtest_detail(None, None, None)

        log_df = get_backtest_log(run_name)
        metrics = get_backtest_metrics(run_name)
        summary = get_backtest_summary(run_name)
        equity_df = get_backtest_equity(run_name)
        orders = get_backtest_orders(run_name)
        rk_df = get_rudometkin_candidates(run_name)

        return create_backtest_detail(
            run_name,
            log_df,
            metrics,
            summary=summary,
            equity_df=equity_df,
            orders_df=orders.get("orders"),
            fills_df=orders.get("fills"),
            trades_df=orders.get("trades"),
            rk_df=rk_df,
        )