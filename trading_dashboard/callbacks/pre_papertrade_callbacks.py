"""Pre-PaperTrade Lab callbacks - UI interactions and test execution."""

from __future__ import annotations

from datetime import datetime

from dash import Input, Output, State, ctx
from dash.exceptions import PreventUpdate


def register_pre_papertrade_callbacks(app):
    """Register callbacks for the Pre-PaperTrade Lab tab."""

    @app.callback(
        Output("time-machine-container", "style"),
        Output("mode-description", "children"),
        Input("pre-papertrade-mode", "value"),
    )
    def toggle_time_machine(mode):
        """Toggle Time Machine visibility and update mode description."""
        from dash import html
        
        if mode == "replay":
            return (
                {"display": "block"},
                html.Small(
                    "Time Machine: Replay an entire past trading session using historical data.",
                    className="text-muted",
                ),
            )
        else:  # live
            return (
                {"display": "none"},
                html.Small(
                    "Live mode: Run strategy in real-time during market hours. "
                    "Signals generated from live market data.",
                    className="text-muted",
                ),
            )

    @app.callback(
        Output("pre-papertrade-status", "children"),
        Output("pre-papertrade-status", "color"),
        Output("signals-table", "data"),
        Output("signals-total", "children"),
        Output("signals-buy", "children"),
        Output("signals-sell", "children"),
        Output("pre-papertrade-interval", "disabled"),
        Input("run-pre-papertrade-btn", "n_clicks"),
        Input("clear-signals-btn", "n_clicks"),
        Input("pre-papertrade-interval", "n_intervals"),
        State("pre-papertrade-mode", "value"),
        State("replay-single-date", "date"),
        State("pre-papertrade-strategy", "value"),
        State("pre-papertrade-symbols", "value"),
        State("pre-papertrade-timeframe", "value"),
        State("pre-papertrade-job-status", "data"),
        prevent_initial_call=True,
    )
    def handle_pre_papertrade_actions(
        run_clicks,
        clear_clicks,
        n_intervals,
        mode,
        replay_date,
        strategy,
        symbols_str,
        timeframe,
        job_status,
    ):
        """Handle Start and Clear signals button clicks."""
        from ..services.pre_papertrade_adapter import create_adapter
        from ..repositories.pre_papertrade import get_signals_summary, clear_test_signals

        triggered_id = ctx.triggered_id

        # Clear signals
        if triggered_id == "clear-signals-btn":
            deleted = clear_test_signals()
            return (
                f"✅ Cleared {deleted} signals",
                "success",
                [],
                "0",
                "0",
                "0",
                True,  # Disable interval
            )

        # Run test
        if triggered_id == "run-pre-papertrade-btn":
            # Validate inputs
            if not symbols_str or not symbols_str.strip():
                return (
                    "❌ Please enter at least one symbol",
                    "danger",
                    [],
                    "0",
                    "0",
                    "0",
                    True,
                )

            symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]

            # Create adapter and execute
            adapter = create_adapter()

            try:
                if mode == "live":
                    # Live mode
                    result = adapter.execute_strategy(
                        strategy=strategy,
                        mode="live",
                        symbols=symbols,
                        timeframe=timeframe,
                    )
                else:
                    # Time Machine replay mode
                    result = adapter.execute_strategy(
                        strategy=strategy,
                        mode="replay",
                        symbols=symbols,
                        timeframe=timeframe,
                        replay_date=replay_date,
                    )

                if result["status"] == "completed":
                    signals = result.get("signals", [])
                    
                    # Format signals for table
                    table_data = [
                        {
                            "symbol": s["symbol"],
                            "side": s["side"],
                            "entry_price": f"${s['entry_price']:.2f}",
                            "stop_loss": f"${s['stop_loss']:.2f}" if s.get("stop_loss") else "-",
                            "take_profit": f"${s['take_profit']:.2f}" if s.get("take_profit") else "-",
                            "detected_at": s["detected_at"],
                            "status": "pending",
                        }
                        for s in signals
                    ]

                    buy_count = sum(1 for s in signals if s["side"] == "BUY")
                    sell_count = sum(1 for s in signals if s["side"] == "SELL")

                    mode_label = "🔴 Live" if mode == "live" else "⏰ Time Machine"
                    return (
                        f"{mode_label}: Generated {len(signals)} signals successfully",
                        "success",
                        table_data,
                        str(len(signals)),
                        str(buy_count),
                        str(sell_count),
                        True,  # Disable interval
                    )
                else:
                    error_msg = result.get("error", "Unknown error")
                    return (
                        f"❌ Failed: {error_msg}",
                        "danger",
                        [],
                        "0",
                        "0",
                        "0",
                        True,
                    )

            except Exception as e:
                return (
                    f"❌ Error: {str(e)}",
                    "danger",
                    [],
                    "0",
                    "0",
                    "0",
                    True,
                )

        # Auto-refresh (if enabled)
        if triggered_id == "pre-papertrade-interval":
            # Refresh signal statistics
            df = get_signals_summary(source="pre_papertrade_replay")
            
            if df.empty:
                return (
                    "No signals in database",
                    "info",
                    [],
                    "0",
                    "0",
                    "0",
                    True,
                )

            table_data = df.to_dict("records")
            buy_count = len(df[df["side"] == "BUY"])
            sell_count = len(df[df["side"] == "SELL"])

            return (
                f"Displaying {len(df)} signals",
                "info",
                table_data,
                str(len(df)),
                str(buy_count),
                str(sell_count),
                False,  # Keep interval enabled
            )

        raise PreventUpdate

    @app.callback(
        Output("pre-papertrade-strategy-config", "children"),
        Input("pre-papertrade-strategy", "value"),
    )
    def update_strategy_config(strategy):
        """Update strategy-specific configuration inputs."""
        from dash import dcc, html
        import dash_bootstrap_components as dbc

        if strategy == "inside_bar":
            return [
                dbc.Label("Risk/Reward Ratio:", className="mt-2"),
                dcc.Input(
                    id="inside-bar-rr-ratio",
                    type="number",
                    value=2.0,
                    step=0.1,
                    min=1.0,
                    max=5.0,
                    className="form-control mb-2",
                ),
                dbc.Label("Volume Filter:"),
                dbc.Checklist(
                    id="inside-bar-volume-filter",
                    options=[{"label": "Enable volume filter", "value": True}],
                    value=[True],
                ),
            ]
        elif strategy == "rudometkin_moc":
            return [
                html.P("No additional configuration required", className="text-muted mt-2"),
            ]
        else:
            return []
