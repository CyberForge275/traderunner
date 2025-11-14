"""Test data integration and EODHD client functionality."""

import pytest
import pandas as pd
from datetime import date, timedelta
import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data import EODHDClient, DataManager
from data.eodhd_client import get_sample_data


class TestEODHDClient:
    """Test EODHD API client."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.client = EODHDClient()  # Demo mode
    
    def test_client_initialization(self):
        """Test client initialization."""
        assert self.client.api_key == "demo"
        assert self.client.BASE_URL == "https://eodhd.com/api"
    
    def test_sample_data_generation(self):
        """Test sample data generation."""
        data = get_sample_data(symbol="AAPL", days=10)
        
        assert isinstance(data, pd.DataFrame)
        assert len(data) == 10
        assert all(col in data.columns for col in ["timestamp", "open", "high", "low", "close", "volume"])
        
        # Check OHLC relationships
        assert (data["high"] >= data["low"]).all()
        assert (data["high"] >= data["open"]).all()
        assert (data["high"] >= data["close"]).all()
        assert (data["low"] <= data["open"]).all()
        assert (data["low"] <= data["close"]).all()
    
    def test_sample_data_different_symbols(self):
        """Test sample data with different symbols."""
        aapl_data = get_sample_data("AAPL", days=5)
        msft_data = get_sample_data("MSFT", days=5)
        
        # Should generate same structure but potentially different values
        assert len(aapl_data) == len(msft_data)
        assert list(aapl_data.columns) == list(msft_data.columns)


class TestDataManager:
    """Test data manager functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.data_manager = DataManager(data_dir="test_data", cache_enabled=False)
    
    def test_data_manager_initialization(self):
        """Test data manager initialization."""
        assert self.data_manager.cache_enabled is False
        assert self.data_manager.eodhd_client.api_key == "demo"
    
    def test_get_historical_data_sample(self):
        """Test historical data retrieval with sample data."""
        data = self.data_manager.get_historical_data(
            symbol="AAPL",
            use_sample_data=True
        )
        
        assert isinstance(data, pd.DataFrame)
        assert len(data) == 30  # Default 30 days
        assert all(col in data.columns for col in ["timestamp", "open", "high", "low", "close", "volume"])
    
    def test_get_historical_data_date_range(self):
        """Test historical data with specific date range."""
        start_date = date.today() - timedelta(days=10)
        end_date = date.today() - timedelta(days=1)
        
        data = self.data_manager.get_historical_data(
            symbol="MSFT",
            start_date=start_date,
            end_date=end_date,
            use_sample_data=True
        )
        
        assert isinstance(data, pd.DataFrame)
        assert len(data) == 9  # 10 - 1 = 9 days
    
    def test_get_intraday_data_sample(self):
        """Test intraday data retrieval."""
        data = self.data_manager.get_intraday_data(
            symbol="TSLA",
            interval="5m",
            use_sample_data=True
        )
        
        assert isinstance(data, pd.DataFrame)
        assert len(data) > 0
        assert all(col in data.columns for col in ["timestamp", "open", "high", "low", "close", "volume"])
        
        # Check that timestamps are properly spaced (5 minute intervals)
        if len(data) > 1:
            time_diff = data["timestamp"].iloc[1] - data["timestamp"].iloc[0]
            assert time_diff.total_seconds() == 300  # 5 minutes = 300 seconds
    
    def test_get_symbols_list(self):
        """Test symbols list retrieval."""
        symbols = self.data_manager.get_symbols_list()
        
        assert isinstance(symbols, list)
        assert len(symbols) > 0
        assert "AAPL" in symbols
        assert "MSFT" in symbols
    
    def test_data_quality_validation_valid(self):
        """Test data quality validation with valid data."""
        data = self.data_manager.get_historical_data("AAPL", use_sample_data=True)
        validation = self.data_manager.validate_data_quality(data)
        
        assert validation["valid"] is True
        assert validation["row_count"] == 30
        assert validation["date_range_days"] is not None
        assert len(validation["errors"]) == 0
    
    def test_data_quality_validation_invalid(self):
        """Test data quality validation with invalid data."""
        # Create invalid data
        invalid_data = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02"],
            "open": [100, 105],
            "high": [95, 100],  # High < open (invalid)
            "low": [110, 115],   # Low > high (invalid)
            "close": [102, 108]
            # Missing volume column
        })
        
        validation = self.data_manager.validate_data_quality(invalid_data)
        
        assert validation["valid"] is False
        assert len(validation["errors"]) > 0
        assert "Missing columns" in str(validation["errors"])
        assert "invalid OHLC relationships" in str(validation["errors"])
    
    def test_data_quality_validation_empty(self):
        """Test data quality validation with empty data."""
        empty_data = pd.DataFrame()
        validation = self.data_manager.validate_data_quality(empty_data)
        
        assert validation["valid"] is False
        assert "Empty dataset" in validation["errors"]


class TestIntegrationWorkflow:
    """Test complete integration workflow."""
    
    def setup_method(self):
        """Set up integration test fixtures."""
        self.data_manager = DataManager(cache_enabled=False)
    
    def test_complete_data_workflow(self):
        """Test complete data workflow from fetching to validation."""
        symbol = "AAPL"
        
        # 1. Fetch historical data
        historical_data = self.data_manager.get_historical_data(
            symbol=symbol,
            use_sample_data=True
        )
        
        # 2. Validate data quality
        validation = self.data_manager.validate_data_quality(historical_data)
        assert validation["valid"] is True
        
        # 3. Fetch intraday data
        intraday_data = self.data_manager.get_intraday_data(
            symbol=symbol,
            interval="5m",
            use_sample_data=True
        )
        
        # 4. Validate intraday data
        intraday_validation = self.data_manager.validate_data_quality(intraday_data)
        assert intraday_validation["valid"] is True
        
        # 5. Check data consistency
        assert historical_data.columns.tolist() == intraday_data.columns.tolist()
        
        # 6. Verify data can be used for strategy testing
        assert len(historical_data) >= 10  # Enough for strategy testing
        assert len(intraday_data) >= 50   # Enough intraday points
    
    def test_multiple_symbols_workflow(self):
        """Test workflow with multiple symbols."""
        symbols = ["AAPL", "MSFT", "GOOGL"]
        
        all_data = {}
        for symbol in symbols:
            data = self.data_manager.get_historical_data(
                symbol=symbol,
                use_sample_data=True
            )
            validation = self.data_manager.validate_data_quality(data)
            
            assert validation["valid"] is True
            all_data[symbol] = data
        
        # Verify all symbols have data
        assert len(all_data) == 3
        
        # Verify consistent structure across symbols
        first_columns = list(all_data[symbols[0]].columns)
        for symbol in symbols[1:]:
            assert list(all_data[symbol].columns) == first_columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])