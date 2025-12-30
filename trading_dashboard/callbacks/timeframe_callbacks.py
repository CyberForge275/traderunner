"""
Timeframe selection callbacks
"""
from dash import Input, Output


def register_timeframe_callbacks(app):
    """Register callbacks for timeframe button selection."""

    @app.callback(
        Output("tf-m1", "active"),
        Output("tf-m1", "outline"),
        Output("tf-m5", "active"),
        Output("tf-m5", "outline"),
        Output("tf-m15", "active"),
        Output("tf-m15", "outline"),
        Output("tf-h1", "active"),
        Output("tf-h1", "outline"),
        Input("tf-m1", "n_clicks"),
        Input("tf-m5", "n_clicks"),
        Input("tf-m15", "n_clicks"),
        Input("tf-h1", "n_clicks"),
        prevent_initial_call=True
    )
    def update_timeframe_buttons(m1_clicks, m5_clicks, m15_clicks, h1_clicks):
        """Update timeframe button states."""
        from dash import ctx

        triggered_id = ctx.triggered_id if ctx.triggered else "tf-m5"

        # Default: all outline except the clicked one
        states = {
            "tf-m1": (False, True),
            "tf-m5": (False, True),
            "tf-m15": (False, True),
            "tf-h1": (False, True)
        }

        # Set the clicked button to active
        if triggered_id in states:
            states[triggered_id] = (True, False)

        return (
            states["tf-m1"][0], states["tf-m1"][1],
            states["tf-m5"][0], states["tf-m5"][1],
            states["tf-m15"][0], states["tf-m15"][1],
            states["tf-h1"][0], states["tf-h1"][1]
        )
