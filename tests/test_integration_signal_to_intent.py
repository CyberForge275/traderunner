"""
Integration test for signal generation → order intent creation flow.

Tests the full pipeline:
1. Generate signal CSV from strategy
2. Use paper_trading_adapter to send to automatictrader-api
3. Verify intent created in database
4. Test idempotency and error handling
"""
import json
import os
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

import pandas as pd
import pytest
import requests

# automatictrader-api project path (adjust if needed)
API_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent / "automatictrader-api"
API_DB_PATH = API_PROJECT_ROOT / "data" / "test_automatictrader.db"


@pytest.fixture(scope="module")
def api_service():
    """
    Start automatictrader-api in test mode for integration testing.
    """
    # Set up test environment
    env = os.environ.copy()
    env["AT_DB_PATH"] = str(API_DB_PATH)
    env["AT_BEARER_TOKEN"] = ""  # No auth for testing
    env["AT_LOG_LEVEL"] = "INFO"
    
    # Clean up old test database
    if API_DB_PATH.exists():
        API_DB_PATH.unlink()
    API_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Start the API service
    api_process = subprocess.Popen(
        ["python", "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8888"],
        cwd=str(API_PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for service to be ready
    max_wait = 10
    for i in range(max_wait):
        try:
            resp = requests.get("http://localhost:8888/healthz", timeout=1)
            if resp.status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(1)
    else:
        api_process.kill()
        pytest.fail("automatictrader-api failed to start within 10 seconds")
    
    yield "http://localhost:8888"
    
    # Cleanup
    api_process.terminate()
    api_process.wait(timeout=5)
    if API_DB_PATH.exists():
        API_DB_PATH.unlink()


@pytest.fixture
def test_signal_csv(tmp_path):
    """Create a test signal CSV file"""
    csv_path = tmp_path / "test_signals.csv"
    
    # Create sample signals
    signals = pd.DataFrame([
        {
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 10,
            "order_type": "LMT",
            "price": 227.50,
            "source": "test_strategy",
            "timestamp": "2024-12-01T10:00:00Z"
        },
        {
            "symbol": "MSFT",
            "side": "SELL",
            "qty": 5,
            "order_type": "LMT",
            "price": 420.25,
            "source": "test_strategy",
            "timestamp": "2024-12-01T10:05:00Z"
        }
    ])
    
    signals.to_csv(csv_path, index=False)
    return csv_path


def test_api_health_check(api_service):
    """Test that the API is running and healthy"""
    resp = requests.get(f"{api_service}/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


def test_signal_to_intent_flow(api_service, test_signal_csv):
    """
    Test full signal → intent flow using paper_trading_adapter
    """
    from trade.paper_trading_adapter import PaperTradingAdapter
    
    # Create adapter
    adapter = PaperTradingAdapter(api_url=api_service, timeout=5)
    
    # Verify API is reachable
    assert adapter.health_check(), "API health check failed"
    
    # Send signals
    results = adapter.send_signals_from_csv(test_signal_csv)
    
    # Verify results
    assert "error" not in results
    assert results["total"] == 2
    assert results["created"] == 2
    assert results["duplicates"] == 0
    assert results["errors"] == 0
    assert results["skipped"] == 0
    
    # Verify intents in database
    conn = sqlite3.connect(str(API_DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM order_intents ORDER BY created_at")
    intents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    assert len(intents) == 2
    
    # Check first intent (AAPL)
    assert intents[0]["symbol"] == "AAPL"
    assert intents[0]["side"] == "BUY"
    assert intents[0]["quantity"] == 10
    assert intents[0]["order_type"] == "LMT"
    assert float(intents[0]["price"]) == 227.50
    assert intents[0]["status"] == "pending"
    assert intents[0]["client_tag"] == "test_strategy"
    
    # Check second intent (MSFT)
    assert intents[1]["symbol"] == "MSFT"
    assert intents[1]["side"] == "SELL"
    assert intents[1]["quantity"] == 5


def test_idempotency(api_service, test_signal_csv):
    """
    Test that sending the same signals twice doesn't create duplicates
    """
    from trade.paper_trading_adapter import PaperTradingAdapter
    
    adapter = PaperTradingAdapter(api_url=api_service, timeout=5)
    
    # Send signals first time
    results1 = adapter.send_signals_from_csv(test_signal_csv)
    assert results1["created"] == 2
    
    # Send same signals again
    results2 = adapter.send_signals_from_csv(test_signal_csv)
    
    # Should be marked as duplicates
    assert results2["total"] == 2
    assert results2["created"] == 0
    assert results2["duplicates"] == 2
    
    # Verify only 2 intents in database
    conn = sqlite3.connect(str(API_DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM order_intents")
    count = cursor.fetchone()[0]
    conn.close()
    
    assert count == 2


def test_adapter_handles_api_unavailable(test_signal_csv):
    """
    Test that adapter gracefully handles API unavailability
    """
    from trade.paper_trading_adapter import PaperTradingAdapter
    
    # Point to non-existent API
    adapter = PaperTradingAdapter(api_url="http://localhost:9999", timeout=2)
    
    # Health check should fail
    assert not adapter.health_check()
    
    # Sending signals should handle errors gracefully
    results = adapter.send_signals_from_csv(test_signal_csv)
    
    # Should track errors, not crash
    assert results["total"] == 2
    assert results["errors"] == 2


def test_invalid_signal_handling(api_service, tmp_path):
    """
    Test handling of invalid signals (e.g., LMT without price)
    """
    from trade.paper_trading_adapter import PaperTradingAdapter
    
    # Create signal with missing price for LMT order
    csv_path = tmp_path / "invalid_signals.csv"
    signals = pd.DataFrame([
        {
            "symbol": "TSLA",
            "side": "BUY",
            "qty": 5,
            "order_type": "LMT",
            "price": None,  # Missing price for LMT!
            "source": "test",
            "timestamp": "2024-12-01T11:00:00Z"
        }
    ])
    signals.to_csv(csv_path, index=False)
    
    adapter = PaperTradingAdapter(api_url=api_service, timeout=5)
    results = adapter.send_signals_from_csv(csv_path)
    
    # Should be skipped
    assert results["total"] == 1
    assert results["skipped"] == 1
    assert results["created"] == 0


def test_batch_signal_processing(api_service, tmp_path):
    """
    Test processing larger batch of signals
    """
    from trade.paper_trading_adapter import PaperTradingAdapter
    
    # Create 20 signals
    csv_path = tmp_path / "batch_signals.csv"
    signals = []
    for i in range(20):
        signals.append({
            "symbol": f"SYM{i:02d}",
            "side": "BUY" if i % 2 == 0 else "SELL",
            "qty": (i + 1) * 10,
            "order_type": "LMT",
            "price": 100.0 + i,
            "source": "batch_test",
            "timestamp": f"2024-12-01T{10 + i // 60:02d}:{i % 60:02d}:00Z"
        })
    
    pd.DataFrame(signals).to_csv(csv_path, index=False)
    
    adapter = PaperTradingAdapter(api_url=api_service, timeout=5)
    results = adapter.send_signals_from_csv(csv_path)
    
    assert results["total"] == 20
    assert results["created"] == 20
    assert results["errors"] == 0
    
    # Verify in database
    conn = sqlite3.connect(str(API_DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM order_intents")
    count = cursor.fetchone()[0]
    conn.close()
    
    assert count == 20
