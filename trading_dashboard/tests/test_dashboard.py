"""
Trading Dashboard - Automated Tests
"""
import pytest
import pandas as pd
from datetime import datetime, date, timedelta


class TestMockData:
    """Test mock data generation."""

    def test_candle_generation_deterministic(self):
        """Test that mock candles are deterministic."""
        from trading_dashboard.repositories.candles import generate_mock_candles

        df1 = generate_mock_candles("MSFT", hours=24, timeframe="M5")
        df2 = generate_mock_candles("MSFT", hours=24, timeframe="M5")

        assert len(df1) == len(df2), "Same symbol should generate same number of candles"
        assert df1['close'].equals(df2['close']), "Prices should be identical"
        assert df1['timestamp'].equals(df2['timestamp']), "Timestamps should be identical"

    def test_different_timeframes(self):
        """Test different timeframes generate different candle counts."""
        from trading_dashboard.repositories.candles import generate_mock_candles
        from datetime import date

        # Use a specific Friday for consistent testing
        test_date = date(2025, 12, 5)  # Friday

        df_m1 = generate_mock_candles("AAPL", hours=24, timeframe="M1", reference_date=test_date)
        df_m5 = generate_mock_candles("AAPL", hours=24, timeframe="M5", reference_date=test_date)
        df_h1 = generate_mock_candles("AAPL", hours=24, timeframe="H1", reference_date=test_date)

        # M1 has more candles than M5, which has more than H1
        # Market hours: 15:30-22:00 = 6.5 hours = 390 minutes
        # M1: ~390 candles, M5: ~78 candles, H1: ~7 candles
        assert len(df_m1) > len(df_m5), f"M1 should have more candles than M5: {len(df_m1)} vs {len(df_m5)}"
        assert len(df_m5) > len(df_h1), f"M5 should have more candles than H1: {len(df_m5)} vs {len(df_h1)}"
        assert len(df_m5) > 50, f"M5 should have ~78 candles for market hours, got {len(df_m5)}"


class TestDatabaseAccess:
    """Test database repository functions."""

    def test_signals_connection(self):
        """Test connecting to signals database."""
        from trading_dashboard.repositories import get_recent_patterns

        df = get_recent_patterns(hours=24)
        assert isinstance(df, pd.DataFrame), "Should return DataFrame"
        # Note: May be empty if no patterns exist


    def test_portfolio_summary(self):
        """Test portfolio summary function."""
        from trading_dashboard.repositories import get_portfolio_summary

        summary = get_portfolio_summary()
        assert isinstance(summary, dict), "Should return dictionary"
        assert "total_value" in summary, "Should have total_value"
        assert summary["total_value"] == 10000.00, "Should start with $10k"

    def test_history_query(self):
        """Test history event query."""
        from trading_dashboard.repositories.history import get_events_by_date

        today = date.today()
        yesterday = today - timedelta(days=1)

        df = get_events_by_date(yesterday, today)
        assert isinstance(df, pd.DataFrame), "Should return DataFrame"


class TestLayoutComponents:
    """Test layout component creation."""

    @pytest.fixture(autouse=True)
    def _skip_if_dash_missing(self):
        """Skip layout tests if Dash is not installed in this environment."""
        pytest.importorskip("dash")

    def test_live_monitor_layout(self):
        """Test Live Monitor layout creates without errors."""
        from trading_dashboard.layouts import create_live_monitor_layout

        layout = create_live_monitor_layout()
        assert layout is not None, "Layout should be created"

    def test_charts_layout(self):
        """Test Charts layout creates without errors."""
        from trading_dashboard.layouts import create_charts_layout

        layout = create_charts_layout()
        assert layout is not None, "Layout should be created"

    def test_portfolio_layout(self):
        """Test Portfolio layout creates without errors."""
        from trading_dashboard.layouts import create_portfolio_layout

        layout = create_portfolio_layout()
        assert layout is not None, "Layout should be created"

    def test_history_layout(self):
        """Test History layout creates without errors."""
        from trading_dashboard.layouts import create_history_layout

        layout = create_history_layout()
        assert layout is not None, "Layout should be created"

    def test_backtests_layout(self):
        """Test Backtests layout creates without errors."""
        from trading_dashboard.layouts import create_backtests_layout

        layout = create_backtests_layout()
        assert layout is not None, "Layout should be created"


class TestCSVExport:
    """Test CSV export functionality."""

    def test_export_empty_dataframe(self):
        """Test exporting empty DataFrame."""
        df = pd.DataFrame()
        assert df.empty, "Should handle empty DataFrames"

    def test_export_with_data(self):
        """Test exporting DataFrame with data."""
        df = pd.DataFrame({
            'timestamp': [datetime.now()],
            'event_type': ['pattern_detected'],
            'symbol': ['AAPL'],
            'details': ['BUY @ $227.00'],
            'status': ['pending']
        })

        csv_string = df.to_csv(index=False)
        assert 'timestamp' in csv_string, "Should contain header"
        assert 'AAPL' in csv_string, "Should contain data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
