"""Date Selection Callback - Handle date selection mode switching and calculation."""

from dash import Input, Output, State, html
from datetime import datetime, timedelta


def register_date_selection_callback(app):
    """Register callbacks for date selection UI.
    
    Handles:
    1. Show/hide containers based on selection mode
    2. Calculate and display data window
    3. Update Quick Period buttons for days back mode
    """
    
    # Toggle visibility based on mode
    @app.callback(
        Output("anchor-date-container", "style"),
        Output("days-back-container", "style"),
        Output("explicit-range-container", "style"),
        Input("date-selection-mode", "value"),
    )
    def toggle_date_mode(mode):
        """Show/hide input fields based on selected mode."""
        if mode == "days_back":
            return {"display": "block"}, {"display": "block"}, {"display": "none"}
        else:  # explicit
            return {"display": "none"}, {"display": "none"}, {"display": "block"}
    
    # Calculate and display data window
    @app.callback(
        Output("data-window-display", "children"),
        Input("date-selection-mode", "value"),
        Input("anchor-date", "date"),
        Input("days-back", "value"),
        Input("explicit-start-date", "date"),
        Input("explicit-end-date", "date"),
    )
    def update_data_window(mode, anchor_date, days_back, start_date, end_date):
        """Calculate and display the effective data window."""
        if mode == "days_back":
            if not anchor_date or not days_back:
                return "Set anchor date and days back"
            
            # Parse anchor date
            if isinstance(anchor_date, str):
                anchor = datetime.fromisoformat(anchor_date).date()
            else:
                anchor = anchor_date
            
            # Calculate range
            end = anchor
            start = anchor - timedelta(days=int(days_back))
            
            return html.Div([
                html.Strong("Data window: "),
                f"{start.isoformat()} → {end.isoformat()}"
            ])
        else:  # explicit
            if not start_date or not end_date:
                return "Set start and end dates"
            
            # Parse dates
            if isinstance(start_date, str):
                start = datetime.fromisoformat(start_date).date()
            else:
                start = start_date
            
            if isinstance(end_date, str):
                end = datetime.fromisoformat(end_date).date()
            else:
                end = end_date
            
            return html.Div([
                html.Strong("Data window: "),
                f"{start.isoformat()} → {end.isoformat()}"
            ])
    
    # Quick Period buttons update days back (only in days_back mode)
    @app.callback(
        Output("days-back", "value"),
        Input("period-1d", "n_clicks"),
        Input("period-5d", "n_clicks"),
        Input("period-1mo", "n_clicks"),
        Input("period-3mo", "n_clicks"),
        Input("period-1y", "n_clicks"),
        State("date-selection-mode", "value"),
        prevent_initial_call=True
    )
    def update_days_back_from_buttons(n1d, n5d, n1mo, n3mo, n1y, mode):
        """Update days back when Quick Period button clicked (days_back mode only)."""
        from dash import ctx
        from dash.exceptions import PreventUpdate
        
        if mode != "days_back":
            raise PreventUpdate
        
        if not ctx.triggered:
            raise PreventUpdate
        
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        period_days = {
            "period-1d": 1,
            "period-5d": 5,
            "period-1mo": 30,
            "period-3mo": 90,
            "period-1y": 365,
        }
        
        return period_days.get(button_id, 30)
    
    # Quick Period buttons update explicit dates (only in explicit mode)
    @app.callback(
        Output("explicit-start-date", "date"),
        Output("explicit-end-date", "date"),
        Input("period-1d", "n_clicks"),
        Input("period-5d", "n_clicks"),
        Input("period-1mo", "n_clicks"),
        Input("period-3mo", "n_clicks"),
        Input("period-1y", "n_clicks"),
        State("date-selection-mode", "value"),
        prevent_initial_call=True
    )
    def update_explicit_dates_from_buttons(n1d, n5d, n1mo, n3mo, n1y, mode):
        """Update explicit dates when Quick Period button clicked (explicit mode only)."""
        from dash import ctx
        from dash.exceptions import PreventUpdate
        
        if mode != "explicit":
            raise PreventUpdate
        
        if not ctx.triggered:
            raise PreventUpdate
        
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        period_days = {
            "period-1d": 1,
            "period-5d": 5,
            "period-1mo": 30,
            "period-3mo": 90,
            "period-1y": 365,
        }
        
        days = period_days.get(button_id, 30)
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)
        
        return start_date, end_date
