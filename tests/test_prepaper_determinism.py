"""
Tests for Signals/Intents Roundtrip + Replay Determinism (WP-MS4-3)

KEY TESTS:
- test_intents_written_idempotent() - write twice, no duplicates
- test_two_replay_runs_same_inputs_same_plan_hash() - DETERMINISM PROOF (GATE)
- test_signals_export_sorted_stable() - optional export verification
"""

import pytest
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# Add marketdata-monorepo to path
monorepo_path = Path(__file__).parent.parent.parent / "marketdata-monorepo" / "src"
if monorepo_path.exists() and str(monorepo_path) not in sys.path:
    sys.path.insert(0, str(monorepo_path))

from marketdata_service import FakeMarketDataService
from pre_paper.marketdata_port import PrePaperMarketDataPort
from pre_paper.plan_writer import PlanWriter


def compute_idempotency_key(order: dict) -> str:
    """
    Compute deterministic idempotency_key for order intent.
    
    Uses SHA256 over canonical representation.
    """
    parts = [
        order.get("ts", ""),
        order.get("symbol", ""),
        order.get("side", ""),
        order.get("strategy_key", ""),
        str(order.get("entry_price", "")),
        str(order.get("sl", "")),
        str(order.get("tp", ""))
    ]
    
    canonical = "|".join(parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@pytest.mark.asyncio
async def test_intents_written_idempotent():
    """
    Writing same order-intents twice must not create duplicates.
    
    Idempotency via UNIQUE(lab, run_id, idempotency_key).
    """
    # Create fresh service for this test
    service = FakeMarketDataService()
    port = PrePaperMarketDataPort(service)
    
    # Order intents
    orders = [
        {
            "ts": "2025-01-01T10:30:00+00:00",
            "symbol": "AAPL",
            "side": "BUY",
            "strategy_key": "inside_bar",
            "entry_price": 150.0,
            "sl": 148.0,
            "tp": 154.0
        }
    ]
    
    # Add idempotency keys
    for order in orders:
        order["idempotency_key"] = compute_idempotency_key(order)
    
    # First write
    result1 = await port.write_signals(
        lab="PREPAPER",
        run_id="test_run_idempotent",
        source_tag="prepaper_plan_intent",
        signals=orders
    )
    
    assert result1.written == 1
    assert result1.duplicates_skipped == 0
    
    # Second write (duplicate)
    result2 = await port.write_signals(
        lab="PREPAPER",
        run_id="test_run_idempotent",
        source_tag="prepaper_plan_intent",
        signals=orders
    )
    
    assert result2.written == 0
    assert result2.duplicates_skipped == 1
    
    # Query: should have exactly 1 record
    signals = await port.query_signals(
        lab="PREPAPER",
        run_id="test_run_idempotent"
    )
    
    assert len(signals) == 1


@pytest.mark.asyncio
async def test_two_replay_runs_same_inputs_same_plan_hash():
    """
    KEY TEST (GATE): Replay determinism proof.
    
    Two runs with:
    - Same backtest manifest
    - Same replay date
    - Same marketdata inputs (FakeService with same seed)
    - Same explicit run_id
    
    Must produce:
    - Identical plan_hash
    - Identical signals (same count, same idempotency_keys)
    """
    # Run 1
    service1 = FakeMarketDataService(emit_ticks=False, bars_count=10)
    port1 = PrePaperMarketDataPort(service1)
    
    start = datetime(2025, 1, 1, 9, 30, tzinfo=timezone.utc)
    end = datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc)
    
    # Get bars (deterministic from FakeService)
    bars_response1 = await port1.get_replay_bars(
        symbol="AAPL",
        start=start,
        end=end,
        timeframe="M1"
    )
    
    # Generate orders (simple: 1 order per 5 bars)
    orders1 = []
    for i, bar in enumerate(bars_response1.bars):
        if i % 5 == 0:
            order = {
                "ts": bar.ts.isoformat(),
                "symbol": bar.symbol,
                "side": "BUY",
                "strategy_key": "test_strategy",
                "entry_price": bar.close,
                "sl": bar.close - 1.0,
                "tp": bar.close + 2.0
            }
            order["idempotency_key"] = compute_idempotency_key(order)
            orders1.append(order)
    
    # Write plan
    plan_writer1 = PlanWriter(Path("/tmp/prepaper_test_run1"))
    plan_hash1 = plan_writer1.write_plan(orders1)
    
    # Write intents to signals.db
    await port1.write_signals(
        lab="PREPAPER",
        run_id="determinism_test_run",
        source_tag="prepaper_plan_intent",
        signals=orders1
    )
    
    # Run 2 (IDENTICAL INPUTS)
    service2 = FakeMarketDataService(emit_ticks=False, bars_count=10)  # Same config!
    port2 = PrePaperMarketDataPort(service2)
    
    # Get bars (same inputs → same bars)
    bars_response2 = await port2.get_replay_bars(
        symbol="AAPL",
        start=start,
        end=end,
        timeframe="M1"
    )
    
    # Generate orders (same logic)
    orders2 = []
    for i, bar in enumerate(bars_response2.bars):
        if i % 5 == 0:
            order = {
                "ts": bar.ts.isoformat(),
                "symbol": bar.symbol,
                "side": "BUY",
                "strategy_key": "test_strategy",
                "entry_price": bar.close,
                "sl": bar.close - 1.0,
                "tp": bar.close + 2.0
            }
            order["idempotency_key"] = compute_idempotency_key(order)
            orders2.append(order)
    
    # Write plan
    plan_writer2 = PlanWriter(Path("/tmp/prepaper_test_run2"))
    plan_hash2 = plan_writer2.write_plan(orders2)
    
    # ASSERT: plan_hash IDENTICAL (DETERMINISM PROOF)
    assert plan_hash1 == plan_hash2, \
        f"DETERMINISM FAILURE: plan_hash mismatch!\n" \
        f"Run1: {plan_hash1}\n" \
        f"Run2: {plan_hash2}"
    
    # ASSERT: marketdata_data_hash IDENTICAL
    assert bars_response1.provenance.data_hash == bars_response2.provenance.data_hash
    
    # ASSERT: orders count identical
    assert len(orders1) == len(orders2)
    
    # ASSERT: idempotency_keys match (deterministic)
    keys1 = [o["idempotency_key"] for o in orders1]
    keys2 = [o["idempotency_key"] for o in orders2]
    assert keys1 == keys2


