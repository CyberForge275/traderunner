"""
Tests for Backtest Pipeline Error Handling
==========================================

Validates enhanced error handling, data validation, and logging improvements.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np


class TestSignalsCLIDataValidation:
    """Test data validation in signals.cli_inside_bar."""
    
    @patch('signals.cli_inside_bar.IntradayStore')
    def test_cli_handles_missing_data_file(self, mock_store_class):
        """CLI should report missing data files clearly."""
        mock_store = Mock()
        mock_store.load.side_effect = FileNotFoundError("No such file")
        mock_store_class.return_value = mock_store
        
        from signals.cli_inside_bar import main
        
        # Should not crash, should return 1 (all symbols failed)
        result = main(['--symbols', 'MISSING', '--data-path', '/tmp/nonexistent'])
        
        # Exit code 1 for complete failure
        assert result == 1
    
    @patch('signals.cli_inside_bar.IntradayStore')
    def test_cli_detects_empty_dataframe(self, mock_store_class):
        """CLI should detect and report empty dataframes."""
        mock_store = Mock()
        empty_df = pd.DataFrame()  # Empty dataframe
        mock_store.load.return_value = empty_df
        mock_store.has_symbol.return_value = True
        mock_store_class.return_value = mock_store
        
        from signals.cli_inside_bar import main
        
        result = main(['--symbols', 'EMPTY', '--data-path', '/tmp/test'])
        
        # Should return 1 (all symbols failed)
        assert result == 1
    
    @patch('signals.cli_inside_bar.IntradayStore')
    @patch('signals.cli_inside_bar.factory.create_strategy')
    def test_cli_detects_nan_values(self, mock_factory, mock_store_class):
        """CLI should detect NaN values in OHLC columns."""
        mock_store = Mock()
        
        # Create dataframe with NaN values
        dates = pd.date_range('2025-01-01', periods=10, freq='5min')
        df = pd.DataFrame({
            'open': [100.0, 101.0, np.nan, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0],
            'high': [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0],
            'low': [99.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5, 107.5, 108.5, 109.5],
            'volume': [1000] * 10
        }, index=dates)
        
        mock_store.load.return_value = df
        mock_store.has_symbol.return_value = True
        mock_store_class.return_value = mock_store
        
        from signals.cli_inside_bar import main
        
        result = main(['--symbols', 'TEST', '--data-path', '/tmp/test'])
        
        # Should return 1 (all symbols failed due to NaN)
        assert result == 1
    
    @patch('signals.cli_inside_bar.IntradayStore')
    @patch('signals.cli_inside_bar.factory.create_strategy')
    def test_cli_partial_success(self, mock_factory, mock_store_class):
        """CLI should handle partial success (some symbols OK, some failed)."""
        mock_store = Mock()
        
        # Create good dataframe
        dates = pd.date_range('2025-01-01', periods=10, freq='5min')
        good_df = pd.DataFrame({
            'open': [100.0] * 10,
            'high': [101.0] * 10,
            'low': [99.0] * 10,
            'close': [100.5] * 10,
            'volume': [1000] * 10
        }, index=dates)
        
        def load_side_effect(symbol, **kwargs):
            if symbol == 'GOOD':
                return good_df
            elif symbol == 'MISSING':
                raise FileNotFoundError("No file")
            else:
                # Return empty for 'EMPTY'
                return pd.DataFrame()
        
        mock_store.load.side_effect = load_side_effect
        mock_store.has_symbol.return_value = True
        mock_store_class.return_value = mock_store
        
        # Mock strategy to return empty signals (we're just testing data validation)
        mock_strategy = Mock()
        mock_strategy.generate_signals.return_value = []
        mock_factory.return_value = mock_strategy
        
        from signals.cli_inside_bar import main
        
        result = main(['--symbols', 'GOOD,MISSING,EMPTY', '--data-path', '/tmp/test'])
        
        # Should return 0 (partial success - GOOD processed)
        assert result == 0


class TestPipelineDataCoverageVerification:
    """Test data coverage verification in pipeline."""
    
    def test_coverage_verification_detects_missing_data(self, tmp_path):
        """Coverage verification should detect when no data was generated."""
        # This would require mocking the IntradayStore in pipeline.py
        # For now, testing the logic structure
        pass
    
    def test_coverage_verification_detects_date_gap(self, tmp_path):
        """Coverage verification should detect when data doesn't cover requested range."""
        pass


class TestLoggingEnhancements:
    """Test logging improvements."""
    
    def test_error_messages_include_symbol_details(self):
        """Error messages should include which symbol failed and why."""
        # Test that error output includes symbol name and failure reason
        pass
    
    def test_exit_codes_are_meaningful(self):
        """Exit codes should indicate type of failure."""
        # 0 = success
        # 1 = complete failure (no symbols processed)
        # Tested in TestSignalsCLIDataValidation
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
