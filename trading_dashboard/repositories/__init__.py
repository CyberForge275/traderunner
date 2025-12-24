"""
Data repositories for Trading Dashboard
"""
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import yaml

from ..config import SIGNALS_DB, TRADING_DB, STRATEGY_CONFIG, MARKETDATA_DIR


def get_connection(db_path: Path) -> Optional[sqlite3.Connection]:
    """Get SQLite connection with error handling."""
    if not db_path.exists():
        return None
    return sqlite3.connect(str(db_path), check_same_thread=False)


def get_watchlist_symbols() -> list[str]:
    """Get symbols for watchlist/charts from EODHD_SYMBOLS environment variable.

    Single Source of Truth: EODHD_SYMBOLS ENV variable (no hardcoded fallbacks).
    This ensures dashboard stays in sync with marketdata-stream subscriptions.

    Returns:
        List of uppercase symbol strings, or empty list if ENV not set.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # SINGLE SOURCE OF TRUTH: EODHD_SYMBOLS environment variable
        symbols_env = os.getenv("EODHD_SYMBOLS")

        if symbols_env:
            symbols = [s.strip().upper() for s in symbols_env.split(",") if s.strip()]
            if symbols:
                logger.info(f"Watchlist symbols (source=ENV EODHD_SYMBOLS): {', '.join(symbols)} ({len(symbols)} total)")
                return symbols
            else:
                logger.warning("EODHD_SYMBOLS is set but empty after parsing")
                return []

        # No ENV set - log warning and return empty
        logger.warning(
            "⚠️ EODHD_SYMBOLS environment variable not set! "
            "Dashboard watchlist will be empty. "
            "Set EODHD_SYMBOLS in systemd service or .env file."
        )
        return []

    except Exception as e:
        logger.error(f"Error loading watchlist symbols: {e}", exc_info=True)
        return []


def get_available_symbols() -> list[str]:
    """
    Get list of symbols that actually have parquet data files.
    Scans data_m1/, data_m5/, data_m15/ directories for .parquet files.

    Returns:
        Sorted list of unique symbol names (without .parquet extension)
    """
    from pathlib import Path
    from ..config import TRADERUNNER_DIR

    symbols = set()

    # Scan all data directories for parquet files
    for data_dir in ["data_m1", "data_m5", "data_m15"]:
        parquet_dir = TRADERUNNER_DIR / "artifacts" / data_dir

        if parquet_dir.exists():
            # Get all .parquet files and extract symbol names
            for parquet_file in parquet_dir.glob("*.parquet"):
                symbol = parquet_file.stem  # filename without .parquet extension
                symbols.add(symbol)

    # Return sorted list
    if not symbols:
        # Fallback if no parquet files found
        return ["AAPL", "MSFT", "NVDA", "TSLA"]

    return sorted(list(symbols))


def get_recent_patterns(hours: int = 24) -> pd.DataFrame:
    """Get recent pattern detections from signals database."""
    try:
        conn = get_connection(SIGNALS_DB)
        if conn is None:
            return pd.DataFrame()

        since = datetime.now() - timedelta(hours=hours)

        query = """
            SELECT
                id, symbol, datetime(created_at) as detected_at,
                entry_price, stop_loss, take_profit, side, status
            FROM signals
            WHERE created_at > ?
            ORDER BY created_at DESC
            LIMIT 50
        """

        df = pd.read_sql_query(query, conn, params=[since.isoformat()])
        conn.close()
        return df
    except Exception as e:
        print(f"Error reading signals: {e}")
        return pd.DataFrame()


def get_order_intents(hours: int = 24) -> pd.DataFrame:
    """Get recent order intents from trading.db."""
    try:
        conn = get_connection(TRADING_DB)
        if conn is None:
            return pd.DataFrame()

        since = datetime.now() - timedelta(hours=hours)

        query = """
            SELECT
                id, symbol, side, quantity, price, status,
                datetime(created_at) as created_at,
                datetime(updated_at) as updated_at
            FROM order_intents
            WHERE created_at > ?
            ORDER BY created_at DESC
            LIMIT 50
        """

        df = pd.read_sql_query(query, conn, params=[since.isoformat()])
        conn.close()
        return df
    except Exception as e:
        print(f"Error reading order intents: {e}")
        return pd.DataFrame()


def get_system_status() -> dict:
    """Check status of key system components."""
    import subprocess

    status = {
        "marketdata_stream": False,
        "automatictrader_api": False,
        "automatictrader_worker": False,
        "signals_db": SIGNALS_DB.exists(),
        "trading_db": TRADING_DB.exists()
    }

    services = [
        ("marketdata_stream", "marketdata-stream"),
        ("automatictrader_api", "automatictrader-api"),
        ("automatictrader_worker", "automatictrader-worker")
    ]

    for key, service in services:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service],
                capture_output=True, text=True, timeout=2
            )
            status[key] = result.stdout.strip() == "active"
        except (subprocess.SubprocessError, FileNotFoundError, PermissionError):
            try:
                result = subprocess.run(
                    ["pgrep", "-f", service.replace("-", "_")],
                    capture_output=True, timeout=2
                )
                status[key] = result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

    return status


def get_portfolio_summary() -> dict:
    """Get portfolio summary (placeholder)."""
    return {
        "total_value": 10000.00,
        "cash": 10000.00,
        "positions_value": 0.00,
        "daily_pnl": 0.00,
        "daily_pnl_pct": 0.00,
        "positions": []
    }
