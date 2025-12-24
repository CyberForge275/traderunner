"""
Timezone button callbacks
"""
from dash import Input, Output


def register_timezone_callbacks(app):
    """Register callbacks for timezone button states."""

    @app.callback(
        Output("tz-ny-btn", "outline"),
        Output("tz-ny-btn", "color"),
        Output("tz-berlin-btn", "outline"),
        Output("tz-berlin-btn", "color"),
        Input("tz-ny-btn", "n_clicks"),
        Input("tz-berlin-btn", "n_clicks"),
        prevent_initial_call=True
    )
    def toggle_timezone_buttons(ny_clicks, berlin_clicks):
        """Toggle timezone button states."""
        from dash import ctx

        triggered_id = ctx.triggered_id if ctx.triggered else "tz-berlin-btn"

        if triggered_id == "tz-ny-btn":
            # NY active (primary), Berlin outline (secondary)
            return False, "primary", True, "secondary"
        else:
            # Berlin active (primary), NY outline (secondary)
            return True, "secondary", False, "primary"
