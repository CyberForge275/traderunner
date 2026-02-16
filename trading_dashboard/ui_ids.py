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

    # Tab IDs
    TAB_LIVE_MONITOR = "live-monitor"
    TAB_PORTFOLIO = "portfolio"
    TAB_CHARTS_LIVE = "charts-live"
    TAB_CHARTS_BACKTESTING = "charts-backtesting"
    TAB_HISTORY = "history"
    TAB_BACKTESTS = "backtests"
    TAB_PRE_PAPERTRADE = "pre-papertrade"
    TAB_TRADE_INSPECTOR = "trade-inspector"


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

    ORDERS_INSPECT_MODAL = "bt:orders-inspect-modal"
    ORDERS_INSPECT_TITLE = "bt:orders-inspect-title"
    ORDERS_INSPECT_BODY = "bt:orders-inspect-body"
    ORDERS_INSPECT_CLOSE = "bt:orders-inspect-modal__close"
    ORDERS_INSPECT_CHART = "bt:orders-inspect-chart"

    TRADES_INSPECT_MODAL = "bt:trades-inspect-modal"
    TRADES_INSPECT_TITLE = "bt:trades-inspect-title"
    TRADES_INSPECT_BODY = "bt:trades-inspect-body"
    TRADES_INSPECT_CLOSE = "bt:trades-inspect-modal__close"
    TRADES_INSPECT_CHART = "bt:trades-inspect-chart"
    
    RUN_DROPDOWN = "bt:run-dropdown"
    STATUS_CONTAINER = "bt:status-container"
    RUN_STATUS_ICON = "bt:run-status-icon"
    REFRESH_BUTTON = "bt:refresh-button"
    DETAIL_CONTAINER = "bt:detail-container"
    VERSION_PATTERN_HINT = "bt:version-hint"
    
    # Stores
    LOADED_METRICS = "bt:store:metrics"
    
    @staticmethod
    def RESULT_ROW(run_id: str):
        """Pattern ID for a specific backtest result row."""
        return {"type": "bt:result-row", "run_id": run_id}

    @staticmethod
    def ERROR_COLLAPSE_BTN(job_id: str):
        """Pattern ID for the error traceback collapse button."""
        return {"type": "bt:error-collapse-btn", "job_id": job_id}

    @staticmethod
    def ERROR_COLLAPSE(job_id: str):
        """Pattern ID for the error traceback collapse container."""
        return {"type": "bt:error-collapse", "job_id": job_id}


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

    @staticmethod
    def PARAM_INPUT(section: str, key: str):
        """Pattern ID for an editable strategy parameter input."""
        return {"type": "ssot-param-input", "section": section, "key": key}


class RUN:
    """Execution & New Backtest IDs"""
    STRATEGY_DROPDOWN = "run:strategy-dropdown"
    VERSION_DROPDOWN = "run:version-dropdown"
    VERSION_LABEL = "run:version-label"
    CONFIG_PREVIEW = "run:config-preview"
    CONFIG_CONTAINER = "run:config-container"
    RUN_NAME_INPUT = "run:name-input"
    RUN_NAME_PREFIX = "run:name-prefix"
    SYMBOL_SELECTOR_CACHED = "run:symbol-selector-cached"
    SYMBOL_INPUT = "run:symbol-input"
    TIMEFRAME_DROPDOWN = "run:timeframe-dropdown"
    DATE_MODE_RADIO = "run:date-mode"
    ANCHOR_DATE_CONTAINER = "run:anchor-date-container"
    ANCHOR_DATE_PICKER = "run:anchor-date"
    DAYS_BACK_CONTAINER = "run:days-back-container"
    DAYS_BACK_INPUT = "run:days-back"
    EXPLICIT_RANGE_CONTAINER = "run:explicit-range-container"
    EXPLICIT_START_PICKER = "run:explicit-start"
    EXPLICIT_END_PICKER = "run:explicit-end"
    DISPLAY_WINDOW = "run:display-window"
    COMPOUND_TOGGLE = "run:compound-toggle"
    EQUITY_BASIS_DROPDOWN = "run:equity-basis"
    START_BUTTON = "run:run-button" # Keyed to the existing backtests-run-button
    PROGRESS_CONTAINER = "run:progress"
    PIPELINE_LOG = "run:pipeline-log"
    CURRENT_JOB_ID_STORE = "run:job-id"
    CONFIG_STORE = "run:config-store"


class Common:
    """Shared/Global components"""
    TOAST_CONTAINER = "common:toast-container"
    CONFIRM_DIALOG = "common:confirm-dialog"


__all__ = ["Nav", "BT", "SSOT", "RUN", "Common"]
