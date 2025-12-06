"""
History tab callbacks - Date filtering and CSV export
"""
from dash import Input, Output, State


def register_history_callbacks(app):
    """Register callbacks for history tab functionality."""
    
    @app.callback(
        Output("history-timeline", "children"),
        Output("history-stats", "children"),
        Input("date-picker-range", "start_date"),
        Input("date-picker-range", "end_date"),
        Input("history-symbol-filter", "value"),
        Input("history-status-filter", "value")
    )
    def update_history(start_date, end_date, symbol_filter, status_filter):
        """Update timeline and stats when filters change."""
        from ..repositories.history import get_events_by_date, get_daily_statistics
        from ..layouts.history import create_event_timeline, create_statistics_cards
        from datetime import datetime
        
        # Convert string dates to date objects
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date).date()
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date).date()
        
        # Apply filters
        symbol = None if symbol_filter == 'all' else symbol_filter
        status = None if status_filter == 'all' else status_filter
        
        # Get data
        events = get_events_by_date(start_date, end_date, symbol, status)
        stats = get_daily_statistics(end_date)
        
        # Create components
        timeline = create_event_timeline(events)
        stats_cards = create_statistics_cards(stats)
        
        return timeline, stats_cards
    
    @app.callback(
        Output("download-csv", "data"),
        Input("export-csv-btn", "n_clicks"),
        State("date-picker-range", "start_date"),
        State("date-picker-range", "end_date"),
        State("history-symbol-filter", "value"),
        State("history-status-filter", "value"),
        prevent_initial_call=True
    )
    def export_to_csv(n_clicks, start_date, end_date, symbol_filter, status_filter):
        """Export current timeline to CSV."""
        from dash import dcc
        from ..repositories.history import get_events_by_date
        from datetime import datetime
        
        # Convert dates
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date).date()
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date).date()
        
        # Apply filters
        symbol = None if symbol_filter == 'all' else symbol_filter
        status = None if status_filter == 'all' else status_filter
        
        # Get data
        events = get_events_by_date(start_date, end_date, symbol, status)
        
        if events.empty:
            return None
        
        # Generate filename
        filename = f"trading_events_{start_date}_{end_date}.csv"
        
        # Convert to CSV
        return dcc.send_data_frame(events.to_csv, filename, index=False)
