"""
Unit tests for visualization layer configuration models.
"""
import pytest
from visualization.plotly.config import PriceChartConfig, VolumeProfileConfig


class TestPriceChartConfig:
    """Tests for PriceChartConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = PriceChartConfig()
        
        assert config.show_volume is True
        assert config.show_grid is True
        assert config.show_rangeslider is False
        assert config.session_mode == "rth"
        assert config.theme_mode == "dark"
        assert config.height == 600
        assert config.show_patterns is False
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = PriceChartConfig(
            show_volume=False,
            session_mode="all",
            theme_mode="light",
            title="Test Chart",
            height=800,
        )
        
        assert config.show_volume is False
        assert config.session_mode == "all"
        assert config.theme_mode == "light"
        assert config.title == "Test Chart"
        assert config.height == 800
    
    def test_immutability(self):
        """Test that config is immutable (frozen dataclass)."""
        config = PriceChartConfig()
        
        with pytest.raises(Exception):  # FrozenInstanceError
            config.show_volume = False  # type: ignore
    
    def test_height_validation_too_small(self):
        """Test height validation rejects values < 100."""
        with pytest.raises(ValueError, match="height must be >= 100"):
            PriceChartConfig(height=50)
    
    def test_height_validation_too_large(self):
        """Test height validation rejects values > 5000."""
        with pytest.raises(ValueError, match="height must be <= 5000"):
            PriceChartConfig(height=10000)
    
    def test_height_validation_valid(self):
        """Test height validation accepts valid values."""
        # Should not raise
        PriceChartConfig(height=100)
        PriceChartConfig(height=600)
        PriceChartConfig(height=5000)
    
    def test_invalid_session_mode(self):
        """Test session mode validation."""
        with pytest.raises(ValueError, match="Invalid session_mode"):
            PriceChartConfig(session_mode="invalid")  # type: ignore
    
    def test_valid_session_modes(self):
        """Test all valid session modes."""
        # Should not raise
        PriceChartConfig(session_mode="all")
        PriceChartConfig(session_mode="rth")
        PriceChartConfig(session_mode="premarket_rth")
        PriceChartConfig(session_mode="all_extended")
    
    def test_indicator_configs(self):
        """Test indicator configuration."""
        config = PriceChartConfig(
            indicator_configs={
                "ma_20": {"period": 20, "color": "blue"},
                "ma_50": {"period": 50, "color": "orange"},
            }
        )
        
        assert len(config.indicator_configs) == 2
        assert config.indicator_configs["ma_20"]["period"] == 20


class TestVolumeProfileConfig:
    """Tests for VolumeProfileConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = VolumeProfileConfig()
        
        assert config.bins == 50
        assert config.show_poc is True
        assert config.show_value_area is True
        assert config.theme_mode == "dark"
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = VolumeProfileConfig(
            bins=100,
            show_poc=False,
            theme_mode="light",
        )
        
        assert config.bins == 100
        assert config.show_poc is False
        assert config.theme_mode == "light"
    
    def test_immutability(self):
        """Test that config is immutable."""
        config = VolumeProfileConfig()
        
        with pytest.raises(Exception):
            config.bins = 100  # type: ignore
    
    def test_bins_validation_too_small(self):
        """Test bins validation rejects values < 10."""
        with pytest.raises(ValueError, match="bins must be >= 10"):
            VolumeProfileConfig(bins=5)
    
    def test_bins_validation_too_large(self):
        """Test bins validation rejects values > 200."""
        with pytest.raises(ValueError, match="bins must be <= 200"):
            VolumeProfileConfig(bins=500)
    
    def test_bins_validation_valid(self):
        """Test bins validation accepts valid values."""
        # Should not raise
        VolumeProfileConfig(bins=10)
        VolumeProfileConfig(bins=50)
        VolumeProfileConfig(bins=200)
