"""Quick Period Buttons Callback - Set date ranges automatically."""

from dash import Input, Output, State, callback_context
from dash.exceptions import PreventUpdate
from datetime import datetime, timedelta


def register_period_buttons_callback(app):
    """Register callbacks for Quick Period buttons to auto-set date range.

    Each button (1D, 5D, 1M, 3M, 1Y) updates the date range picker
    to show the appropriate lookback period from today.
    """

    @app.callback(
        Output("backtests-new-daterange", "start_date"),
        Output("backtests-new-daterange", "end_date"),
        Input("period-1d", "n_clicks"),
        Input("period-5d", "n_clicks"),
        Input("period-1mo", "n_clicks"),
        Input("period-3mo", "n_clicks"),
        Input("period-1y", "n_clicks"),
        prevent_initial_call=True
    )
    def update_date_range(n1d, n5d, n1mo, n3mo, n1y):
        """Update date range based on which period button was clicked."""
        from dash import ctx

        if not ctx.triggered:
            raise PreventUpdate

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]

        end_date = datetime.utcnow().date()

        # Map button to days
        period_days = {
            "period-1d": 1,
            "period-5d": 5,
            "period-1mo": 30,
            "period-3mo": 90,
            "period-1y": 365,
        }

        days = period_days.get(button_id, 30)
        start_date = end_date - timedelta(days=days)

        return start_date, end_date
