"""
Session Mode Tests - Cache Separation and RTH Validation

Tests the configurable session_mode feature:
1. Cache key separation (RTH vs ALL use different files)
2. RTH validation gate (files labeled _rth must contain only RTH data)
"""
import pandas as pd
import pytest
from pathlib import Path
from datetime import time

from axiom_bt.intraday import IntradayStore, Timeframe


class TestSessionModeCacheSeparation:
    """Test that RTH and ALL modes use separate cache files."""
    
    def test_cache_key_separation(self):
        """Verify RTH and ALL use different filenames"""
        store = IntradayStore()
        
        # RTH path
        path_rth = store.path_for("HOOD", timeframe=Timeframe.M5, session_mode="rth")
        assert path_rth.name == "HOOD_rth.parquet", f"Expected HOOD_rth.parquet, got {path_rth.name}"

        
        # ALL path
        path_all = store.path_for("HOOD", timeframe=Timeframe.M5, session_mode="all")
        assert path_all.name == "HOOD_all.parquet", f"Expected HOOD_all.parquet, got {path_all.name}"
        
        # Different files - no collision
        assert path_rth != path_all, "RTH and ALL must use separate cache files"
    
    def test_default_session_mode_is_rth(self):
        """Verify default session_mode is rth for backward compatibility"""
        store = IntradayStore()
        
        path_default = store.path_for("TSLA", timeframe=Timeframe.M1)
        assert path_default.name == "TSLA_rth.parquet", "Default should be RTH mode"
    
    def test_cache_key_separation_all_timeframes(self):
        """Verify cache separation works for M1, M5, M15"""
        store = IntradayStore()
        
        for tf in [Timeframe.M1, Timeframe.M5, Timeframe.M15]:
            path_rth = store.path_for("AAPL", timeframe=tf, session_mode="rth")
            path_all = store.path_for("AAPL", timeframe=tf, session_mode="all")
            
            assert "_rth" in path_rth.name
            assert "_all" in path_all.name
            assert path_rth != path_all


class TestRTHValidationGate:
    """Test RTH validation gate for _rth labeled files."""
    
    def test_rth_validation_rejects_pre_market(self, tmp_path):
        """RTH validation should reject Pre-Market data in _rth file"""
        # Create fake _rth file with Pre-Market data (04:00 NY)
        timestamps = pd.date_range(
            "2025-01-15 04:00",
            periods=10,
            freq="5min",
            tz="America/New_York"
        )
        df = pd.DataFrame({
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "volume": 1000
        }, index=timestamps)
        
        # Write as _rth file (mislabeled!)
        fake_path = tmp_path / "FAKE_rth.parquet"
        df.to_parquet(fake_path)
        
        # Monkey-patch IntradayStore to use tmp_path
        from axiom_bt.fs import DATA_M5
        import axiom_bt.intraday as intraday_mod
        
        original_path_for = IntradayStore.path_for
        
        def mock_path_for(self, symbol, *, timeframe, session_mode="rth"):
            if symbol == "FAKE":
                return fake_path
            return original_path_for(self, symbol, timeframe=timeframe, session_mode=session_mode)
        
        try:
            IntradayStore.path_for = mock_path_for
            store = IntradayStore()
            
            # This should raise ValueError due to RTH violation
            with pytest.raises(ValueError, match="RTH Violation.*10 non-RTH bars"):
                store.load("FAKE", timeframe=Timeframe.M5, session_mode="rth")
        
        finally:
            IntradayStore.path_for = original_path_for
    
    def test_rth_validation_accepts_rth_only_data(self, tmp_path):
        """RTH validation should accept data within 09:30-16:00 NY"""
        # Create RTH-only data (10:00-11:00 NY)
        timestamps = pd.date_range(
            "2025-01-15 10:00",
            periods=12,
            freq="5min",
            tz="America/New_York"
        )
        df = pd.DataFrame({
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "volume": 1000
        }, index=timestamps)
        
        # Write as _rth file
        valid_path = tmp_path / "VALID_rth.parquet"
        df.to_parquet(valid_path)
        
        # Monkey-patch
        original_path_for = IntradayStore.path_for
        
        def mock_path_for(self, symbol, *, timeframe, session_mode="rth"):
            if symbol == "VALID":
                return valid_path
            return original_path_for(self, symbol, timeframe=timeframe, session_mode=session_mode)
        
        try:
            IntradayStore.path_for = mock_path_for
            store = IntradayStore()
            
            # This should NOT raise (valid RTH data)
            result = store.load("VALID", timeframe=Timeframe.M5, session_mode="rth")
            assert not result.empty
            assert len(result) == 12
        
        finally:
            IntradayStore.path_for = original_path_for
    
    def test_all_mode_does_not_validate(self, tmp_path):
        """ALL mode should not enforce RTH validation even for _all files"""
        # Create Pre-Market data
        timestamps = pd.date_range(
            "2025-01-15 04:00",
            periods=10,
            freq="5min",
            tz="America/New_York"
        )
        df = pd.DataFrame({
            "open": 100,
            "high": 101,
            "low": 99,
            "close": 100,
            "volume": 1000
        }, index=timestamps)
        
        # Write as _all file (correctly labeled)
        all_path = tmp_path / "PREMARKET_all.parquet"
        df.to_parquet(all_path)
        
        # Monkey-patch
        original_path_for = IntradayStore.path_for
        
        def mock_path_for(self, symbol, *, timeframe, session_mode="rth"):
            if symbol == "PREMARKET":
                return all_path
            return original_path_for(self, symbol, timeframe=timeframe, session_mode=session_mode)
        
        try:
            IntradayStore.path_for = mock_path_for
            store = IntradayStore()
            
            # This should NOT raise (ALL mode, no validation)
            result = store.load("PREMARKET", timeframe=Timeframe.M5, session_mode="all")
            assert not result.empty
        
        finally:
            IntradayStore.path_for = original_path_for


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
