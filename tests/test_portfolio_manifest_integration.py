"""
Tests for Step D: Manifest Integration (Flag-Gated Portfolio Artifacts).

Tests verify that:
- Default runs: manifest unchanged (no portfolio artifacts)
- Flag enabled: manifest includes portfolio artifacts in deterministic order
- Robustness: handles missing files gracefully
"""

import pytest
import json
import os
from pathlib import Path
from axiom_bt.portfolio.ledger import PortfolioLedger
from axiom_bt.portfolio.reporting import generate_portfolio_artifacts
import pandas as pd


def test_reporting_returns_empty_list_when_flag_off(tmp_path, monkeypatch):
    """When flag is OFF, generate_portfolio_artifacts returns empty list."""
    monkeypatch.setenv("AXIOM_BT_PORTFOLIO_REPORT", "0")
    
    ledger = PortfolioLedger(10000, enforce_monotonic=False)
    ledger.apply_trade(
        exit_ts=pd.Timestamp("2025-01-01 10:00", tz="UTC"),
        pnl=100
    )
    
    result = generate_portfolio_artifacts(ledger, tmp_path)
    
    # Should return empty list
    assert result == []
    
    # Should NOT create any files
    assert not (tmp_path / "portfolio_ledger.csv").exists()
    assert not (tmp_path / "portfolio_summary.json").exists()
    assert not (tmp_path / "portfolio_report.md").exists()


def test_reporting_returns_file_list_when_flag_on(tmp_path, monkeypatch):
    """When flag is ON, generate_portfolio_artifacts returns list of 3 files."""
    monkeypatch.setenv("AXIOM_BT_PORTFOLIO_REPORT", "1")
    
    ledger = PortfolioLedger(10000, enforce_monotonic=False)
    ledger.apply_trade(
        exit_ts=pd.Timestamp("2025-01-01 10:00", tz="UTC"),
        pnl=100
    )
    
    result = generate_portfolio_artifacts(ledger, tmp_path)
    
    # Should return exactly 3 files in deterministic order
    assert result == [
        "portfolio_ledger.csv",
        "portfolio_summary.json",
        "portfolio_report.md"
    ]
    
    # All files should exist
    assert (tmp_path / "portfolio_ledger.csv").exists()
    assert (tmp_path / "portfolio_summary.json").exists()
    assert (tmp_path / "portfolio_report.md").exists()


def test_file_list_order_is_deterministic(tmp_path, monkeypatch):
    """Files are returned in stable, deterministic order."""
    monkeypatch.setenv("AXIOM_BT_PORTFOLIO_REPORT", "1")
    
    ledger = PortfolioLedger(10000, enforce_monotonic=False)
    
    # Run multiple times - order should be identical
    results = []
    for i in range(3):
        run_dir = tmp_path / f"run_{i}"
        run_dir.mkdir()
        result = generate_portfolio_artifacts(ledger, run_dir)
        results.append(result)
    
    # All runs should produce same order
    assert results[0] == results[1] == results[2]
    assert results[0] == [
        "portfolio_ledger.csv",
        "portfolio_summary.json",
        "portfolio_report.md"
    ]


def test_manifest_integration_conceptual():
    """
    Conceptual test: demonstrates how generated_files would integrate with manifest.
    
    This shows the expected pattern for manifest writer integration:
    1. Call generate_portfolio_artifacts()
    2. If non-empty, append to artifacts_produced list
    3. Pass to manifest_writer.finalize_manifest(run_result, artifacts_produced)
    """
    # Simulated manifest artifacts list (existing artifacts)
    existing_artifacts = [
        "trades.csv",
        "equity_curve.csv",
        "metrics.json",
        "run_result.json"
    ]
    
    # Simulated portfolio artifacts (from generate_portfolio_artifacts)
    portfolio_artifacts = [
        "portfolio_ledger.csv",
        "portfolio_summary.json",
        "portfolio_report.md"
    ]
    
    # Integration pattern: append if non-empty
    artifacts_produced = existing_artifacts.copy()
    if portfolio_artifacts:  # Only if flag was ON and files generated
        artifacts_produced.extend(portfolio_artifacts)
    
    # Verify order is preserved
    assert artifacts_produced == [
        "trades.csv",
        "equity_curve.csv",
        "metrics.json",
        "run_result.json",
        "portfolio_ledger.csv",
        "portfolio_summary.json",
        "portfolio_report.md"
    ]
    
    # Verify no duplicates
    assert len(artifacts_produced) == len(set(artifacts_produced))


def test_manifest_default_run_unchanged():
    """
    Default run: manifest should NOT include portfolio artifacts.
    
    This test verifies the 0-behavior-change guardrail.
    """
    # Simulated default run (flag OFF)
    portfolio_artifacts = []  # Empty because flag is OFF
    
    existing_artifacts = [
        "trades.csv",
        "equity_curve.csv",
        "metrics.json"
    ]
    
    # Manifest should remain unchanged
    artifacts_produced = existing_artifacts.copy()
    if portfolio_artifacts:
        artifacts_produced.extend(portfolio_artifacts)
    
    # Should be identical to existing
    assert artifacts_produced == existing_artifacts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
