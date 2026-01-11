"""Tests for OhlcvRequest validation rules.

Critical validation rules:
- Full-Load (start=None, end=None) MUST have warmup_bars=None
- Window-Load (start/end set) MUST have explicit warmup_bars (0 allowed)
- Partial windows (only start OR end) are forbidden
- warmup_bars < 0 is forbidden
"""

import pytest
import pandas as pd

from trading_dashboard.providers.ohlcv_contract import OhlcvRequest


class TestFullLoadValidation:
    """Test Full-Load (no start/end) validation rules."""
    
    def test_full_load_without_warmup_passes(self):
        """Full-Load with warmup=None is valid."""
        req = OhlcvRequest(
            symbol="PLTR",
            timeframe="M5",
            warmup_bars=None
        )
        # Should NOT raise
        req.validate()
    
    def test_full_load_with_warmup_zero_fails(self):
        """Full-Load with warmup=0 is INVALID."""
        req = OhlcvRequest(
            symbol="PLTR",
            timeframe="M5",
            warmup_bars=0
        )
        with pytest.raises(ValueError, match="Full-Load.*MUST have warmup_bars=None"):
            req.validate()
    
    def test_full_load_with_warmup_positive_fails(self):
        """Full-Load with warmup=20 is INVALID."""
        req = OhlcvRequest(
            symbol="PLTR",
            timeframe="M5",
            warmup_bars=20
        )
        with pytest.raises(ValueError, match="Full-Load.*MUST have warmup_bars=None"):
            req.validate()


class TestWindowLoadValidation:
    """Test Window-Load (start/end set) validation rules."""
    
    def test_window_load_without_warmup_fails(self):
        """Window-Load without warmup is INVALID."""
        req = OhlcvRequest(
            symbol="PLTR",
            timeframe="M5",
            start=pd.Timestamp("2024-12-01", tz="America/New_York"),
            end=pd.Timestamp("2024-12-10", tz="America/New_York"),
            warmup_bars=None
        )
        with pytest.raises(ValueError, match="MUST have explicit warmup_bars"):
            req.validate()
    
    def test_window_load_with_warmup_zero_passes(self):
        """Window-Load with warmup=0 is valid."""
        req = OhlcvRequest(
            symbol="PLTR",
            timeframe="M5",
            start=pd.Timestamp("2024-12-01", tz="America/New_York"),
            end=pd.Timestamp("2024-12-10", tz="America/New_York"),
            warmup_bars=0
        )
        # Should NOT raise
        req.validate()
    
    def test_window_load_with_warmup_positive_passes(self):
        """Window-Load with warmup=20 is valid."""
        req = OhlcvRequest(
            symbol="PLTR",
            timeframe="M5",
            start=pd.Timestamp("2024-12-01", tz="America/New_York"),
            end=pd.Timestamp("2024-12-10", tz="America/New_York"),
            warmup_bars=20
        )
        # Should NOT raise
        req.validate()


class TestPartialWindowValidation:
    """Test that partial windows (only start OR end) are forbidden."""
    
    def test_start_without_end_fails(self):
        """start without end is INVALID."""
        req = OhlcvRequest(
            symbol="PLTR",
            timeframe="M5",
            start=pd.Timestamp("2024-12-01", tz="America/New_York"),
            end=None,
            warmup_bars=0
        )
        with pytest.raises(ValueError, match="start/end must both be set"):
            req.validate()
    
    def test_end_without_start_fails(self):
        """end without start is INVALID."""
        req = OhlcvRequest(
            symbol="PLTR",
            timeframe="M5",
            start=None,
            end=pd.Timestamp("2024-12-10", tz="America/New_York"),
            warmup_bars=0
        )
        with pytest.raises(ValueError, match="start/end must both be set"):
            req.validate()


class TestWarmupValueValidation:
    """Test warmup_bars value constraints."""
    
    def test_negative_warmup_fails(self):
        """warmup_bars < 0 is INVALID."""
        req = OhlcvRequest(
            symbol="PLTR",
            timeframe="M5",
            start=pd.Timestamp("2024-12-01", tz="America/New_York"),
            end=pd.Timestamp("2024-12-10", tz="America/New_York"),
            warmup_bars=-5
        )
        with pytest.raises(ValueError, match="warmup_bars must be >= 0"):
            req.validate()
    
    def test_large_warmup_passes(self):
        """Large positive warmup is valid for Window-Load."""
        req = OhlcvRequest(
            symbol="PLTR",
            timeframe="M5",
            start=pd.Timestamp("2024-12-01", tz="America/New_York"),
            end=pd.Timestamp("2024-12-10", tz="America/New_York"),
            warmup_bars=1000
        )
        # Should NOT raise
        req.validate()
