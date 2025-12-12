import pytest
import pandas as pd
from datetime import datetime

from trading_dashboard.data_loading.buffer_manager import BufferManager


class TestBufferManager:
    """Unit tests for BufferManager."""
    
    @pytest.fixture
    def buffer(self):
        """Create BufferManager instance."""
        return BufferManager(required_lookback=50)
    
    @pytest.fixture
    def sample_candles(self):
        """Create sample candles."""
        return pd.DataFrame({
            'timestamp': pd.date_range('2025-12-11 09:30', periods=50, freq='5min'),
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000
        })
    
    def test_initialize_with_sufficient_data(self, buffer, sample_candles):
        """Should initialize buffer with provided candles."""
        buffer.initialize(sample_candles)
        
        assert buffer.is_ready()
        assert len(buffer.get_buffer()) == 50
        assert buffer._initialized
    
    def test_initialize_with_insufficient_data(self, buffer):
        """Should warn but still initialize with fewer candles."""
        partial_candles = pd.DataFrame({
            'timestamp': pd.date_range('2025-12-11 09:30', periods=30, freq='5min'),
            'close': 100.0
        })
        
        buffer.initialize(partial_candles)
        
        assert buffer._initialized
        assert len(buffer.get_buffer()) == 30
        assert not buffer.is_ready()  # Not enough data
    
    def test_add_candle(self, buffer, sample_candles):
        """Should add candle to buffer."""
        buffer.initialize(sample_candles)
        
        new_candle = {
            'timestamp': pd.Timestamp('2025-12-11 13:40'),
            'close': 101.0
        }
        
        buffer.add_candle(new_candle)
        
        # Buffer size should stay at max (50) due to deque maxlen
        assert len(buffer.get_buffer()) == 50
        
        # Last candle should be the new one
        last = buffer.get_buffer().iloc[-1]
        assert last['close'] == 101.0
    
    def test_get_buffer_returns_dataframe(self, buffer, sample_candles):
        """Should return buffer as DataFrame."""
        buffer.initialize(sample_candles)
        
        df = buffer.get_buffer()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 50
        assert 'timestamp' in df.columns
    
    def test_is_ready_false_before_init(self, buffer):
        """Should not be ready before initialization."""
        assert not buffer.is_ready()
    
    def test_is_ready_false_with_insufficient_data(self, buffer):
        """Should not be ready with insufficient data."""
        partial = pd.DataFrame({
            'timestamp': pd.date_range('2025-12-11 09:30', periods=10, freq='5min'),
            'close': 100.0
        })
        
        buffer.initialize(partial)
        
        assert not buffer.is_ready()
    
    def test_get_readiness_status(self, buffer, sample_candles):
        """Should return detailed readiness status."""
        buffer.initialize(sample_candles)
        
        status = buffer.get_readiness_status()
        
        assert status['initialized'] is True
        assert status['buffer_size'] == 50
        assert status['required_size'] == 50
        assert status['ready'] is True
        assert status['coverage_pct'] == 100.0
    
    def test_buffer_maintains_max_size(self, buffer, sample_candles):
        """Should maintain max size when adding more candles."""
        buffer.initialize(sample_candles)
        
        # Add 10 more candles
        for i in range(10):
            buffer.add_candle({'timestamp': f'2025-12-11 {14+i}:00', 'close': 102.0})
        
        # Should still have exactly 50 candles
        assert len(buffer.get_buffer()) == 50
    
    def test_empty_buffer_before_init(self, buffer):
        """Should have empty buffer before initialization."""
        df = buffer.get_buffer()
        
        assert len(df) == 0
        assert isinstance(df, pd.DataFrame)
