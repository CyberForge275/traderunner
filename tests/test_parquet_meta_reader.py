"""
Tests for fast parquet metadata reader.
"""

import pytest
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from unittest.mock import patch, MagicMock

from trading_dashboard.utils.parquet_meta_reader import (
    read_parquet_metadata_fast,
    ParquetMetadata,
)


@pytest.fixture
def sample_parquet_with_stats(tmp_path):
    """Create a parquet file with statistics enabled."""
    dates = pd.date_range('2024-11-20 09:30', periods=100, freq='1min', tz='America/New_York')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': [100.0] * 100,
        'close': [101.0] * 100,
        'high': [102.0] * 100,
        'low': [99.0] * 100,
        'volume': [1000] * 100,
    })
    
    path = tmp_path / "test_with_stats.parquet"
    
    # Write with statistics enabled
    table = pa.Table.from_pandas(df)
    pq.write_table(
        table,
        path,
        compression='snappy',
        write_statistics=True  # Ensure stats are written
    )
    
    return path


@pytest.fixture
def sample_parquet_without_stats(tmp_path):
    """Create a parquet file without statistics."""
    dates = pd.date_range('2024-11-20 09:30', periods=50, freq='1min', tz='America/New_York')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': [100.0] * 50,
        'close': [101.0] * 50,
        'high': [102.0] * 50,
        'low': [99.0] * 50,
        'volume': [1000] * 50,
    })
    
    path = tmp_path / "test_without_stats.parquet"
    
    # Write without statistics
    table = pa.Table.from_pandas(df)
    pq.write_table(
        table,
        path,
        compression='snappy',
        write_statistics=False  # No stats
    )
    
    return path


def test_parquet_meta_reader_uses_stats_no_pandas(sample_parquet_with_stats):
    """Test that happy path uses only metadata, not pandas read_parquet."""
    
    # Mock pd.read_parquet to ensure it's NOT called
    with patch('pandas.read_parquet') as mock_read:
        meta = read_parquet_metadata_fast(sample_parquet_with_stats)
        
        # Should NOT call pandas read_parquet in happy path
        mock_read.assert_not_called()
    
    # Verify results
    assert meta.exists is True
    assert meta.rows == 100
    assert meta.first_ts is not None
    assert meta.last_ts is not None
    assert meta.used_stats is True  # Should use stats
    
    # Check timestamp values are reasonable
    assert meta.first_ts.year == 2024
    assert meta.first_ts.month == 11
    assert meta.first_ts.day == 20


def test_meta_reader_fallback_when_stats_missing(sample_parquet_without_stats):
    """Test fallback to rowgroup reads when stats unavailable."""
    
    meta = read_parquet_metadata_fast(sample_parquet_without_stats)
    
    # Verify results (should still work, but used_stats=False)
    assert meta.exists is True
    assert meta.rows == 50
    assert meta.first_ts is not None
    assert meta.last_ts is not None
    assert meta.used_stats is False  # Fallback path


def test_meta_reader_nonexistent_file(tmp_path):
    """Test handling of nonexistent file."""
    nonexistent = tmp_path / "does_not_exist.parquet"
    
    meta = read_parquet_metadata_fast(nonexistent)
    
    assert meta.exists is False
    assert meta.rows == 0


def test_meta_reader_empty_parquet(tmp_path):
    """Test handling of empty parquet file."""
    # Create empty parquet
    df = pd.DataFrame({
        'timestamp': pd.DatetimeIndex([], tz='America/New_York'),
        'open': [],
        'close': [],
    })
    
    path = tmp_path / "empty.parquet"
    df.to_parquet(path)
    
    meta = read_parquet_metadata_fast(path)
    
    assert meta.exists is True
    assert meta.rows == 0


def test_meta_reader_performance(sample_parquet_with_stats):
    """Test that metadata read is fast (< 50ms)."""
    import time
    
    start = time.time()
    meta = read_parquet_metadata_fast(sample_parquet_with_stats)
    elapsed = time.time() - start
    
    # Should be very fast (metadata only)
    assert elapsed < 0.05  # 50ms
    assert meta.used_stats is True


def test_meta_reader_with_index_col(tmp_path):
    """Test with timestamp as index (common pattern)."""
    dates = pd.date_range('2024-11-20 09:30', periods=100, freq='1min', tz='America/New_York')
    df = pd.DataFrame({
        'open': [100.0] * 100,
        'close': [101.0] * 100,
    }, index=dates)
    df.index.name = 'timestamp'
    
    path = tmp_path / "indexed.parquet"
    df.to_parquet(path, write_statistics=True)
    
    meta = read_parquet_metadata_fast(path, ts_col='timestamp')
    
    assert meta.exists is True
    assert meta.rows == 100
    # Note: timestamp as index might behave differently
    # May need special handling if this fails
