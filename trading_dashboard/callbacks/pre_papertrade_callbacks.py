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
        Output("strategy-description", "children"),
        Input("pre-papertrade-strategy", "value"),
    )
    def update_strategy_description(strategy):
        """Update strategy description when selection changes."""
        from dash import html
        
        # Hardcoded strategy descriptions (avoid import issues)
        strategy_descriptions = {
            "insidebar_intraday": "Inside Bar Intraday - Pattern breakout strategy (V1)",
            "insidebar_intraday_v2": "Inside Bar Intraday v2 - Enhanced pattern breakout with strict filtering (V2)",
            "rudometkin_moc_mode": "Rudometkin MOC - Market-On-Close mean reversion system",
        }
        
        if not strategy:
            return html.Small("Select a strategy", className="text-muted")
        
        description = strategy_descriptions.get(strategy, "Unknown strategy")
        return html.Small(description, className="text-muted")

    @app.callback(
        Output("past-runs-dropdown", "options"),
        Input("pre-papertrade-status", "children"),  # Trigger on page load
    )
    def load_past_runs(_):
        """Load list of past Pre-PaperTrade test runs."""
        from ..repositories.pre_papertrade import get_past_runs
        
        try:
            past_runs = get_past_runs()
            options = [
                {
                    "label": f"{run['timestamp']} - {run['strategy']} ({run['signals_count']} signals)",
                    "value": run['id']
                }
                for run in past_runs
            ]
            return options
        except Exception:
            return []

    @app.callback(
        [
            Output("pre-papertrade-status", "children"),
            Output("pre-papertrade-status", "color"),
            Output("signals-table", "data"),
            Output("signals-total", "children"),
            Output("signals-buy", "children"),
            Output("signals-sell", "children"),
            Output("pre-papertrade-interval", "disabled"),
        ],
        [
            Input("run-pre-papertrade-btn", "n_clicks"),
            Input("clear-signals-btn", "n_clicks"),
            Input("pre-papertrade-interval", "n_intervals"),
        ],
        [
            State("pre-papertrade-mode", "value"),
            State("replay-single-date", "date"),
            State("pre-papertrade-strategy", "value"),
            State("pre-papertrade-symbols", "value"),
            State("pre-papertrade-timeframe", "value"),
            State("session-filter-input", "value"),  # NEW
            State("pre-papertrade-job-status", "data"),
        ],
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
        session_filter_input,  # NEW
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
            # Parse combined strategy|version value
            strategy_name = strategy
            version = None
            
            if strategy and "|" in strategy:
                # Format: "strategy_id|version"
                parts = strategy.split("|", 1)
                strategy_name = parts[0]
                version = parts[1]
            
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
            # Parse symbols
            symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]

            # Execute strategy
            try:
                with create_adapter() as adapter:
                    # NEW: Parse session filter from UI input
                    config_params = {}
                    if session_filter_input and session_filter_input.strip():
                        try:
                            from dash import html
                            from src.strategies.inside_bar.config import SessionFilter
                            session_strings = [s.strip() for s in session_filter_input.split(",") if s.strip()]
                            session_filter = SessionFilter.from_strings(session_strings)
                            config_params["session_filter"] = session_filter
                        except Exception as e:
                            from dash import html
                            return (
                                [
                                    html.H4("❌ Invalid Session Filter", className="text-danger"),
                                    html.P(f"Error: {str(e)}"),
                                    html.P("Format: HH:MM-HH:MM or HH:MM-HH:MM,HH:MM-HH:MM (e.g., 15:00-16:00,16:00-17:00)"),
                                ],
                                "danger",
                                [],
                                "0",
                                "0",
                                "0",
                                True,  # Disable interval
                            )
                    
                    if mode == "live":
                        # Live mode
                        result = adapter.execute_strategy(
                            strategy=strategy_name,
                            version=version,  # NEW: Pass version
                            mode="live",
                            symbols=symbols,
                            timeframe=timeframe,
                            config_params=config_params if config_params else None,  # NEW
                        )
                    else:
                        # Time Machine replay mode
                        result = adapter.execute_strategy(
                            strategy=strategy_name,
                            version=version,  # NEW: Pass version
                            mode="replay",
                            symbols=symbols,
                            timeframe=timeframe,
                            replay_date=replay_date,
                            config_params=config_params if config_params else None,  # NEW
                        )

                    if result["status"] == "completed":
                        signals = result.get("signals", [])
                        
                        # Format signals for table
                        table_data = [
                            {
                                "symbol": s["symbol"],
                                "side": s["side"],
                                "entry_price": f"{s['entry_price']:.2f}",
                                "stop_loss": f"{s['stop_loss']:.2f}",
                                "take_profit": f"{s['take_profit']:.2f}",
                                "detected_at": s["timestamp"],
                                "status": "Pending",
                            }
                            for s in signals
                        ]
                        
                        # Count by side
                        buy_count = sum(1 for s in signals if s["side"] == "BUY")
                        sell_count = sum(1 for s in signals if s["side"] == "SELL")
                        
                        return (
                            f"✅ Completed: {len(signals)} signals generated",
                            "success",
                            table_data,
                            str(len(signals)),
                            str(buy_count),
                            str(sell_count),
                            True,
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
