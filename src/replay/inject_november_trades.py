#!/usr/bin/env python3
"""
Inject November APP trades into Pre-Papertrading Lab
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# November APP trades (24-26.11.2025)
TRADES = [
    # Nov 24
    {
        'symbol': 'APP',
        'side': 'BUY',
        'entry_price': 539.323927,
        'stop_loss': 539.323927 - (543.895605 - 539.323927),  # Inverse of profit
        'take_profit': 543.895605,
        'timestamp': '2025-11-24 15:36:00',  # 16:36 CET = 15:36 UTC
    },
    # Nov 25 - Trade 1
    {
        'symbol': 'APP',
        'side': 'SELL',
        'entry_price': 556.7343209999999,
        'stop_loss': 556.7343209999999 + (556.7343209999999 - 553.835378),  # SELL: SL above entry
        'take_profit': 553.835378,
        'timestamp': '2025-11-25 14:05:00',  # 15:05 CET = 14:05 UTC
    },
    # Nov 25 - Trade 2
    {
        'symbol': 'APP',
        'side': 'BUY',
        'entry_price': 541.394134,
        'stop_loss': 541.394134 - (541.394134 - 540.8109135),
        'take_profit': 541.394134 + (541.394134 - 540.8109135) * 2,
        'timestamp': '2025-11-25 15:44:00',  # 16:44 CET = 15:44 UTC
    },
    # Nov 26 - Trade 1
    {
        'symbol': 'APP',
        'side': 'SELL',
        'entry_price': 560.933901,
        'stop_loss': 563.0563 + (563.0563 - 560.933901),
        'take_profit': 560.933901 - (563.0563 - 560.933901) * 2,
        'timestamp': '2025-11-26 14:01:00',  # 15:01 CET = 14:01 UTC
    },
    # Nov 26 - Trade 2
    {
        'symbol': 'APP',
        'side': 'BUY',
        'entry_price': 584.588453,
        'stop_loss': 584.588453 - (587.7912150000001 - 584.588453),
        'take_profit': 587.7912150000001,
        'timestamp': '2025-11-26 15:27:00',  # 16:27 CET = 15:27 UTC
    },
]

def inject_trades(signals_db_path: str):
    """Inject November trades as signals."""
    conn = sqlite3.connect(signals_db_path)
    cursor = conn.cursor()
    
    print(f"📂 Injecting {len(TRADES)} November APP trades...")
    
    inserted = 0
    for trade in TRADES:
        try:
            cursor.execute("""
                INSERT INTO signals (
                    symbol, side, entry_price, stop_loss, take_profit,
                    created_at, strategy_name, interval
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade['symbol'],
                trade['side'],
                trade['entry_price'],
                trade['stop_loss'],
                trade['take_profit'],
                trade['timestamp'],
                'InsideBar',
                'M5'
            ))
            inserted += 1
            print(f"  ✅ {trade['symbol']} {trade['side']} @ {trade['entry_price']} ({trade['timestamp']})")
        except sqlite3.IntegrityError:
            print(f"  ⚠️  Duplicate: {trade['symbol']} at {trade['timestamp']}")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Injected {inserted}/{len(TRADES)} trades")
    return inserted

if __name__ == "__main__":
    """
    Main entry point.
    
    Uses central Settings for signals database path (configurable via TRADING_SIGNALS_DB_PATH env var).
    """
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Use Settings for default path
        script_dir = Path(__file__).resolve().parent
        project_root = script_dir.parent.parent
        sys.path.insert(0, str(project_root))
        
        from src.core.settings import get_settings
        settings = get_settings()
        db_path = str(settings.signals_db_path)
    
    inject_trades(db_path)
