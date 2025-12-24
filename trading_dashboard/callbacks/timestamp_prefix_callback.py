"""Callback to update timestamp prefix for run name."""

from dash import Input, Output
from datetime import datetime


def register_timestamp_prefix_callback(app):
    """Register callback to update timestamp prefix when strategy changes."""
    
    @app.callback(
        Output("run-name-timestamp-prefix", "children"),
        Input("backtests-new-strategy", "value"),
        prevent_initial_call=False  # Run on page load
    )
    def update_timestamp_prefix(strategy):
        """Update timestamp prefix with current time."""
        # Generate current timestamp
        now = datetime.now()
        timestamp = now.strftime("%y%m%d_%H%M%S")  # Format: YYMMDD_HHMMSS
        
        # Always show timestamp with underscore, ready for user input
        return f"{timestamp}_"
