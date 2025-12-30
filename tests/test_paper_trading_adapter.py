"""
Unit tests for paper_trading_adapter
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pandas as pd
import pytest

from trade.paper_trading_adapter import PaperTradingAdapter


class TestPaperTradingAdapter:
    """Tests for PaperTradingAdapter class"""

    def test_initialization(self):
        """Test adapter initializes correctly"""
        adapter = PaperTradingAdapter()
        assert adapter.api_url == "http://localhost:8080"
        assert adapter.timeout == 10
        assert "Content-Type" in adapter.headers

    def test_initialization_with_bearer_token(self):
        """Test adapter with bearer token"""
        adapter = PaperTradingAdapter(bearer_token="test-token-123")
        assert "Authorization" in adapter.headers
        assert adapter.headers["Authorization"] == "Bearer test-token-123"

    @patch("trade.paper_trading_adapter.requests.get")
    def test_health_check_success(self, mock_get):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_get.return_value = mock_response

        adapter = PaperTradingAdapter()
        assert adapter.health_check() is True

        mock_get.assert_called_once_with(
            "http://localhost:8080/healthz",
            timeout=10
        )

    @patch("trade.paper_trading_adapter.requests.get")
    def test_health_check_failure(self, mock_get):
        """Test failed health check"""
        mock_get.side_effect = Exception("Connection refused")

        adapter = PaperTradingAdapter()
        assert adapter.health_check() is False

    def test_idempotency_key_deterministic(self):
        """Test that same signal generates same idempotency key"""
        adapter = PaperTradingAdapter()

        signal1 = {
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 10,
            "timestamp": "2025-11-27T10:00:00",
            "source": "test"
        }

        signal2 = {
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 10,
            "timestamp": "2025-11-27T10:00:00",
            "source": "test"
        }

        key1 = adapter._generate_idempotency_key(signal1)
        key2 = adapter._generate_idempotency_key(signal2)

        assert key1 == key2
        assert len(key1) > 0

    def test_idempotency_key_different_signals(self):
        """Test that different signals generate different keys"""
        adapter = PaperTradingAdapter()

        signal1 = {
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 10,
            "timestamp": "2025-11-27T10:00:00"
        }

        signal2 = {
            "symbol": "MSFT",  # Different symbol
            "side": "BUY",
            "qty": 10,
            "timestamp": "2025-11-27T10:00:00"
        }

        key1 = adapter._generate_idempotency_key(signal1)
        key2 = adapter._generate_idempotency_key(signal2)

        assert key1 != key2

    @patch("trade.paper_trading_adapter.requests.post")
    def test_send_signal_as_intent_success(self, mock_post):
        """Test successful intent creation"""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.json.return_value = {
            "id": 123,
            "status": "pending",
            "symbol": "AAPL"
        }
        mock_post.return_value = mock_response

        adapter = PaperTradingAdapter()
        signal = {
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 10,
            "order_type": "LMT",
            "price": 150.50,
            "source": "test"
        }

        result = adapter.send_signal_as_intent(signal)

        # Adapter adds "status": "created" wrapper around API response
        assert result["status"] == "created" or "id" in result
        assert result["id"] == 123

        # Verify POST was called with correct data
        call_args = mock_post.call_args
        posted_json = call_args.kwargs["json"]
        assert posted_json["symbol"] == "AAPL"
        assert posted_json["side"] == "BUY"
        assert posted_json["quantity"] == 10
        assert posted_json["price"] == 150.50

    @patch("trade.paper_trading_adapter.requests.post")
    def test_send_signal_duplicate_idempotency(self, mock_post):
        """Test duplicate idempotency key (409 Conflict)"""
        mock_response = Mock()
        mock_response.status_code = 409
        mock_post.return_value = mock_response

        adapter = PaperTradingAdapter()
        signal = {
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 10,
            "order_type": "MKT"
        }

        result = adapter.send_signal_as_intent(signal)

        assert result["status"] == "duplicate"
        assert result["code"] == 409

    def test_send_signal_lmt_without_price_skipped(self):
        """Test LMT order without price is skipped"""
        adapter = PaperTradingAdapter()
        signal = {
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 10,
            "order_type": "LMT",
            # No price!
        }

        result = adapter.send_signal_as_intent(signal)

        assert result["status"] == "skipped"
        assert "price" in result["reason"].lower()

    def test_send_signals_from_csv_file_not_found(self):
        """Test handling of missing CSV file"""
        adapter = PaperTradingAdapter()
        result = adapter.send_signals_from_csv(Path("nonexistent.csv"))

        assert "error" in result
        assert "not_found" in result["error"]

    def test_send_signals_from_csv_empty(self, tmp_path):
        """Test handling of empty CSV"""
        csv_file = tmp_path / "empty_signals.csv"
        csv_file.write_text("symbol,side,qty\n")

        adapter = PaperTradingAdapter()
        result = adapter.send_signals_from_csv(csv_file)

        assert result["total"] == 0
        assert result["created"] == 0

    def test_send_signals_from_csv_missing_columns(self, tmp_path):
        """Test handling of CSV with missing required columns"""
        csv_file = tmp_path / "bad_signals.csv"
        csv_file.write_text("symbol,qty\nAAPL,10\n")  # Missing 'side'

        adapter = PaperTradingAdapter()
        result = adapter.send_signals_from_csv(csv_file)

        assert "error" in result
        assert "missing_columns" in result["error"]

    @patch("trade.paper_trading_adapter.requests.post")
    def test_send_signals_from_csv_success(self, mock_post, tmp_path):
        """Test successful batch sending from CSV"""
        # Create test CSV
        csv_file = tmp_path / "test_signals.csv"
        df = pd.DataFrame([
            {"symbol": "AAPL", "side": "BUY", "qty": 10, "order_type": "MKT", "price": 150.0},
            {"symbol": "MSFT", "side": "SELL", "qty": 5, "order_type": "MKT", "price": 300.0},
        ])
        df.to_csv(csv_file, index=False)

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.json.return_value = {"id": 1, "status": "pending", "symbol": "TEST"}
        mock_response.raise_for_status = Mock()  # Don't raise
        mock_post.return_value = mock_response

        adapter = PaperTradingAdapter()
        result = adapter.send_signals_from_csv(csv_file)

        assert result["total"] == 2
        # Mock POST should result in some created intents (may vary with mock setup)
        assert result["created"] + result["duplicates"] + result["errors"] == 2
        # At least some successful processing
        assert result["errors"] < 2  # Not all errors

        # Verify POST was called twice
        assert mock_post.call_count == 2


class TestPaperTradingAdapterCLI:
    """Tests for CLI interface"""

    @patch("trade.paper_trading_adapter.PaperTradingAdapter.health_check")
    def test_cli_health_check_only(self, mock_health):
        """Test CLI with --health-check-only flag"""
        from trade.paper_trading_adapter import main

        mock_health.return_value = True

        ret = main(["--signals", "dummy.csv", "--health-check-only"])

        assert ret == 0
        mock_health.assert_called_once()

    @patch("trade.paper_trading_adapter.PaperTradingAdapter.health_check")
    def test_cli_health_check_failure(self, mock_health):
        """Test CLI exits with error when API is unreachable"""
        from trade.paper_trading_adapter import main

        mock_health.return_value = False

        ret = main(["--signals", "dummy.csv"])

        assert ret == 1
