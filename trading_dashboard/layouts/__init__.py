"""Dashboard Layouts."""

from .live_monitor import create_live_monitor_layout, get_live_monitor_content
from .charts import create_charts_layout, get_charts_content
from .portfolio import create_portfolio_layout, get_portfolio_content
from .history import create_history_layout, get_history_content
from .backtests import create_backtests_layout, get_backtests_content

__all__ = [
    "create_live_monitor_layout",
    "get_live_monitor_content",
    "create_charts_layout",
    "get_charts_content",
    "create_portfolio_layout",
    "get_portfolio_content",
    "create_history_layout",
    "get_history_content",
    "create_backtests_layout",
    "get_backtests_content",
]

