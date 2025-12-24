"""Integration tests for complete data loading flow."""
import pytest
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import os
import sqlite3
import time

from trading_dashboard.data_loading.loaders.database_loader import DatabaseLoader
from trading_dashboard.data_loading.buffer_manager import BufferManager


@pytest.fixture
def temp_db():
    """Create temporary database file with schema."""
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


class TestDataLoadingIntegration:
    """Integration tests for data loading workflow."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cold_start_backfill_flow(self, temp_db):
        """
        Test complete flow: empty DB → EODHD backfill → strategy init.
        
        This is the critical path for production deployments.
        """
        # Mock EODHD backfiller to avoid real API calls
        from unittest.mock import AsyncMock
        
        # Step 1: Initialize loader with empty DB
        loader = DatabaseLoader(
            db_path=temp_db,
            backfill_enabled=True,
            api_key='test_key'
        )
        
        # Mock the backfiller
        mock_candles = pd.DataFrame({
            'timestamp': pd.date_range('2025-12-11 09:30', periods=50, freq='5min', tz='UTC'),
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000
        })
        
        loader.backfiller.fetch_rth_candles = AsyncMock(return_value=mock_candles)
        
        # Step 2: Load 50 candles (should trigger backfill)
        candles = await loader.load_candles(
            symbol='AAPL',
            interval='M5',
            required_count=50,
            session='ALL'  # Use ALL to avoid RTH filtering in test
        )
        
        # Verify results
        assert len(candles) >= 50, "Should have at least 50 candles"
        assert 'timestamp' in candles.columns
        assert 'close' in candles.columns
        
        # Verify backfill was triggered
        loader.backfiller.fetch_rth_candles.assert_called_once()
        
        # Step 3: Initialize strategy buffer
        buffer_mgr = BufferManager(required_lookback=50)
        buffer_mgr.initialize(candles)
        
        # Verify strategy readiness
        assert buffer_mgr.is_ready()
        assert len(buffer_mgr.get_buffer()) == 50
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_warm_start_fast_load(self, temp_db):
        """
        Test warm start: DB already has data → fast load.
        
        Should complete in <2 seconds.
        """
        # Pre-populate DB with data
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Insert 100 candles
        base_ts = int(datetime(2025, 12, 11, 9, 30).timestamp() * 1000)
        for i in range(100):
            ts = base_ts + (i * 5 * 60 * 1000)  # 5 min intervals
            cursor.execute(
                """
                INSERT INTO candles 
                (timestamp, symbol, interval, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, 'AAPL', 'M5', 100.0, 101.0, 99.0, 100.5, 1000)
            )
        
        conn.commit()
        conn.close()
        
        # Measure load time
        loader = DatabaseLoader(db_path=temp_db, backfill_enabled=False)
        
        start_time = time.time()
        
        candles = await loader.load_candles(
            symbol='AAPL',
            interval='M5',
            required_count=50,
            session='ALL'
        )
        
        load_time = time.time() - start_time
        
        # Assertions
        assert len(candles) == 50
        assert load_time < 2.0, f"Load took {load_time}s, expected <2s"
        
        # Verify data is sorted oldest first
        assert candles['timestamp'].is_monotonic_increasing
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_buffer_integration_with_loader(self, temp_db):
        """
        Test complete integration: DatabaseLoader → BufferManager → Strategy ready.
        """
        # Pre-populate DB
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        base_ts = int(datetime(2025, 12, 11, 9, 30).timestamp() * 1000)
        for i in range(50):
            ts = base_ts + (i * 5 * 60 * 1000)
            cursor.execute(
                """
                INSERT INTO candles 
                (timestamp, symbol, interval, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, 'APP', 'M5', 100.0 + i*0.1, 101.0, 99.0, 100.5, 1000)
            )
        
        conn.commit()
        conn.close()
        
        # Load data
        loader = DatabaseLoader(db_path=temp_db, backfill_enabled=False)
        candles = await loader.load_candles(
            symbol='APP',
            interval='M5',
            required_count=50,
            session='ALL'
        )
        
        # Initialize buffer
        buffer = BufferManager(required_lookback=50)
        buffer.initialize(candles)
        
        # Verify integration
        assert buffer.is_ready()
        
        # Add new candle
        new_candle = {
            'timestamp': pd.Timestamp('2025-12-11 13:40'),
            'open': 105.0,
            'high': 106.0,
            'low': 104.0,
            'close': 105.5,
            'volume': 2000
        }
        
        buffer.add_candle(new_candle)
        
        # Buffer should maintain size
        assert len(buffer.get_buffer()) == 50
        
        # Latest candle should be the new one
        latest = buffer.get_buffer().iloc[-1]
        assert latest['close'] == 105.5
    
    @pytest.mark.integration
    def test_partial_data_backfill(self, temp_db):
        """
        Test scenario: DB has 30/50 candles → Backfill remaining 20.
        
        This tests the incremental backfill capability.
        """
        # Pre-populate with 30 candles
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        base_ts = int(datetime(2025, 12, 11, 9, 30).timestamp() * 1000)
        for i in range(30):
            ts = base_ts + (i * 5 * 60 * 1000)
            cursor.execute(
                """
                INSERT INTO candles 
                (timestamp, symbol, interval, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, 'TSLA', 'M5', 380.0, 381.0, 379.0, 380.5, 5000)
            )
        
        conn.commit()
        conn.close()
        
        # Verify partial data exists
        loader = DatabaseLoader(db_path=temp_db, backfill_enabled=False)
        initial = loader._get_recent_candles('TSLA', 'M5', 50, 'ALL')
        
        assert len(initial) == 30, "Should have 30 candles initially"