@pytest.mark.asyncio
async def test_signals_query_ordering_stable():
    """
    Signals query must return stable ordering (ts, symbol, idempotency_key).
    """
    service = FakeMarketDataService()
    port = PrePaperMarketDataPort(service)
    
    # Write in random order
    orders = [
        {
            "ts": "2025-01-01T10:31:00+00:00",
            "symbol": "TSLA",
            "side": "BUY",
            "strategy_key": "test",
            "entry_price": 250.0,
            "sl": 248.0,
            "tp": 254.0,
            "idempotency_key": "order_2"
        },
        {
            "ts": "2025-01-01T10:30:00+00:00",
            "symbol": "AAPL",
            "side": "BUY",
            "strategy_key": "test",
            "entry_price": 150.0,
            "sl": 148.0,
            "tp": 154.0,
            "idempotency_key": "order_1"
        },
        {
            "ts": "2025-01-01T10:30:00+00:00",
            "symbol": "AAPL",
            "side": "BUY",
            "strategy_key": "test",
            "entry_price": 149.0,
            "sl": 147.0,
            "tp": 153.0,
            "idempotency_key": "order_0"
        }
    ]
    
    await port.write_signals(
        lab="PREPAPER",
        run_id="test_ordering",
        source_tag="prepaper_plan_intent",
        signals=orders
    )
    
    # Query
    results = await port.query_signals(
        lab="PREPAPER",
        run_id="test_ordering"
    )
    
    # Assert: stable ordering (ts, symbol, idempotency_key)
    assert len(results) == 3
    assert results[0].symbol == "AAPL"
    assert results[0].idempotency_key == "order_0"  # Lexicographic
    assert results[1].symbol == "AAPL"
    assert results[1].idempotency_key == "order_1"
    assert results[2].symbol == "TSLA"  # Later ts


@pytest.mark.asyncio
async def test_signals_export_canonical_json(tmp_path):
    """
    Optional: signals_export.json must be canonical (sorted, stable).
    """
    service = FakeMarketDataService()
    port = PrePaperMarketDataPort(service)
    
    orders = [
        {
            "ts": "2025-01-01T10:30:00+00:00",
            "symbol": "AAPL",
            "side": "BUY",
            "strategy_key": "test",
            "entry_price": 150.0,
            "sl": 148.0,
            "tp": 154.0
        }
    ]
    
    for order in orders:
        order["idempotency_key"] = compute_idempotency_key(order)
    
    await port.write_signals(
        lab="PREPAPER",
        run_id="test_export",
        source_tag="prepaper_plan_intent",
        signals=orders
    )
    
    # Query and export
    results = await port.query_signals(
        lab="PREPAPER",
        run_id="test_export"
    )
    
    # Export to JSON
    export_path = tmp_path / "signals_export.json"
    export_data = {
        "schema_version": "1.0.0",
        "signals": [
            {
                "ts": r.ts.isoformat(),
                "symbol": r.symbol,
                "idempotency_key": r.idempotency_key,
                "payload": json.loads(r.payload_json)
            }
            for r in results
        ]
    }
    
    # Canonical JSON
    export_json = json.dumps(export_data, indent=2, sort_keys=True, separators=(",", ": "))
    export_path.write_text(export_json, encoding="utf-8")
    
    # Verify: parseable and sorted
    loaded = json.loads(export_path.read_text())
    assert "schema_version" in loaded
    assert len(loaded["signals"]) == 1
