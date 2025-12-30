"""
Repository for Pre-PaperTrade Lab data access.

Provides access to:
- Signals database (configurable via Settings)
- Signal history and statistics
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, date
from typing import Optional

import pandas as pd


def _get_signals_db_path() -> Path:
    """
    Get the signals database path from central Settings.

    This eliminates hardcoded paths and makes the database location
    configurable via environment variables.

    Returns:
        Path to signals database
    """
    from src.core.settings import get_settings

    settings = get_settings()
    return settings.signals_db_path


def get_signals_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    strategy: Optional[str] = None,
    source: Optional[str] = None,
) -> pd.DataFrame:
    """
    Get summary of signals from the signals database.

    Args:
        start_date: Filter signals from this date
        end_date: Filter signals to this date
        strategy: Filter by strategy name
        source: Filter by source (e.g., 'pre_papertrade_replay')

    Returns:
        DataFrame with signal summary
    """
    db_path = _get_signals_db_path()

    if not db_path.exists():
        return pd.DataFrame(columns=[
            "symbol", "side", "entry_price", "strategy", "detected_at", "status"
        ])

    conn = sqlite3.connect(str(db_path))

    query = "SELECT * FROM signals WHERE 1=1"
    params = []

    if start_date:
        query += " AND DATE(detected_at) >= ?"
        params.append(start_date.isoformat())

    if end_date:
        query += " AND DATE(detected_at) <= ?"
        params.append(end_date.isoformat())

    if strategy:
        query += " AND strategy = ?"
        params.append(strategy)

    if source:
        query += " AND source = ?"
        params.append(source)

    query += " ORDER BY detected_at DESC"

    try:
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        conn.close()
        # Table doesn't exist yet
        return pd.DataFrame(columns=[
            "symbol", "side", "entry_price", "strategy", "detected_at", "status"
        ])


def get_signals_count(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> int:
    """
    Get count of signals in database.

    Args:
        start_date: Filter from this date
        end_date: Filter to this date

    Returns:
        Count of signals
    """
    db_path = _get_signals_db_path()

    if not db_path.exists():
        return 0

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    query = "SELECT COUNT(*) FROM signals WHERE 1=1"
    params = []

    if start_date:
        query += " AND DATE(detected_at) >= ?"
        params.append(start_date.isoformat())

    if end_date:
        query += " AND DATE(detected_at) <= ?"
        params.append(end_date.isoformat())

    try:
        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        conn.close()
        return 0


def get_signal_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    """
    Get statistics about signals.

    Args:
        start_date: Filter from this date
        end_date: Filter to this date

    Returns:
        Dictionary with statistics
    """
    df = get_signals_summary(start_date, end_date)

    if df.empty:
        return {
            "total": 0,
            "buy": 0,
            "sell": 0,
            "strategies": [],
            "symbols": [],
        }

    return {
        "total": len(df),
        "buy": len(df[df["side"] == "BUY"]),
        "sell": len(df[df["side"] == "SELL"]),
        "strategies": df["strategy"].unique().tolist(),
        "symbols": df["symbol"].unique().tolist() if "symbol" in df.columns else [],
    }


def clear_test_signals(source: str = "pre_papertrade_replay") -> int:
    """
    Clear test signals from database.

    Args:
        source: Source to clear (default: 'pre_papertrade_replay')

    Returns:
        Number of signals deleted
    """
    db_path = _get_signals_db_path()

    if not db_path.exists():
        return 0

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("DELETE FROM signals WHERE source = ?", (source,))
    deleted = cursor.rowcount

    conn.commit()
    conn.close()

    return deleted
