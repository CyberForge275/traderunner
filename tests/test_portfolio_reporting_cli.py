"""
Tests for Step E: CLI Runner for Portfolio Reporting.

Tests verify that:
- CLI can be invoked as module (python -m axiom_bt.portfolio.reporting)
- Generates 3 artifacts from trades.csv
- Deterministic output
- Handles missing files gracefully
"""

import pytest
import subprocess
import sys
import json
import pandas as pd
from pathlib import Path


def create_sample_trades_csv(path: Path):
    """Create a minimal trades.csv for testing."""
    trades = pd.DataFrame({
        "symbol": ["AAPL", "AAPL", "MSFT"],
        "side": ["BUY", "SELL", "BUY"],
        "entry_ts": ["2025-01-01 09:30:00", "2025-01-01 10:00:00", "2025-01-01 10:30:00"],
        "exit_ts": ["2025-01-01 10:00:00", "2025-01-01 11:00:00", "2025-01-01 12:00:00"],
        "entry_price": [150.0, 151.0, 300.0],
        "exit_price": [151.0, 150.0, 305.0],
        "qty": [100, 100, 50],
        "pnl": [98.0, -102.0, 247.0],  # Net PnL (after fees)
        "fees": [2.0, 2.0, 3.0],
        "slippage": [0.0, 0.0, 0.0]
    })
    trades.to_csv(path, index=False)
    return trades


def test_cli_help_works(tmp_path):
    """Verify CLI --help works (sanity check)."""
    result = subprocess.run(
        [sys.executable, "-m", "axiom_bt.portfolio.reporting", "--help"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env={"PYTHONPATH": str(Path.cwd() / "src")}
    )
    
    assert result.returncode == 0
    assert "Generate portfolio reporting artifacts" in result.stdout
    assert "--run-dir" in result.stdout


def test_cli_generates_three_artifacts(tmp_path):
    """CLI should generate exactly 3 portfolio artifacts."""
    # Create minimal run directory
    run_dir = tmp_path / "test_run"
    run_dir.mkdir()
    
    # Create trades.csv
    create_sample_trades_csv(run_dir / "trades.csv")
    
    # Run CLI
    result = subprocess.run(
        [
            sys.executable, "-m", "axiom_bt.portfolio.reporting",
            "--run-dir", str(run_dir),
            "--initial-cash", "10000"
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env={"PYTHONPATH": str(Path.cwd() / "src")}
    )
    
    # Should succeed
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    
    # Should generate 3 files
    assert (run_dir / "portfolio_ledger.csv").exists()
    assert (run_dir / "portfolio_summary.json").exists()
    assert (run_dir / "portfolio_report.md").exists()
    
    # Verify output message
    assert "Generated 3 artifacts" in result.stdout


def test_cli_output_is_deterministic(tmp_path):
    """Running CLI twice with same input should produce identical output."""
    # Create run directory
    run_dir = tmp_path / "test_run"
    run_dir.mkdir()
    create_sample_trades_csv(run_dir / "trades.csv")
    
    # Run CLI twice
    for i in range(2):
        out_dir = tmp_path / f"output_{i}"
        out_dir.mkdir()
        
        result = subprocess.run(
            [
                sys.executable, "-m", "axiom_bt.portfolio.reporting",
                "--run-dir", str(run_dir),
                "--out-dir", str(out_dir),
                "--initial-cash", "10000"
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            env={"PYTHONPATH": str(Path.cwd() / "src")}
        )
        
        assert result.returncode == 0
    
    # Compare outputs
    summary1_path = tmp_path / "output_0" / "portfolio_summary.json"
    summary2_path = tmp_path / "output_1" / "portfolio_summary.json"
    
    with open(summary1_path) as f1, open(summary2_path) as f2:
        summary1 = json.load(f1)
        summary2 = json.load(f2)
    
    # Should be identical
    assert summary1 == summary2


def test_cli_fails_gracefully_on_missing_trades(tmp_path):
    """CLI should fail with clear error if trades.csv missing."""
    # Empty run directory
    run_dir = tmp_path / "empty_run"
    run_dir.mkdir()
    
    result = subprocess.run(
        [
            sys.executable, "-m", "axiom_bt.portfolio.reporting",
            "--run-dir", str(run_dir)
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env={"PYTHONPATH": str(Path.cwd() / "src")}
    )
    
    # Should fail
    assert result.returncode == 1
    assert "trades.csv not found" in result.stderr


def test_cli_uses_custom_out_dir(tmp_path):
    """CLI should respect --out-dir argument."""
    # Create run directory
    run_dir = tmp_path / "test_run"
    run_dir.mkdir()
    create_sample_trades_csv(run_dir / "trades.csv")
    
    # Custom output directory
    out_dir = tmp_path / "custom_output"
    out_dir.mkdir()
    
    result = subprocess.run(
        [
            sys.executable, "-m", "axiom_bt.portfolio.reporting",
            "--run-dir", str(run_dir),
            "--out-dir", str(out_dir),
            "--initial-cash", "10000"
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env={"PYTHONPATH": str(Path.cwd() / "src")}
    )
    
    assert result.returncode == 0
    
    # Files should be in custom out_dir, not run_dir
    assert (out_dir / "portfolio_ledger.csv").exists()
    assert (out_dir / "portfolio_summary.json").exists()
    assert (out_dir / "portfolio_report.md").exists()
    
    # Should NOT be in run_dir
    assert not (run_dir / "portfolio_ledger.csv").exists()


def test_cli_calculates_correct_totals(tmp_path):
    """Verify CLI produces correct financial totals."""
    run_dir = tmp_path / "test_run"
    run_dir.mkdir()
    
    # Create known trades
    trades = create_sample_trades_csv(run_dir / "trades.csv")
    
    result = subprocess.run(
        [
            sys.executable, "-m", "axiom_bt.portfolio.reporting",
            "--run-dir", str(run_dir),
            "--initial-cash", "10000"
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env={"PYTHONPATH": str(Path.cwd() / "src")}
    )
    
    assert result.returncode == 0
    
    # Load summary and verify
    with open(run_dir / "portfolio_summary.json") as f:
        summary = json.load(f)
    
    # Check totals match expected values
    expected_pnl_net = trades["pnl"].sum()  # 98 - 102 + 247 = 243
    expected_fees = trades["fees"].sum()    # 2 + 2 + 3 = 7
    expected_final = 10000 + expected_pnl_net  # 10243
    
    assert summary["initial_cash_usd"] == 10000
    assert summary["total_pnl_net_usd"] == pytest.approx(expected_pnl_net)
    assert summary["total_fees_usd"] == pytest.approx(expected_fees)
    assert summary["final_cash_usd"] == pytest.approx(expected_final)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
