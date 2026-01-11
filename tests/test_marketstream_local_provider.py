"""Tests for marketstream_local Provider (S2a).

Hermetic tests using tmp_path - no network, no real EODHD data dependency.
"""

import pytest
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

from trading_dashboard.providers.marketstream_local_provider import MarketstreamLocalProvider
from trading_dashboard.providers.ohlcv_contract import OhlcvRequest


@pytest.fixture
def temp_data_root(tmp_path):
    """Create temporary MARKETDATA_DATA_ROOT structure."""
    data_root = tmp_path / "marketdata"
    data_root.mkdir()
    return data_root


@pytest.fixture
def sample_parquet_rth(temp_data_root):
    """Create sample PLTR_rth.parquet file."""
    # Create directory structure
    m5_dir = temp_data_root / "eodhd_http" / "m5"
    m5_dir.mkdir(parents=True)
    
    # Create sample dataframe (RTH bars)
    index = pd.date_range(
        start="2025-01-02 14:30",  # 09:30 ET
        periods=50,
        freq="5min",
        tz="UTC"
    )
    df = pd.DataFrame({
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1000,
    }, index=index)
    
    # Write parquet
    parquet_path = m5_dir / "PLTR_rth.parquet"
    df.to_parquet(parquet_path)
    
    return parquet_path, df


@pytest.fixture
def sample_parquet_raw(temp_data_root):
    """Create sample PLTR_raw.parquet file."""
    m5_dir = temp_data_root / "eodhd_http" / "m5"
    m5_dir.mkdir(parents=True, exist_ok=True)
    
    # Create sample dataframe (RAW - includes pre/after market)
    index = pd.date_range(
        start="2025-01-02 12:00",  # 07:00 ET (pre-market)
        periods=100,
        freq="5min",
        tz="UTC"
    )
    df = pd.DataFrame({
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 500,  # Lower volume in pre-market
    }, index=index)
    
    parquet_path = m5_dir / "PLTR_raw.parquet"
    df.to_parquet(parquet_path)
    
    return parquet_path, df


def test_provider_loads_rth_parquet(temp_data_root, sample_parquet_rth):
    """S2a: Provider loads RTH parquet file successfully."""
    provider = MarketstreamLocalProvider(data_root=str(temp_data_root))
    
    request = OhlcvRequest(
        symbol="PLTR",
        timeframe="M5",
        session_mode="rth",
        start=None,
        end=None,
        warmup_bars=None,
        tz=None,
    )
    
    df, metadata = provider.get_ohlcv(request)
    
    # Verify data loaded
    assert len(df) == 50
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is not None  # TZ-aware
    
    # Verify metadata
    assert metadata["provider_id"] == "marketstream_local"
    assert metadata["symbol"] == "PLTR"
    assert metadata["timeframe"] == "m5"  # Normalized to lowercase
    assert metadata["session_mode"] == "rth"
    assert metadata["row_count"] == 50


def test_provider_loads_raw_session_mode(temp_data_root, sample_parquet_raw):
    """S2a: Provider loads RAW session mode parquet."""
    provider = MarketstreamLocalProvider(data_root=str(temp_data_root))
    
    request = OhlcvRequest(
        symbol="PLTR",
        timeframe="M5",
        session_mode="raw",
        start=None,
        end=None,
        warmup_bars=None,
        tz=None,
    )
    
    df, metadata = provider.get_ohlcv(request)
    
    assert len(df) == 100
    assert metadata["session_mode"] == "raw"


def test_provider_defaults_session_mode_to_rth(temp_data_root, sample_parquet_rth):
    """S2a: Provider defaults to 'rth' if session_mode=None."""
    provider = MarketstreamLocalProvider(data_root=str(temp_data_root))
    
    request = OhlcvRequest(
        symbol="PLTR",
        timeframe="M5",
        session_mode=None,  # Not specified
        start=None,
        end=None,
        warmup_bars=None,
        tz=None,
    )
    
    df, metadata = provider.get_ohlcv(request)
    
    assert len(df) == 50
    assert metadata["session_mode"] == "rth"


def test_provider_converts_tz(temp_data_root, sample_parquet_rth):
    """S2a: Provider converts index TZ when requested."""
    provider = MarketstreamLocalProvider(data_root=str(temp_data_root))
    
    request = OhlcvRequest(
        symbol="PLTR",
        timeframe="M5",
        session_mode="rth",
        start=None,
        end=None,
        warmup_bars=None,
        tz="America/New_York",
    )
    
    df, metadata = provider.get_ohlcv(request)
    
    # Verify TZ conversion
    assert str(df.index.tz) == "America/New_York"
    assert metadata["tz"] == "America/New_York"


def test_provider_raises_on_window_load(temp_data_root, sample_parquet_rth):
    """S2a restriction: Raises ValueError on Window-Load (start/end set)."""
    provider = MarketstreamLocalProvider(data_root=str(temp_data_root))
    
    request = OhlcvRequest(
        symbol="PLTR",
        timeframe="M5",
        session_mode="rth",
        start=datetime(2025, 1, 2, 14, 30, tzinfo=timezone.utc),
        end=datetime(2025, 1, 2, 20, 0, tzinfo=timezone.utc),
        warmup_bars=0,  # Window-Load requires explicit warmup_bars
        tz=None,
    )
    
    with pytest.raises(ValueError, match="Window-load not supported in S2a"):
        provider.get_ohlcv(request)


def test_provider_raises_on_missing_file(temp_data_root):
    """S2a: Raises FileNotFoundError if parquet doesn't exist."""
    provider = MarketstreamLocalProvider(data_root=str(temp_data_root))
    
    request = OhlcvRequest(
        symbol="NONEXISTENT",
        timeframe="M5",
        session_mode="rth",
        start=None,
        end=None,
        warmup_bars=None,
        tz=None,
    )
    
    with pytest.raises(FileNotFoundError, match="Parquet file not found"):
        provider.get_ohlcv(request)


def test_provider_raises_if_data_root_not_set():
    """S2a: Raises ValueError if MARKETDATA_DATA_ROOT not set and data_root=None."""
    import os
    
    # Temporarily unset ENV (if set)
    original = os.environ.get("MARKETDATA_DATA_ROOT")
    if "MARKETDATA_DATA_ROOT" in os.environ:
        del os.environ["MARKETDATA_DATA_ROOT"]
    
    try:
        with pytest.raises(ValueError, match="MARKETDATA_DATA_ROOT environment variable not set"):
            MarketstreamLocalProvider()
    finally:
        # Restore original ENV
        if original:
            os.environ["MARKETDATA_DATA_ROOT"] = original


def test_provider_normalizes_timeframe_case(temp_data_root, sample_parquet_rth):
    """S2a: Provider normalizes timeframe to lowercase (M5 → m5)."""
    provider = MarketstreamLocalProvider(data_root=str(temp_data_root))
    
    request = OhlcvRequest(
        symbol="PLTR",
        timeframe="M5",  # Uppercase
        session_mode="rth",
        start=None,
        end=None,
        warmup_bars=None,
        tz=None,
    )
    
    df, metadata = provider.get_ohlcv(request)
    
    # Should load from m5/ directory (lowercase)
    assert len(df) == 50
    assert metadata["timeframe"] == "m5"
