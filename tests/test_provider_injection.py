"""Tests for provider injection and resolver integration.

Proves that:
1. Resolver accepts injected providers
2. Resolver uses the injected provider (not default)
3. Full-Load requests work end-to-end
"""

import pytest
import pandas as pd
from typing import Tuple

from trading_dashboard.resolvers.timeframe_resolver import BacktestingTimeframeResolver
from trading_dashboard.providers.ohlcv_contract import OhlcvRequest, OhlcvMeta, OhlcvProvider


class FakeProvider:
    """Fake provider for testing injection."""
    
    def __init__(self, fixture_data: pd.DataFrame):
        """Initialize with fixture data to return."""
        self.fixture_data = fixture_data
        self.calls = []  # Track calls for verification
    
    def get_ohlcv(self, req: OhlcvRequest) -> Tuple[pd.DataFrame, OhlcvMeta]:
        """Return fixture data and track call."""
        # Validate request
        req.validate()
        
        # Track call
        self.calls.append({
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "tz": req.tz,
            "warmup_bars": req.warmup_bars
        })
        
        meta = OhlcvMeta(
            provider_id="fake",
            source_effective="test_fixture",
            row_count_total=len(self.fixture_data),
            warnings=[]
        )
        
        return self.fixture_data.copy(), meta


@pytest.fixture
def fake_fixture_data():
    """Create fake OHLCV data for testing."""
    data = {
        'open': [100.0, 101.0, 102.0],
        'high': [101.0, 102.0, 103.0],
        'low': [99.0, 100.0, 101.0],
        'close': [100.5, 101.5, 102.5],
        'volume': [1000, 1100, 1200]
    }
    index = pd.DatetimeIndex([
        pd.Timestamp("2024-12-01 09:30", tz="America/New_York"),
        pd.Timestamp("2024-12-01 09:35", tz="America/New_York"),
        pd.Timestamp("2024-12-01 09:40", tz="America/New_York"),
    ])
    return pd.DataFrame(data, index=index)


class TestProviderInjection:
    """Test that resolver uses injected provider."""
    
    def test_resolver_accepts_injected_provider(self, fake_fixture_data):
        """Resolver accepts provider in constructor."""
        fake = FakeProvider(fake_fixture_data)
        resolver = BacktestingTimeframeResolver(ohlcv_provider=fake)
        
        assert resolver.ohlcv_provider is fake
    
    def test_resolver_uses_injected_provider(self, fake_fixture_data):
        """Resolver delegates to injected provider."""
        fake = FakeProvider(fake_fixture_data)
        resolver = BacktestingTimeframeResolver(ohlcv_provider=fake)
        
        # Load data
        df = resolver.load("PLTR", "M5")
        
        # Verify: fake provider was called
        assert len(fake.calls) == 1
        assert fake.calls[0]["symbol"] == "PLTR"
        assert fake.calls[0]["timeframe"] == "M5"
        assert fake.calls[0]["warmup_bars"] is None  # Full-Load
        
        # Verify: returned fixture data
        assert len(df) == 3
        assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
    
    def test_resolver_enforces_full_load_request(self, fake_fixture_data):
        """Resolver creates Full-Load requests (warmup_bars=None)."""
        fake = FakeProvider(fake_fixture_data)
        resolver = BacktestingTimeframeResolver(ohlcv_provider=fake)
        
        # Load data
        resolver.load("TSLA", "M1", tz="America/New_York")
        
        # Verify: Full-Load semantics
        assert len(fake.calls) == 1
        call = fake.calls[0]
        assert call["symbol"] == "TSLA"
        assert call["timeframe"] == "M1"
        assert call["tz"] == "America/New_York"
        assert call["warmup_bars"] is None  # CRITICAL: UI cannot set warmup


class TestDefaultProvider:
    """Test that resolver defaults to AxiomBtProvider when no provider injected."""
    
    def test_resolver_defaults_to_axiom_bt_provider(self):
        """Resolver uses AxiomBtProvider by default."""
        from trading_dashboard.providers.axiom_bt_provider import AxiomBtProvider
        
        resolver = BacktestingTimeframeResolver()
        
        assert isinstance(resolver.ohlcv_provider, AxiomBtProvider)
