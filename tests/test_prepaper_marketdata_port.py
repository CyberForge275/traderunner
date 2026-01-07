"""
Guard Tests for PrePaper MarketData Port

Validates that PrePaper:
1. NEVER opens signals.db directly (sqlite3.connect guard)
2. NEVER imports from axiom_bt/data (import guard)
3. ONLY uses marketdata_service interface
"""

import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_prepaper_never_opens_signals_db(monkeypatch):
    """
    PrePaper must NEVER call sqlite3.connect.
    
    All DB access must go through marketdata_service.
    """
    # Monkeypatch sqlite3.connect to fail if called
    def _forbidden_sqlite_connect(*args, **kwargs):
        raise AssertionError(
            "FORBIDDEN: PrePaper tried to open SQLite DB directly! "
            "Use marketdata_service.signals_write/query instead."
        )
    
    import sqlite3
    monkeypatch.setattr(sqlite3, "connect", _forbidden_sqlite_connect)
    
    # Import PrePaperMarketDataPort (should work without DB access)
    from pre_paper.marketdata_port import PrePaperMarketDataPort
    
    # Create port with fake service (no DB calls)
    from unittest.mock import AsyncMock
    fake_service = AsyncMock()
    port = PrePaperMarketDataPort(fake_service)
    
    # Assert: import succeeded without triggering sqlite3.connect
    assert port is not None


def test_prepaper_uses_marketdata_service_only():
    """
    PrePaper port must use ONLY marketdata_service interface.
    """
    from pre_paper.marketdata_port import PrePaperMarketDataPort
    from unittest.mock import AsyncMock
    
    # Create mock service
    mock_service = AsyncMock()
    port = PrePaperMarketDataPort(mock_service)
    
    # Assert: port wraps service correctly
    assert port.service is mock_service
    
    # Assert: has required methods
    assert hasattr(port, "get_replay_bars")
    assert hasattr(port, "ensure_features")
    assert hasattr(port, "write_signals")
    assert hasattr(port, "query_signals")
    assert hasattr(port, "open_feed")


@pytest.mark.asyncio
async def test_prepaper_smoke_replay_with_fake_service():
    """
    Smoke test: PrePaper can run replay mode with FakeMarketDataService.
    """
    # Add marketdata-monorepo to path
    monorepo_path = Path(__file__).parent.parent.parent / "marketdata-monorepo" / "src"
    if monorepo_path.exists() and str(monorepo_path) not in sys.path:
        sys.path.insert(0, str(monorepo_path))
    
    from marketdata_service import FakeMarketDataService
    from pre_paper.marketdata_port import PrePaperMarketDataPort
    from datetime import datetime, timezone
    
    # Create fake service
    fake_service = FakeMarketDataService(emit_ticks=False, bars_count=10)
    
    # Create port
    port = PrePaperMarketDataPort(fake_service)
    
    # Get replay bars
    start = datetime(2025, 1, 1, 9, 30, tzinfo=timezone.utc)
    end = datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc)
    
    response = await port.get_replay_bars(
        symbol="AAPL",
        start=start,
        end=end,
        timeframe="M1"
    )
    
    # Assert: bars returned
    assert len(response.bars) > 0
    assert response.provenance.data_hash is not None
    assert response.provenance.source == "fake"


@pytest.mark.asyncio
async def test_prepaper_signals_write_read_roundtrip():
    """
    Test signals write + query roundtrip via port.
    """
    monorepo_path = Path(__file__).parent.parent.parent / "marketdata-monorepo" / "src"
    if monorepo_path.exists() and str(monorepo_path) not in sys.path:
        sys.path.insert(0, str(monorepo_path))
    
    from marketdata_service import FakeMarketDataService
    from pre_paper.marketdata_port import PrePaperMarketDataPort
    
    # Create fake service
    fake_service = FakeMarketDataService()
    port = PrePaperMarketDataPort(fake_service)
    
    # Write signals
    signals = [
        {
            "symbol": "TSLA",
            "ts": "2025-01-01T10:30:00+00:00",
            "side": "BUY",
            "idempotency_key": "test_sig_1"
        }
    ]
    
    write_result = await port.write_signals(
        lab="PREPAPER",
        run_id="test_run_123",
        source_tag="test",
        signals=signals
    )
    
    assert write_result.written == 1
    assert write_result.duplicates_skipped == 0
    
    # Query signals
    results = await port.query_signals(
        lab="PREPAPER",
        run_id="test_run_123"
    )
    
    assert len(results) == 1
    assert results[0].symbol == "TSLA"
    assert results[0].source_tag == "test"


def test_prepaper_no_axiom_bt_data_imports():
    """
    PrePaper modules must NEVER import from axiom_bt/data.
    
    This guard prevents cross-contamination.
    """
    # Import PrePaper modules
    from pre_paper import marketdata_port
    
    # Check module source
    port_source = Path(marketdata_port.__file__).read_text()
    
    # Assert: NO axiom_bt imports
    forbidden_imports = [
        "from axiom_bt.data",
        "import axiom_bt.data",
        "from src.axiom_bt.data",
    ]
    
    for forbidden in forbidden_imports:
        assert forbidden not in port_source, \
            f"FORBIDDEN: PrePaper imports from axiom_bt/data! Found: {forbidden}"
    
    # Assert: Uses marketdata_service instead
    assert "from marketdata_service import" in port_source or \
           "import marketdata_service" in port_source
