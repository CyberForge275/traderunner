#!/usr/bin/env python3
"""
Daily Data Update Script

Updates yearly parquet files from MySQL database.
Run daily at 4:00 AM via cron job.

Usage:
    python update_daily_data.py --year 2025
    python update_daily_data.py --auto  # Current year
"""
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
import sys

try:
    import mysql.connector
except ImportError:
    print("ERROR: mysql-connector-python not installed")
    print("Install: pip install mysql-connector-python")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DailyDataUpdater:
    """Updates daily parquet files from MySQL."""

    def __init__(
        self,
        mysql_host: str = 'localhost',
        mysql_user: str = 'trading',
        mysql_password: str = None,
        mysql_database: str = 'market_data',
        output_dir: str = '/opt/trading/traderunner/artifacts/data_d1'
    ):
        """
        Initialize updater.

        Args:
            mysql_host: MySQL host
            mysql_user: MySQL username
            mysql_password: MySQL password (or set MYSQL_PASSWORD env var)
            mysql_database: Database name
            output_dir: Directory for parquet files (consistent with M1/M5/M15)
        """
        self.mysql_config = {
            'host': mysql_host,
            'user': mysql_user,
            'password': mysql_password or self._get_mysql_password(),
            'database': mysql_database
        }

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_mysql_password(self) -> str:
        """Get MySQL password from environment or file."""
        import os

        # Try environment variable
        password = os.getenv('MYSQL_PASSWORD')
        if password:
            return password

        # Try password file
        password_file = Path.home() / '.mysql_password'
        if password_file.exists():
            return password_file.read_text().strip()

        raise ValueError(
            "MySQL password not found. Set MYSQL_PASSWORD env var or "
            "create ~/.mysql_password file"
        )

    def update_year(self, year: int):
        """
        Update parquet file for a specific year.

        Args:
            year: Year to update (e.g., 2025)
        """
        logger.info(f"Updating daily data for year {year}...")

        # Query MySQL for all daily data in that year
        query = f"""
            SELECT
                timestamp,
                symbol,
                open,
                high,
                low,
                close,
                volume
            FROM daily_candles
            WHERE YEAR(timestamp) = {year}
            ORDER BY timestamp, symbol
        """

        try:
            # Connect to MySQL
            conn = mysql.connector.connect(**self.mysql_config)
            logger.info(f"Connected to MySQL: {self.mysql_config['host']}/{self.mysql_config['database']}")

            # Load data
            df = pd.read_sql(query, conn)
            conn.close()

            if df.empty:
                logger.warning(f"No data found for year {year}")
                return

            logger.info(f"Loaded {len(df)} rows from MySQL")
            logger.info(f"Symbols: {df['symbol'].nunique()}")
            logger.info(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Normalize column names
            df.columns = [c.lower() for c in df.columns]

            # Save to parquet
            output_file = self.output_dir / f'universe_{year}.parquet'
            df.to_parquet(output_file, compression='snappy', index=False)

            file_size_mb = output_file.stat().st_size / 1024 / 1024
            logger.info(f"✅ Saved to {output_file} ({file_size_mb:.2f} MB)")

        except mysql.connector.Error as e:
            logger.error(f"MySQL error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error updating year {year}: {e}")
            raise

    def update_current_year(self):
        """Update parquet file for current year."""
        year = datetime.now().year
        self.update_year(year)

    def verify_update(self, year: int) -> dict:
        """
        Verify parquet file contents.

        Args:
            year: Year to verify

        Returns:
            Dict with verification results
        """
        file_path = self.output_dir / f'universe_{year}.parquet'

        if not file_path.exists():
            return {'exists': False}

        df = pd.read_parquet(file_path)

        return {
            'exists': True,
            'file_size_mb': file_path.stat().st_size / 1024 / 1024,
            'row_count': len(df),
            'symbol_count': df['symbol'].nunique(),
            'date_min': df['timestamp'].min(),
            'date_max': df['timestamp'].max(),
            'columns': df.columns.tolist()
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Update daily data from MySQL')
    parser.add_argument('--year', type=int, help='Specific year to update')
    parser.add_argument('--auto', action='store_true', help='Update current year')
    parser.add_argument('--verify', action='store_true', help='Verify after update')
    parser.add_argument('--mysql-host', default='localhost', help='MySQL host')
    parser.add_argument('--mysql-user', default='trading', help='MySQL user')
    parser.add_argument('--mysql-db', default='market_data', help='MySQL database')
    parser.add_argument('--output-dir', default='/opt/trading/traderunner/artifacts/data_d1',
                        help='Output directory (consistent with M1/M5/M15)')

    args = parser.parse_args()

    # Determine year
    if args.auto:
        year = datetime.now().year
    elif args.year:
        year = args.year
    else:
        parser.error('Either --year or --auto must be specified')

    # Create updater
    updater = DailyDataUpdater(
        mysql_host=args.mysql_host,
        mysql_user=args.mysql_user,
        mysql_database=args.mysql_db,
        output_dir=args.output_dir
    )

    # Run update
    try:
        updater.update_year(year)

        if args.verify:
            logger.info("\nVerifying update...")
            result = updater.verify_update(year)

            if result['exists']:
                logger.info(f"✅ Verification passed:")
                logger.info(f"   File size: {result['file_size_mb']:.2f} MB")
                logger.info(f"   Rows: {result['row_count']:,}")
                logger.info(f"   Symbols: {result['symbol_count']}")
                logger.info(f"   Date range: {result['date_min']} to {result['date_max']}")
            else:
                logger.error("❌ Verification failed: File not found")
                sys.exit(1)

        logger.info("\n✅ Update completed successfully")

    except Exception as e:
        logger.error(f"\n❌ Update failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
