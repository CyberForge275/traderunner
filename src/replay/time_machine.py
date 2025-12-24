#!/usr/bin/env python3
"""
Time Machine Replay - Inject historical backtest signals into Pre-Papertrading Lab

This script:
1. Loads successful backtest run data
2. Extracts signal generation moments
3. Injects them into the signals database (with backup)
4. Allows rollback if needed

NO CHANGES to Pre-Papertrading Lab code - pure external injection!
"""
import sqlite3
import pandas as pd
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import json


class TimeMachine:
    """Replay historical backtest signals into Pre-Papertrading Lab."""

    def __init__(self, signals_db_path: str, backup: bool = True):
        self.signals_db = Path(signals_db_path)
        self.backup_path = None

        if backup and self.signals_db.exists():
            self.backup_path = self._create_backup()

    def _create_backup(self) -> Path:
        """Create timestamped backup of signals database."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = self.signals_db.parent / f"signals_backup_{timestamp}.db"
        shutil.copy2(self.signals_db, backup)
        print(f"✅ Backup created: {backup}")
        return backup

    def rollback(self):
        """Restore from backup."""
        if not self.backup_path or not self.backup_path.exists():
            print("❌ No backup found!")
            return False

        shutil.copy2(self.backup_path, self.signals_db)
        print(f"✅ Rolled back to: {self.backup_path}")
        return True

    def load_backtest_signals(self, run_dir: Path) -> pd.DataFrame:
        """
        Extract signals from backtest run.

        Returns DataFrame with columns:
        - symbol
        - side (BUY/SELL)
        - entry_price
        - stop_loss
        - take_profit
        - detected_at (timestamp)
        """
        # Load orders from backtest
        orders_file = run_dir / "orders.csv"
        if not orders_file.exists():
            raise FileNotFoundError(f"Orders file not found: {orders_file}")

        orders = pd.read_csv(orders_file)

        # Entry orders are MARKET or LIMIT (not STOP which is exit)
        # Each BUY/SELL pair represents entry + stop loss
        entry_orders = orders[orders['order_type'].isin(['MARKET', 'LIMIT'])].copy()

        if len(entry_orders) == 0:
            print("⚠️  No entry orders found, trying alternative approach...")
            # Alternative: group by side and take first of each pair
            entry_orders = orders.groupby(['symbol', 'side', 'valid_from']).first().reset_index()

        # Convert to signals format
        signals = pd.DataFrame({
            'symbol': entry_orders['symbol'],
            'side': entry_orders['side'],
            'entry_price': entry_orders['price'],
            'stop_loss': entry_orders['stop_loss'],
            'take_profit': entry_orders['take_profit'],
            'detected_at': pd.to_datetime(entry_orders['valid_from'], utc=True),
            'strategy': 'InsideBar',
            'timeframe': 'M5',
            'metadata': '{}'  # Could include pattern details if needed
        })

        # Remove any duplicates
        signals = signals.drop_duplicates(subset=['symbol', 'detected_at', 'side'])

        return signals.sort_values('detected_at').reset_index(drop=True)

    def inject_signals(self, signals: pd.DataFrame, time_shift: timedelta = None):
        """
        Inject signals into the signals database.

        Args:
            signals: DataFrame with signal data
            time_shift: Optional time offset (e.g., shift to today)
        """
        if time_shift:
            signals['detected_at'] = signals['detected_at'] + time_shift

        # Connect to signals database
        conn = sqlite3.connect(self.signals_db)

        try:
            # Check table schema
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
            if not cursor.fetchone():
                print("⚠️  signals table doesn't exist, creating...")
                self._create_signals_table(conn)

            # Get actual column names from existing table
            cursor.execute("PRAGMA table_info(signals)")
            schema_columns = {col[1] for col in cursor.fetchall()}

            # Insert signals using actual schema
            signals_to_insert = signals.copy()
            timestamps_list = signals_to_insert['detected_at'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()

            inserted_count = 0
            for idx, (_, row) in enumerate(signals_to_insert.iterrows()):
                try:
                    timestamp_str = timestamps_list[idx]

                    # Use actual schema column names
                    cursor.execute("""
                        INSERT INTO signals (
                            symbol, side, entry_price, stop_loss, take_profit,
                            created_at, strategy_name, interval
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['symbol'], row['side'], row['entry_price'],
                        row['stop_loss'], row['take_profit'], timestamp_str,
                        row['strategy'], row['timeframe']
                    ))
                    inserted_count += 1
                except sqlite3.IntegrityError as e:
                    print(f"⚠️  Duplicate signal skipped: {row['symbol']} at {timestamp_str}")

            conn.commit()
            print(f"✅ Injected {inserted_count}/{len(signals)} signals")

        finally:
            conn.close()

    def _create_signals_table(self, conn):
        """Create signals table if it doesn't exist."""
        conn.execute("""
            CREATE TABLE signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                detected_at TEXT NOT NULL,
                strategy TEXT,
                timeframe TEXT,
                metadata TEXT,
                UNIQUE(symbol, detected_at, side)
            )
        """)
        conn.commit()

    def get_signal_count(self) -> int:
        """Count signals in database."""
        if not self.signals_db.exists():
            return 0

        conn = sqlite3.connect(self.signals_db)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM signals WHERE 1")
            return cursor.fetchone()[0]
        except:
            return 0
        finally:
            conn.close()


