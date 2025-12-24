import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile
import os
import sqlite3

from trading_dashboard.data_loading.loaders.database_loader import DatabaseLoader


@pytest.fixture
def temp_db():
    """Create temporary database file."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    # Create table structure
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE candles (
            timestamp INTEGER,
            symbol TEXT,
            interval TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            PRIMARY KEY (timestamp, symbol, interval)
        )
    """)
    conn.commit()
    conn.close()
    
    yield db_path
    os.unlink(db_path)


@pytest.fixture
def loader(temp_db):
    """Create DatabaseLoader with temp database."""
    return DatabaseLoader(db_path=temp_db, backfill_enabled=True, api_key='test_key')


class TestDatabaseLoader:
    """Unit tests for DatabaseLoader."""
    
    @pytest.mark.asyncio
    async def test_load_candles_sufficient_data(self, temp_db):
        """Should load from DB if sufficient data exists."""
        # Pre-populate database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Insert 50 candles
        base_ts = int(datetime(2025, 12, 11, 9, 30).timestamp() * 1000)
        for i in range(50):
            ts = base_ts + (i * 5 * 60 * 1000)  # 5 min intervals
            cursor.execute(
                """
                INSERT INTO candles 
                (timestamp, symbol, interval, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, 'APP', 'M5', 100.0, 101.0, 99.0, 100.5, 1000)
            )
        
        conn.commit()
        conn.close()
        
        # Load candles
        loader = DatabaseLoader(db_path=temp_db, backfill_enabled=False)
        result = await loader.load_candles(
            symbol='APP',
            interval='M5',
            required_count=50,
            session='ALL'  # Skip RTH filter for this test
        )
        
        assert len(result) == 50
        # Should be sorted by timestamp (oldest first)
        assert result['timestamp'].is_monotonic_increasing
    
    @pytest.mark.asyncio
    async def test_load_candles_triggers_backfill(self, temp_db):
        """Should trigger backfill if DB has insufficient data."""
        # Mock backfill
        mock_backfiller = AsyncMock()
        mock_backfiller.fetch_rth_candles = AsyncMock(return_value=pd.DataFrame({
            'timestamp': pd.date_range('2025-12-11 09:30', periods=50, freq='5min', tz='UTC'),
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000
        }))
        
        loader = DatabaseLoader(db_path=temp_db, backfill_enabled=True, api_key='test_key')
        loader.backfiller = mock_backfiller
        
        result = await loader.load_candles(
            symbol='APP',
            interval='M5',
            required_count=50,
            session='ALL'
        )
        
        # Should have triggered backfill
        mock_backfiller.fetch_rth_candles.assert_called_once()
        
        # Should return sufficient data after backfill
        assert len(result) >= 50
    
    @pytest.mark.asyncio
    async def test_load_candles_backfill_disabled_raises(self, temp_db):
        """Should raise if backfill disabled and data insufficient."""
        loader = DatabaseLoader(db_path=temp_db, backfill_enabled=False)
        
        with pytest.raises(ValueError, match="backfill disabled"):
            await loader.load_candles(
                symbol='APP',
                interval='M5',
                required_count=50,
                session='ALL'
            )
    
    def test_parse_interval_minutes(self, loader):
        """Should parse interval strings correctly."""
        assert loader._parse_interval_minutes('M1') == 1
        assert loader._parse_interval_minutes('M5') == 5
        assert loader._parse_interval_minutes('M15') == 15
        assert loader._parse_interval_minutes('H1') == 60
        assert loader._parse_interval_minutes('H4') == 240
        
        with pytest.raises(ValueError):
            loader._parse_interval_minutes('D1')  # Unsupported
    
    def test_insert_candles(self, temp_db):
        """Should insert candles into database."""
        loader = DatabaseLoader(db_path=temp_db, backfill_enabled=False)
        
        candles = pd.DataFrame({
            'timestamp': pd.date_range('2025-12-11 09:30', periods=10, freq='5min', tz='UTC'),
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000
        })
        
        loader._insert_candles('APP', 'M5', candles)
        
        # Verify insertion
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM candles WHERE symbol = 'APP'")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 10
    
    def test_auto_detect_database(self):
        """Should auto-detect database path."""
        # This test would require mocking Path.exists()
        # For now, just verify it raises FileNotFoundError if no DB found
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError):
                DatabaseLoader()
