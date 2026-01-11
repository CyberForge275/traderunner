"""Baseline verification test - ensures provider refactor is non-breaking.

Verifies that AxiomBtProvider returns identical data to baseline fingerprint
created in S0.
"""

import pytest
import json
import pandas as pd
from pathlib import Path

from trading_dashboard.providers.axiom_bt_provider import AxiomBtProvider
from trading_dashboard.providers.ohlcv_contract import OhlcvRequest


@pytest.fixture
def baseline_fingerprint():
    """Load baseline fingerprint from S0."""
    baseline_path = Path("docs/migration/baseline_ui_full_load.json")
    
    if not baseline_path.exists():
        pytest.skip(f"Baseline not found: {baseline_path}")
    
    with open(baseline_path) as f:
        return json.load(f)


class TestBaselineMatch:
    """Verify AxiomBtProvider matches baseline fingerprint."""
    
    def test_axiom_provider_matches_baseline(self, baseline_fingerprint):
        """AxiomBtProvider returns identical data to baseline."""
        # Load via provider (same as S0 baseline generation)
        provider = AxiomBtProvider()
        req = OhlcvRequest(
            symbol=baseline_fingerprint["symbol"],
            timeframe=baseline_fingerprint["timeframe"],
            tz=None,  # Default (same as baseline)
            start=None,
            end=None,
            warmup_bars=None,
            session_mode=None  # Default (same as baseline)
        )
        
        df, meta = provider.get_ohlcv(req)
        
        # Take same slice as baseline (last 800 bars)
        df_slice = df.tail(baseline_fingerprint["row_count"])
        
       # Verify row count
        assert len(df_slice) == baseline_fingerprint["row_count"], \
            f"Row count mismatch: expected {baseline_fingerprint['row_count']}, got {len(df_slice)}"
        
        # Verify timestamp range
        assert str(df_slice.index[0]) == baseline_fingerprint["first_ts"], \
            f"First timestamp mismatch: expected {baseline_fingerprint['first_ts']}, got {df_slice.index[0]}"
        assert str(df_slice.index[-1]) == baseline_fingerprint["last_ts"], \
            f"Last timestamp mismatch: expected {baseline_fingerprint['last_ts']}, got {df_slice.index[-1]}"
        
        # Verify data hash (CRITICAL: proves data is identical)
        data_hash = int(pd.util.hash_pandas_object(df_slice[['open', 'high', 'low', 'close', 'volume']]).sum())
        assert data_hash == baseline_fingerprint["data_hash"], \
            f"Data hash mismatch: expected {baseline_fingerprint['data_hash']}, got {data_hash}. " \
            f"This indicates data content has changed!"
        
        # Verify metadata
        assert meta.provider_id == "axiom_bt"
        assert meta.source_effective == "IntradayStore"
        assert len(meta.warnings) == 0
    
    def test_full_load_returns_all_data(self):
        """Full-Load returns complete dataset (no windowing)."""
        provider = AxiomBtProvider()
        req = OhlcvRequest(
            symbol="PLTR",
            timeframe="M5",
            tz=None,
            start=None,  # Full-Load
            end=None,
            warmup_bars=None,
            session_mode=None
        )
        
        df, meta = provider.get_ohlcv(req)
        
        # Full-Load should return many rows (all available data)
        assert len(df) > 800, f"Full-Load should return >800 rows, got {len(df)}"
        assert meta.row_count_total == len(df)