def main():
    """
    Main entry point for Time Machine replay.

    Uses central Settings for signals database path (configurable via TRADING_SIGNALS_DB_PATH env var).
    """
    # Import Settings for default path resolution
    import sys
    from pathlib import Path as PathLib

    # Add src to path for Settings import
    script_dir = PathLib(__file__).resolve().parent
    project_root = script_dir.parent.parent
    sys.path.insert(0, str(project_root))

    from src.core.settings import get_settings

    # Get default signals DB path from Settings
    settings = get_settings()
    default_signals_db = str(settings.signals_db_path)

    parser = argparse.ArgumentParser(description="Time Machine: Replay backtest signals")
    parser.add_argument("--run-id", required=True, help="Backtest run ID")
    parser.add_argument("--signals-db", default=default_signals_db,
                       help=f"Path to signals database (default: from Settings)")
    parser.add_argument("--date", help="Replay specific date (YYYY-MM-DD)")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    parser.add_argument("--rollback", action="store_true", help="Rollback last injection")
    parser.add_argument("--analyze", action="store_true", help="Only analyze, don't inject")

    args = parser.parse_args()

    # Initialize Time Machine
    tm = TimeMachine(args.signals_db, backup=not args.no_backup)

    # Rollback mode
    if args.rollback:
        tm.rollback()
        return

    # Load backtest data
    run_dir = Path(f"artifacts/backtests/{args.run_id}")
    if not run_dir.exists():
        print(f"❌ Run directory not found: {run_dir}")
        return

    print(f"📂 Loading backtest: {args.run_id}")
    signals = tm.load_backtest_signals(run_dir)

    print(f"\n📊 Found {len(signals)} signals")
    print(f"   Date range: {signals['detected_at'].min()} → {signals['detected_at'].max()}")
    print(f"   Symbols: {signals['symbol'].unique()}")
    print(f"   BUY: {len(signals[signals['side']=='BUY'])}, SELL: {len(signals[signals['side']=='SELL'])}")

    # Filter by date if specified
    if args.date:
        target_date = pd.to_datetime(args.date).date()
        # Convert timezone-aware to naive for date comparison
        signals_dates = pd.to_datetime(signals['detected_at']).dt.tz_convert('Europe/Berlin').dt.date
        signals = signals[signals_dates == target_date]
        print(f"\n🎯 Filtered to {args.date}: {len(signals)} signals")

    # Analyze mode - just show, don't inject
    if args.analyze:
        print("\n📋 Sample signals:")
        print(signals.head(10).to_string())
        return

    # Check current DB state
    current_count = tm.get_signal_count()
    print(f"\n💾 Current signals in DB: {current_count}")

    # Inject signals
    print("\n🚀 Injecting signals...")
    tm.inject_signals(signals)

    new_count = tm.get_signal_count()
    print(f"✅ Total signals now: {new_count} (+{new_count - current_count})")

    if tm.backup_path:
        print(f"\n💡 To rollback: python {__file__} --rollback --signals-db {args.signals_db}")


if __name__ == "__main__":
    main()
