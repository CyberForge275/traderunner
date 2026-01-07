"""
Tests for PlanWriter (WP-MS4-1)

Validates:
1. Stable sort order (shuffle-invariant)
2. Canonical JSON (byte-identical for same input)
3. Plan hash stability
"""

import pytest
import json
from pathlib import Path
from pre_paper.plan_writer import PlanWriter


def test_plan_writer_sort_stable(tmp_path):
    """
    Plan writer must sort orders stably by (ts, symbol, side, idempotency_key).
    
    Shuffle-invariant: same orders in random order → same output.
    """
    writer = PlanWriter(tmp_path)
    
    # Orders in random order
    orders = [
        {
            "ts": "2025-01-01T10:31:00+00:00",
            "symbol": "TSLA",
            "side": "BUY",
            "idempotency_key": "order_2",
            "price": 250.0
        },
        {
            "ts": "2025-01-01T10:30:00+00:00",
            "symbol": "AAPL",
            "side": "BUY",
            "idempotency_key": "order_1",
            "price": 150.0
        },
        {
            "ts": "2025-01-01T10:30:00+00:00",
            "symbol": "AAPL",
            "side": "BUY",
            "idempotency_key": "order_0",
            "price": 149.0
        },
    ]
    
    plan_hash = writer.write_plan(orders)
    
    # Read back
    plan = writer.read_plan()
    
    # Assert: stable ordering
    assert len(plan["orders"]) == 3
    assert plan["orders"][0]["symbol"] == "AAPL"
    assert plan["orders"][0]["idempotency_key"] == "order_0"  # Lexicographic
    assert plan["orders"][1]["symbol"] == "AAPL"
    assert plan["orders"][1]["idempotency_key"] == "order_1"
    assert plan["orders"][2]["symbol"] == "TSLA"  # Later ts
    
    # Assert: schema version present
    assert plan["schema_version"] == "1.0.0"


def test_plan_is_byte_identical_two_writes_same_input(tmp_path):
    """
    Same input → byte-identical plan.json (canonical JSON).
    """
    writer1 = PlanWriter(tmp_path / "run1")
    writer2 = PlanWriter(tmp_path / "run2")
    
    orders = [
        {
            "ts": "2025-01-01T10:30:00+00:00",
            "symbol": "AAPL",
            "side": "BUY",
            "idempotency_key": "order_1",
            "price": 150.0,
            "quantity": 100
        }
    ]
    
    # Write twice
    hash1 = writer1.write_plan(orders)
    hash2 = writer2.write_plan(orders)
    
    # Assert: hashes match (deterministic)
    assert hash1 == hash2
    
    # Assert: bytes match
    bytes1 = (tmp_path / "run1" / "plan.json").read_bytes()
    bytes2 = (tmp_path / "run2" / "plan.json").read_bytes()
    assert bytes1 == bytes2


def test_plan_hash_stable_for_same_content(tmp_path):
    """
    Plan hash must be stable across writes (sha256 over bytes).
    """
    writer = PlanWriter(tmp_path)
    
    orders = [
        {"ts": "2025-01-01T10:30:00+00:00", "symbol": "TSLA", "side": "BUY", "idempotency_key": "sig_1"}
    ]
    
    hash1 = writer.write_plan(orders)
    
    # Write again (same orders)
    hash2 = writer.write_plan(orders)
    
    # Assert: hash stable
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex


def test_plan_json_is_diff_friendly(tmp_path):
    """
    Plan JSON must be diff-friendly (sorted keys, indented).
    """
    writer = PlanWriter(tmp_path)
    
    orders = [
        {
            "ts": "2025-01-01T10:30:00+00:00",
            "symbol": "AAPL",
            "side": "BUY",
            "idempotency_key": "order_1",
            "price": 150.0,
            "quantity": 100
        }
    ]
    
    writer.write_plan(orders)
    
    # Read as text
    plan_text = (tmp_path / "plan.json").read_text()
    
    # Assert: indented JSON
    assert "  " in plan_text  # Indentation present
    
    # Assert: sorted keys ('orders' comes before 'schema_version' alphabetically)
    lines = plan_text.split("\n")
    schema_line_idx = next(i for i, line in enumerate(lines) if "schema_version" in line)
    orders_line_idx = next(i for i, line in enumerate(lines) if '"orders"' in line)
    assert schema_line_idx > orders_line_idx  # 'schema_version' comes after 'orders' (alphabetical)


def test_plan_schema_version_present(tmp_path):
    """
    Plan must include schema_version for future compatibility.
    """
    writer = PlanWriter(tmp_path)
    
    orders = [{"ts": "2025-01-01T10:30:00+00:00", "symbol": "AAPL", "side": "BUY", "idempotency_key": "sig_1"}]
    
    writer.write_plan(orders)
    plan = writer.read_plan()
    
    assert "schema_version" in plan
    assert plan["schema_version"] == "1.0.0"
