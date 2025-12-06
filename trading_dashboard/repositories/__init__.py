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
    """Get symbols from strategy configuration."""
    try:
        # First try: Read from EODHD_SYMBOLS environment variable (used by marketdata-stream)
        symbols_env = os.getenv("EODHD_SYMBOLS")
        if symbols_env:
            symbols = [s.strip() for s in symbols_env.split(",")]
            if symbols:
                return symbols
        
        # Second try: Read from .env file in marketdata directory
        env_file = MARKETDATA_DIR / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("EODHD_SYMBOLS="):
                        symbols_str = line.split("=", 1)[1].strip()
                        symbols = [s.strip() for s in symbols_str.split(",")]
                        if symbols:
                            return symbols
        
        # Third try: Read from strategy_params.yaml
        if not STRATEGY_CONFIG.exists():
            return ["AAPL", "MSFT", "TSLA", "NVDA", "PLTR"]
        
        with open(STRATEGY_CONFIG) as f:
            config = yaml.safe_load(f)
        
        if 'strategies' in config and 'insidebar' in config['strategies']:
            return config['strategies']['insidebar'].get('symbols', [])
        
        return config.get('symbols', ["AAPL", "MSFT", "TSLA"])
    except Exception as e:
        print(f"Error loading strategy config: {e}")
        return ["AAPL", "MSFT", "TSLA"]


def get_recent_patterns(hours: int = 24) -> pd.DataFrame:
    """Get recent pattern detections from signals.db."""
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
