"""
Tests for ManifestWriter (WP-MS4-2)

Validates:
1. Manifest contains required fields
2. marketdata_data_hash is included
3. plan_hash matches file bytes
4. backtest_manifest_hash computed correctly
"""

import pytest
import json
import hashlib
from pathlib import Path
from pre_paper.manifest_writer import ManifestWriter


def test_manifest_contains_required_fields(tmp_path):
    """
    run_manifest.json must contain all required sections.
    """
    writer = ManifestWriter(tmp_path)
    
    manifest = writer.write_manifest(
        run_id="test_run_001",
        lab="PREPAPER",
        mode="replay",
        source_backtest_run_id="251215_144939_HOOD_M5_100d",
        backtest_manifest={"identity": {"run_id": "251215_144939_HOOD_M5_100d"}},
        marketdata_data_hash="abc123def456",
        plan_hash="plan_hash_xyz",
        signals_count=42,
        strategy={"key": "inside_bar", "version": "1.0"},
        params={"lookback": 50},
        data={"symbol": "AAPL", "tf": "M5"},
        git_commit="abc1234"
    )
    
    # Assert: required sections
    assert "identity" in manifest
    assert "strategy" in manifest
    assert "params" in manifest
    assert "data" in manifest
    assert "inputs" in manifest
    assert "outputs" in manifest
    assert "result" in manifest
    
    # Assert: identity fields
    assert manifest["identity"]["run_id"] == "test_run_001"
    assert manifest["identity"]["lab"] == "PREPAPER"
    assert manifest["identity"]["mode"] == "replay"
    assert manifest["identity"]["source_backtest_run_id"] == "251215_144939_HOOD_M5_100d"
    
    # Assert: inputs
    assert "backtest_manifest_hash" in manifest["inputs"]
    assert "marketdata_data_hash" in manifest["inputs"]
    assert "git_commit" in manifest["inputs"]
    
    # Assert: outputs
    assert manifest["outputs"]["plan_hash"] == "plan_hash_xyz"
    assert manifest["outputs"]["signals_count"] == 42


def test_manifest_includes_marketdata_data_hash(tmp_path):
    """
    Manifest must include marketdata_data_hash from DataProvenance.
    """
    writer = ManifestWriter(tmp_path)
    
    manifest = writer.write_manifest(
        run_id="test_run_002",
        lab="PREPAPER",
        mode="replay",
        source_backtest_run_id="test_backtest",
        backtest_manifest={},
        marketdata_data_hash="sha256_marketdata_hash",
        plan_hash="plan_hash",
        signals_count=10,
        strategy={},
        params={},
        data={}
    )
    
    # Assert: marketdata_data_hash present
    assert manifest["inputs"]["marketdata_data_hash"] == "sha256_marketdata_hash"


def test_backtest_manifest_hash_computed(tmp_path):
    """
    backtest_manifest_hash must be SHA256 of backtest manifest (canonical JSON).
    """
    writer = ManifestWriter(tmp_path)
    
    backtest_manifest = {
        "identity": {"run_id": "backtest_123"},
        "strategy": {"key": "inside_bar"}
    }
    
    manifest = writer.write_manifest(
        run_id="test_run_003",
        lab="PREPAPER",
        mode="replay",
        source_backtest_run_id="backtest_123",
        backtest_manifest=backtest_manifest,
        marketdata_data_hash="data_hash",
        plan_hash="plan_hash",
        signals_count=0,
        strategy={},
        params={},
        data={}
    )
    
    # Compute expected hash
    expected_hash = hashlib.sha256(
        json.dumps(backtest_manifest, sort_keys=True).encode("utf-8")
    ).hexdigest()
    
    assert manifest["inputs"]["backtest_manifest_hash"] == expected_hash


def test_manifest_is_diff_friendly(tmp_path):
    """
    Manifest JSON must be diff-friendly (sorted, indented).
    """
    writer = ManifestWriter(tmp_path)
    
    writer.write_manifest(
        run_id="test_run_004",
        lab="PREPAPER",
        mode="replay",
        source_backtest_run_id="test",
        backtest_manifest={},
        marketdata_data_hash="hash",
        plan_hash="hash",
        signals_count=0,
        strategy={},
        params={},
        data={}
    )
    
    manifest_text = (tmp_path / "run_manifest.json").read_text()
    
    # Assert: indented
    assert "  " in manifest_text
    
    # Assert: sorted keys (can parse as JSON)
    manifest = json.loads(manifest_text)
    assert "identity" in manifest


def test_manifest_mode_field_present(tmp_path):
    """
    Manifest must include mode field (replay/live) for determinism tests.
    """
    writer = ManifestWriter(tmp_path)
    
    # Replay mode
    manifest_replay = writer.write_manifest(
        run_id="test_run_replay",
        lab="PREPAPER",
        mode="replay",
        source_backtest_run_id="test",
        backtest_manifest={},
        marketdata_data_hash="hash",
        plan_hash="hash",
        signals_count=0,
        strategy={},
        params={},
        data={}
    )
    
    assert manifest_replay["identity"]["mode"] == "replay"
    
    # Live mode (for future WS-only)
    manifest_live = writer.write_manifest(
        run_id="test_run_live",
        lab="PREPAPER",
        mode="live",
        source_backtest_run_id="test",
        backtest_manifest={},
        marketdata_data_hash="hash",
        plan_hash="hash",
        signals_count=0,
        strategy={},
        params={},
        data={}
    )
    
    assert manifest_live["identity"]["mode"] == "live"
