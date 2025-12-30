"""
Logging configuration for Trading Dashboard
"""
import logging
import logging.handlers
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent

# Ensure logs directory exists
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Log files
DASHBOARD_LOG = LOGS_DIR / "dashboard.log"
CHARTS_LOG = LOGS_DIR / "charts.log"
ERRORS_LOG = LOGS_DIR / "errors.log"


def setup_logging():
    """Configure logging for the entire application"""

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler (for development)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Dashboard file handler (all logs)
    dashboard_handler = logging.handlers.RotatingFileHandler(
        DASHBOARD_LOG,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    dashboard_handler.setLevel(logging.INFO)
    dashboard_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    dashboard_handler.setFormatter(dashboard_formatter)
    root_logger.addHandler(dashboard_handler)

    # Charts-specific handler
    charts_logger = logging.getLogger('trading_dashboard.repositories.candles')
    charts_handler = logging.handlers.RotatingFileHandler(
        CHARTS_LOG,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    charts_handler.setLevel(logging.DEBUG)
    charts_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    charts_handler.setFormatter(charts_formatter)
    charts_logger.addHandler(charts_handler)
    charts_logger.setLevel(logging.DEBUG)

    # Pre-PaperTrade Lab specific handler
    ppt_logger = logging.getLogger('trading_dashboard.services.pre_papertrade')
    ppt_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / 'pre_papertrade.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    ppt_handler.setLevel(logging.DEBUG)
    ppt_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    ppt_handler.setFormatter(ppt_formatter)
    ppt_logger.addHandler(ppt_handler)
    ppt_logger.setLevel(logging.DEBUG)

    # Pre-PaperTrade signals handler (signal generation details)
    signals_logger = logging.getLogger('trading_dashboard.services.pre_papertrade.signals')
    signals_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / 'pre_papertrade_signals.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    signals_handler.setLevel(logging.INFO)
    signals_handler.setFormatter(ppt_formatter)
    signals_logger.addHandler(signals_handler)
    signals_logger.setLevel(logging.INFO)

    # Error file handler (errors only)
    error_handler = logging.handlers.RotatingFileHandler(
        ERRORS_LOG,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    error_handler.setFormatter(error_formatter)
    root_logger.addHandler(error_handler)

    logging.info("✅ Logging configured successfully")
    logging.info(f"📁 Dashboard logs: {DASHBOARD_LOG}")
    logging.info(f"📊 Charts logs: {CHARTS_LOG}")
    logging.info(f"🧪 Pre-PaperTrade logs: {LOGS_DIR / 'pre_papertrade.log'}")
    logging.info(f"❌ Error logs: {ERRORS_LOG}")
