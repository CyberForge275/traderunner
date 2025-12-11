"""
Unit tests for price chart builder.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from visualization.plotly.price_chart import build_price_chart
from visualization.plotly.config import PriceChartConfig


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV DataFrame for testing."""
    dates = pd.date_range(
        start=datetime(2024, 1, 1, 9, 30),
        periods=100,
        freq="5min"
    )
    
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(100) * 0.5)
    
    df = pd.DataFrame({
        "open": close + np.random.randn(100) * 0.2,
        "high": close + abs(np.random.randn(100) * 0.5),
        "low": close - abs(np.random.randn(100) * 0.5),
        "close": close,
        "volume": np.random.randint(1000, 10000, 100),
    }, index=dates)
    
    return df


class TestBuildPriceChart:
    """Tests for build_price_chart function."""
    
    def test_basic_chart(self, sample_ohlcv):
        """Test basic chart building with default config."""
        config = PriceChartConfig()
        fig = build_price_chart(sample_ohlcv, {}, config)
        
        # Verify figure structure
        assert fig is not None
        assert len(fig.data) >= 1
        assert fig.data[0].type == "candlestick"
        
        # Verify volume trace present when enabled
        if config.show_volume:
            assert len(fig.data) == 2
            assert fig.data[1].type == "bar"
    
    def test_chart_without_volume(self, sample_ohlcv):
        """Test chart without volume subplot."""
        config = PriceChartConfig(show_volume=False)
        fig = build_price_chart(sample_ohlcv, {}, config)
        
        # Should only have candlestick
        assert len(fig.data) == 1
        assert fig.data[0].type == "candlestick"
    
    def test_chart_with_indicators(self, sample_ohlcv):
        """Test chart with moving average indicators."""
        # Compute indicators
        indicators = {
            "ma_20": sample_ohlcv["close"].rolling(20).mean(),
            "ma_50": sample_ohlcv["close"].rolling(50).mean(),
        }
        
        config = PriceChartConfig(show_volume=False)
        fig = build_price_chart(sample_ohlcv, indicators, config)
        
        # Should have candlestick + 2 MA traces
        assert len(fig.data) == 3
        assert fig.data[0].type == "candlestick"
        assert fig.data[1].type == "scatter"
        assert fig.data[2].type == "scatter"
    
    def test_missing_columns(self):
        """Test error handling for missing required columns."""
        bad_df = pd.DataFrame({"close": [1, 2, 3]})
        config = PriceChartConfig()
        
        with pytest.raises(ValueError, match="Missing required columns"):
            build_price_chart(bad_df, {}, config)
    
    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        config = PriceChartConfig()
        
        fig = build_price_chart(empty_df, {}, config)
        
        # Should return a figure with "No data" message
        assert fig is not None
        assert "No data" in fig.layout.title.text
    
    def test_session_filtering_rth(self, sample_ohlcv):
        """Test RTH session filtering."""
        config = PriceChartConfig(session_mode="rth")
        fig = build_price_chart(sample_ohlcv, {}, config)
        
        # Chart should be built (data is already in RTH hours)
        assert fig is not None
        assert len(fig.data) >= 1
    
    def test_session_filtering_all(self, sample_ohlcv):
        """Test 'all' session mode (no filtering)."""
        config = PriceChartConfig(session_mode="all")
        fig = build_price_chart(sample_ohlcv, {}, config)
        
        assert fig is not None
        assert len(fig.data) >= 1
    
    def test_dark_theme(self, sample_ohlcv):
        """Test dark theme mode."""
        config = PriceChartConfig(theme_mode="dark")
        fig = build_price_chart(sample_ohlcv, {}, config)
        
        assert fig is not None
        # Verify dark theme template applied
        assert fig.layout.template.layout.paper_bgcolor is not None
    
    def test_light_theme(self, sample_ohlcv):
        """Test light theme mode."""
        config = PriceChartConfig(theme_mode="light")
        fig = build_price_chart(sample_ohlcv, {}, config)
        
        assert fig is not None
    
    def test_custom_title(self, sample_ohlcv):
        """Test custom chart title."""
        config = PriceChartConfig(title="AAPL - M5")
        fig = build_price_chart(sample_ohlcv, {}, config)
        
        assert fig.layout.title.text == "AAPL - M5"
    
    def test_custom_height(self, sample_ohlcv):
        """Test custom chart height."""
        config = PriceChartConfig(height=800)
        fig = build_price_chart(sample_ohlcv, {}, config)
        
        assert fig.layout.height == 800
    
    def test_grid_enabled(self, sample_ohlcv):
        """Test grid lines enabled."""
        config = PriceChartConfig(show_grid=True)
        fig = build_price_chart(sample_ohlcv, {}, config)
        
        # Verify grid is shown
        assert fig.layout.xaxis.showgrid is True
        assert fig.layout.yaxis.showgrid is True
    
    def test_grid_disabled(self, sample_ohlcv):
        """Test grid lines disabled."""
        config = PriceChartConfig(show_grid=False)
        fig = build_price_chart(sample_ohlcv, {}, config)
        
        assert fig.layout.xaxis.showgrid is False
        assert fig.layout.yaxis.showgrid is False
