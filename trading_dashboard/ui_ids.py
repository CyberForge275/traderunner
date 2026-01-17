"""Single Source of Truth (SSOT) for Dash Component IDs.

All IDs used in layouts and callbacks MUST be defined here as constants or pattern builders.
Convention: lowercase with ':' or '-' separators (e.g., 'bt:run-table').
"""

class Nav:
    """Navigation and Layout IDs"""
    MAIN_TABS = "nav:main-tabs"
    TAB_CONTENT = "nav:tab-content"
    HEADER_TIME = "nav:header-time"
    LAST_UPDATE = "nav:last-update"
    MARKET_STATUS = "nav:market-status"
    REFRESH_INTERVAL = "nav:refresh-interval"


class BT:
    """Backtest Results Tab IDs"""
    STRATEGY_FILTER = "bt:strategy-filter"
    TABLE = "bt:run-table"
    METRICS_TABLE = "bt:metrics-table"
    LOG_TABLE = "bt:log-table"
    LOG_SUMMARY = "bt:log-summary"
    ORDERS_TABLE = "bt:orders-table"
    FILLS_TABLE = "bt:fills-table"
    TRADES_TABLE = "bt:trades-table"
    RK_TABLE = "bt:rk-table"
    
    # Stores
    LOADED_METRICS = "bt:store:metrics"
    
    @staticmethod
    def RESULT_ROW(run_id: str):
        """Pattern ID for a specific backtest result row."""
        return {"type": "bt:result-row", "run_id": run_id}


class SSOT:
    """Config Viewer & SSOT Management IDs"""
    STRATEGY_ID = "ssot:strategy-id"
    VERSION = "ssot:version"
    NEW_VERSION = "ssot:new-version"
    LOAD_BUTTON = "ssot:load-button"
    RESET_BUTTON = "ssot:reset-button"
    SAVE_VERSION_BUTTON = "ssot:save-version"
    FINALIZE_BUTTON = "ssot:finalize-button"
    SAVE_STATUS = "ssot:save-status"
    LOAD_STATUS = "ssot:load-status"
    LOADED_DEFAULTS_STORE = "ssot:loaded-defaults"
    EDITABLE_FIELDS_CONTAINER = "ssot:editable-fields"


class RUN:
    """Execution & New Backtest IDs"""
    STRATEGY_DROPDOWN = "run:strategy-dropdown"
    VERSION_DROPDOWN = "run:version-dropdown"
    CONFIG_CONTAINER = "run:config-container"
    RUN_NAME_INPUT = "run:name-input"
    START_BUTTON = "run:start-button"


class Common:
    """Shared/Global components"""
    TOAST_CONTAINER = "common:toast-container"
    CONFIRM_DIALOG = "common:confirm-dialog"


__all__ = ["Nav", "BT", "SSOT", "RUN", "Common"]
