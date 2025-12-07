"""Callbacks for cached symbol selector."""

from dash import Input, Output, State
from pathlib import Path


def register_symbol_selector_callbacks(app):
    """Register callbacks for symbol selector functionality."""
    
    @app.callback(
        Output("cached-symbols-selector", "options"),
        Input("backtests-new-timeframe", "value"),
    )
    def update_cached_symbols_options(timeframe):
        """Update cached symbol options when timeframe changes."""
        from ..utils.symbol_cache import get_symbols_for_timeframe
        from pathlib import Path
        
        if not timeframe:
            return []
        
        # Get absolute path to artifacts directory
        dashboard_dir = Path(__file__).parents[1]  # trading_dashboard/
        project_root = dashboard_dir.parent  # traderunner/
        artifacts_dir = project_root / "artifacts"
        
        cached_symbols = get_symbols_for_timeframe(timeframe, str(artifacts_dir))
        return [{"label": symbol, "value": symbol} for symbol in cached_symbols]
    
    @app.callback(
        Output("backtests-new-symbols", "value"),
        Input("cached-symbols-selector", "value"),
        State("backtests-new-symbols", "value"),
        prevent_initial_call=True
    )
    def update_symbols_from_selector(selected_symbols, current_value):
        """Update symbols input when selector changes."""
        if not selected_symbols:
            return current_value
        
        # Combine selected symbols with any manually typed ones
        selected_set = set(selected_symbols)
        
        # Parse current manually entered symbols
        if current_value:
            manual_symbols = [s.strip() for s in current_value.split(",") if s.strip()]
            selected_set.update(manual_symbols)
        
        # Return as comma-separated string
        return ",".join(sorted(selected_set))
