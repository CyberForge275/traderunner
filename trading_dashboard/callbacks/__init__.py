"""Register all dashboard callbacks."""
from .chart_callbacks import register_chart_callbacks
from .active_patterns_callback import register_active_patterns_callback
from .live_data_callback import register_live_data_callback


def register_all_callbacks(app):
    """Register all callback functions."""
    register_chart_callbacks(app)
    register_active_patterns_callback(app)
    register_live_data_callback(app)  # NEW: Register live data callback
