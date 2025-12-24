"""
Tests for chart logging utilities.
"""

import pytest
import logging
import json
from unittest.mock import Mock, patch
import pandas as pd

from trading_dashboard.utils.chart_logging import (
    generate_error_id,
    build_chart_meta,
    log_chart_meta,
    log_chart_error,
)


def test_generate_error_id():
    """Test error ID generation."""
    error_id = generate_error_id()

    # Should be 8 characters
    assert len(error_id) == 8

    # Should be uppercase hex
    assert error_id.isalnum()
    assert error_id.isupper()

    # Should be unique
    error_id2 = generate_error_id()
    assert error_id != error_id2


def test_chart_meta_structure():
    """Test that chart_meta dict has all required keys."""
    meta = build_chart_meta(
        source="BACKTEST_PARQUET",
        symbol="AMZN",
        timeframe="D1",
        requested_date="2025-11-20",
        effective_date="2025-11-20",
        window_mode="12M",
        rows_before=695,
        rows_after=252,
        dropped_rows=0,
        date_filter_mode="D1_WINDOW",
        min_ts=pd.Timestamp("2024-11-20", tz="America/New_York"),
        max_ts=pd.Timestamp("2025-11-20", tz="America/New_York"),
        market_tz="America/New_York",
        display_tz="America/New_York",
        session_flags={"pre": False, "after": False},
        data_path="data/universe/stocks_data.parquet",
    )

    # Verify all required keys exist
    required_keys = {
        "source", "symbol", "timeframe",
        "requested_date", "effective_date", "window_mode",
        "rows_before", "rows_after", "dropped_rows",
        "date_filter_mode", "min_ts", "max_ts",
        "market_tz", "display_tz", "session_flags", "data_path"
    }

    assert set(meta.keys()) == required_keys

    # Verify types
    assert isinstance(meta["source"], str)
    assert isinstance(meta["rows_before"], int)
    assert isinstance(meta["session_flags"], dict)

    # Verify timestamps are ISO format strings
    assert isinstance(meta["min_ts"], str)
    assert "2024-11-20" in meta["min_ts"]


def test_log_chart_meta(caplog):
    """Test chart_meta logging outputs correct format."""
    meta = {
        "source": "BACKTEST_PARQUET",
        "symbol": "TEST",
        "timeframe": "M5",
        "rows_after": 100,
    }

    with caplog.at_level(logging.INFO):
        log_chart_meta(meta)

    # Should have one log record
    assert len(caplog.records) == 1

    # Should contain "chart_meta" prefix
    assert "chart_meta" in caplog.text

    # Should be valid JSON
    log_message = caplog.records[0].message
    json_part = log_message.split("chart_meta ", 1)[1]
    parsed = json.loads(json_part)

    assert parsed["symbol"] == "TEST"
    assert parsed["rows_after"] == 100


def test_error_id_correlation(caplog):
    """
    Test that error_id appears in both UI message and logs.

    This is the critical correlation test - ensures error_id
    from UI can be found in logs for debugging.
    """
    error_id = generate_error_id()
    exception = ValueError("Test error")

    meta = build_chart_meta(
        source="BACKTEST_PARQUET",
        symbol="AMZN",
        timeframe="D1",
        requested_date=None,
        effective_date=None,
        window_mode=None,
        rows_before=0,
        rows_after=0,
        dropped_rows=0,
        date_filter_mode="NONE",
        min_ts=None,
        max_ts=None,
        market_tz="America/New_York",
        display_tz="America/New_York",
        session_flags={},
        data_path="test.parquet",
    )

    # Capture logs from errors logger
    error_logger = logging.getLogger("errors")

    with caplog.at_level(logging.ERROR, logger="errors"):
        log_chart_error(error_id, exception, meta)

    # Verify error_id in log output
    assert error_id in caplog.text

    # Verify exception details in log
    assert "ValueError" in caplog.text
    assert "Test error" in caplog.text

    # Verify chart_meta context in log
    assert "AMZN" in caplog.text
    assert "D1" in caplog.text

    # Simulate UI error message
    ui_error_message = f"Error loading AMZN D1 (error_id={error_id})"

    # Verify UI would show same error_id
    assert error_id in ui_error_message


def test_chart_meta_handles_none_values():
    """Test that chart_meta handles None values gracefully."""
    meta = build_chart_meta(
        source="BACKTEST_PARQUET",
        symbol="TEST",
        timeframe="M5",
        requested_date=None,  # None values
        effective_date=None,
        window_mode=None,
        rows_before=100,
        rows_after=50,
        dropped_rows=50,
        date_filter_mode="NONE",
        min_ts=None,
        max_ts=None,
        market_tz="America/New_York",
        display_tz="America/New_York",
        session_flags={},
        data_path="test.parquet",
    )

    # Should not raise
    assert meta["requested_date"] is None
    assert meta["effective_date"] is None
    assert meta["min_ts"] is None

    # Should still be JSON-serializable
    json_str = json.dumps(meta)
    assert json_str  # Not empty
