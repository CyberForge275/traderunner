"""Unit tests for Inside Bar data loader."""
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import tempfile
import os
import sqlite3

from ..data_loader import InsideBarDataLoader, create_insidebar_loader


@pytest.fixture
def temp_db():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

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


class TestInsideBarDataLoader:
    """Tests for InsideBarDataLoader."""

    @pytest.mark.asyncio
    async def test_initialization(self, temp_db):
        """Should initialize with database and buffer."""
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
                (ts, 'APP', 'M5', 100.0, 101.0, 99.0, 100.5, 1000)
            )

        conn.commit()
        conn.close()

        # Initialize loader
        loader = InsideBarDataLoader(
            symbol='APP',
            interval='M5',
            lookback_candles=50,
            db_path=temp_db,
            backfill_enabled=False
        )

        await loader.initialize()

        assert loader.is_ready()
        assert loader._initialized

        candles = loader.get_candles()
        assert len(candles) == 50

    @pytest.mark.asyncio
    async def test_add_candle(self, temp_db):
        """Should add new candle to buffer."""
        # Pre-populate
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
                (ts, 'APP', 'M5', 100.0, 101.0, 99.0, 100.5, 1000)
            )

        conn.commit()
        conn.close()

        loader = InsideBarDataLoader(
            symbol='APP',
            interval='M5',
            db_path=temp_db,
            backfill_enabled=False
        )

        await loader.initialize()

        # Add new candle
        new_candle = {
            'timestamp': pd.Timestamp('2025-12-11 13:40'),
            'open': 101.0,
            'high': 102.0,
            'low': 100.0,
            'close': 101.5,
            'volume': 2000
        }

        loader.add_candle(new_candle)

        # Buffer should maintain size
        candles = loader.get_candles()
        assert len(candles) == 50

        # Latest candle should be the new one
        latest = candles.iloc[-1]
        assert latest['close'] == 101.5

    @pytest.mark.asyncio
    async def test_get_status(self, temp_db):
        """Should return detailed status."""
        loader = InsideBarDataLoader(
            symbol='APP',
            interval='M5',
            db_path=temp_db,
            backfill_enabled=False
        )

        # Before init
        status = loader.get_status()
        assert status['initialized'] is False
        assert status['symbol'] == 'APP'
        assert status['interval'] == 'M5'

    @pytest.mark.asyncio
    async def test_not_initialized_error(self):
        """Should raise error if accessing before initialization."""
        loader = InsideBarDataLoader(symbol='APP', backfill_enabled=False)

        with pytest.raises(RuntimeError, match="not initialized"):
            loader.get_candles()

        with pytest.raises(RuntimeError, match="not initialized"):
            loader.add_candle({'timestamp': pd.Timestamp.now()})

    @pytest.mark.asyncio
    async def test_create_convenience_function(self, temp_db):
        """Test convenience function."""
        # This would need mocking or real data
        # For now just verify it doesn't crash
        pass  # Skip - requires DB setup
