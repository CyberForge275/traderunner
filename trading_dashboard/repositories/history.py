"""
History data repository - Query historical events
"""
import sqlite3
import pandas as pd
from datetime import date
from typing import Optional, Dict

from ..config import SIGNALS_DB, TRADING_DB


def get_events_by_date(
    start_date: date,
    end_date: date,
    symbol_filter: Optional[str] = None,
    status_filter: Optional[str] = None
) -> pd.DataFrame:
    """
    Get all trading events within date range.
    
    Returns DataFrame with columns:
    - timestamp
    - event_type (pattern_detected, signal_created, order_intent, order_executed)
    - symbol
    - details
    - status
    """
    events = []
    
    # Get pattern detections from signals.db
    try:
        conn = sqlite3.connect(str(SIGNALS_DB))
        query = """
            SELECT 
                created_at as timestamp,
                'pattern_detected' as event_type,
                symbol,
                side || ' @ $' || entry_price as details,
                status
            FROM signals
            WHERE date(created_at) BETWEEN ? AND ?
        """
        params = [start_date.isoformat(), end_date.isoformat()]
        
        if symbol_filter:
            query += " AND symbol = ?"
            params.append(symbol_filter)
        
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        
        query += " ORDER BY created_at DESC LIMIT 1000"
        
        df_signals = pd.read_sql_query(query, conn, params=params)
        events.append(df_signals)
        conn.close()
    except Exception as e:
        print(f"Error reading signals: {e}")
    
    # Get order intents from trading.db
    try:
        conn = sqlite3.connect(str(TRADING_DB))
        query = """
            SELECT 
                created_at as timestamp,
                'order_intent' as event_type,
                symbol,
                side || ' x' || quantity || ' @ $' || price as details,
                status
            FROM order_intents
            WHERE date(created_at) BETWEEN ? AND ?
        """
        params = [start_date.isoformat(), end_date.isoformat()]
        
        if symbol_filter:
            query += " AND symbol = ?"
            params.append(symbol_filter)
        
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        
        query += " ORDER BY created_at DESC LIMIT 1000"
        
        df_orders = pd.read_sql_query(query, conn, params=params)
        events.append(df_orders)
        conn.close()
    except Exception as e:
        print(f"Error reading orders: {e}")
    
    # Combine all events
    if events:
        df = pd.concat(events, ignore_index=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp', ascending=False)
        return df.head(500)  # Limit to 500 most recent events
    
    return pd.DataFrame()


def get_daily_statistics(target_date: date) -> Dict:
    """Get statistics for a specific day."""
    stats = {
        'total_patterns': 0,
        'patterns_triggered': 0,
        'total_orders': 0,
        'orders_filled': 0,
        'win_rate': 0.0,
        'daily_pnl': 0.0
    }
    
    try:
        # Get pattern stats
        conn = sqlite3.connect(str(SIGNALS_DB))
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'triggered' THEN 1 ELSE 0 END) as triggered
            FROM signals
            WHERE date(created_at) = ?
        """
        cursor = conn.execute(query, [target_date.isoformat()])
        row = cursor.fetchone()
        if row:
            stats['total_patterns'] = row[0] or 0
            stats['patterns_triggered'] = row[1] or 0
        conn.close()
        
        # Get order stats
        conn = sqlite3.connect(str(TRADING_DB))
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END) as filled
            FROM order_intents
            WHERE date(created_at) = ?
        """
        cursor = conn.execute(query, [target_date.isoformat()])
        row = cursor.fetchone()
        if row:
            stats['total_orders'] = row[0] or 0
            stats['orders_filled'] = row[1] or 0
        conn.close()
        
        # Calculate win rate
        if stats['orders_filled'] > 0:
            stats['win_rate'] = (stats['orders_filled'] / stats['total_orders']) * 100
        
    except Exception as e:
        print(f"Error calculating statistics: {e}")
    
    return stats
