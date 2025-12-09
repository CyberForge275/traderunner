"""Backtests tab callbacks - filtering and detail view."""

from __future__ import annotations

from datetime import datetime

from dash import Input, Output, State


def register_backtests_callbacks(app):
    """Register callbacks for the Backtests tab."""

    @app.callback(
        Output("version-pattern-hint", "children"),
        Output("version-pattern-hint", "style"),
        Input("backtests-new-version", "value")
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
        Output("backtests-detail", "children"),
        Input("backtests-run-dropdown", "value"),
        Input("backtests-refresh-interval", "n_intervals"),
        prevent_initial_call=True,  # Changed to True for proper dropdown behavior
    )
    def update_backtests_detail(run_name, n_intervals):
        from ..repositories.backtests import (
            get_backtest_log,
            get_backtest_metrics,
            get_backtest_summary,
            get_backtest_equity,
            get_backtest_orders,
            get_rudometkin_candidates,
        )
        from ..layouts.backtests import create_backtest_detail

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