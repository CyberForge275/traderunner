# Portfolio Reporting - Manual Testing Guide

**Date**: 2026-01-05  
**Status**: Backend complete (Steps A-E), UI integration pending

---

## Overview

Portfolio reporting generates optional, audit-grade artifacts for backtest runs:
- `portfolio_ledger.csv` - Complete ledger with START entry, sequence numbers
- `portfolio_summary.json` - Financial summary (cash, PnL, fees, peak equity)
- `portfolio_report.md` - Human-readable markdown report

**Key Features:**
- ✅ Deterministic (same trades → same reports)
- ✅ Cost semantics clarified (pnl = net cash delta, fees/slippage = evidence)
- ✅ Standalone CLI (no UI required)
- ✅ 0 behavior change for default runs

---

## Method 1: CLI Standalone (Recommended for Testing)

### Generate Report from Existing Run

```bash
# From repository root
cd /home/mirko/data/workspace/droid/traderunner

# Set PYTHONPATH and run
PYTHONPATH=$(pwd)/src python -m axiom_bt.portfolio.reporting \
  --run-dir artifacts/backtests/260105_120000_AAPL
```

**Output:**
```
Replaying 15 trades...
Generating portfolio artifacts to artifacts/backtests/260105_120000_AAPL...

✅ Generated 3 artifacts:
  - portfolio_ledger.csv (2341 bytes)
  - portfolio_summary.json (456 bytes)
  - portfolio_report.md (1024 bytes)

Output directory: artifacts/backtests/260105_120000_AAPL
```

### CLI Options

```bash
# Custom output directory
python -m axiom_bt.portfolio.reporting \
  --run-dir artifacts/backtests/<RUN_ID> \
  --out-dir ./portfolio_reports

# Override initial cash (if not in manifest)
python -m axiom_bt.portfolio.reporting \
  --run-dir <RUN_ID> \
  --initial-cash 50000

# Specify start timestamp
python -m axiom_bt.portfolio.reporting \
  --run-dir <RUN_ID> \
  --start-ts "2025-01-01T09:30:00-05:00"
```

### Verify Determinism

```bash
# Generate twice, compare outputs
RUN_DIR="artifacts/backtests/260105_120000_AAPL"

python -m axiom_bt.portfolio.reporting --run-dir $RUN_DIR --out-dir /tmp/test1
python -m axiom_bt.portfolio.reporting --run-dir $RUN_DIR --out-dir /tmp/test2

# Should be identical (byte-for-byte)
sha256sum /tmp/test1/portfolio_summary.json /tmp/test2/portfolio_summary.json
```

---

## Method 2: Environment Variable (Legacy)

### Enable During Backtest

```bash
# Set flag before running backtest
export AXIOM_BT_PORTFOLIO_REPORT=1

# Run backtest (trading_dashboard or CLI)
# Portfolio artifacts will be generated automatically

# Disable after
unset AXIOM_BT_PORTFOLIO_REPORT
```

**Note**: This method generates artifacts during backtest execution. Use CLI method for post-hoc reporting.

---

## Method 3: Programmatic (Python API)

### Direct API Call

```python
from pathlib import Path
from axiom_bt.portfolio.ledger import PortfolioLedger
from axiom_bt.portfolio.reporting import generate_portfolio_artifacts
import pandas as pd

# Load trades from existing run
run_dir = Path("artifacts/backtests/260105_120000_AAPL")
trades_df = pd.read_csv(run_dir / "trades.csv")

# Replay ledger
ledger = PortfolioLedger.replay_from_trades(
    trades_df,
    initial_cash=10000
)

# Generate artifacts (returns list of filenames)
import os
os.environ["AXIOM_BT_PORTFOLIO_REPORT"] = "1"

generated_files = generate_portfolio_artifacts(
    ledger=ledger,
    run_dir=run_dir,
    trades_df=trades_df
)

print(f"Generated: {generated_files}")
# Output: ['portfolio_ledger.csv', 'portfolio_summary.json', 'portfolio_report.md']
```

---

## Verification Checklist

### 1. Files Exist
```bash
RUN_DIR="artifacts/backtests/<RUN_ID>"
ls -lh $RUN_DIR/portfolio_*.{csv,json,md}
```

Expected:
- `portfolio_ledger.csv` (~1-10 KB depending on trades)
- `portfolio_summary.json` (~500 bytes)
- `portfolio_report.md` (~1 KB)

### 2. JSON Structure Valid

```bash
jq . $RUN_DIR/portfolio_summary.json
```

Expected fields:
```json
{
  "initial_cash_usd": 10000,
  "final_cash_usd": 10243.50,
  "total_pnl_net_usd": 243.50,
  "total_fees_usd": 15.00,
  "total_slippage_usd": 3.50,
  "peak_equity_usd": 10350.00,
  "num_events": 10,
  "max_drawdown": -2.5,
  "trades": {
    "count": 10,
    "wins": 6,
    "losses": 4,
    "win_rate": 0.6
  }
}
```

### 3. Ledger Parity (Optional Assertion)

```python
import pandas as pd
import json

# Load portfolio_summary
with open("artifacts/backtests/<RUN_ID>/portfolio_summary.json") as f:
    summary = json.load(f)

# Load trades
trades = pd.read_csv("artifacts/backtests/<RUN_ID>/trades.csv")

# Verify: final_cash = initial + sum(pnl_net)
initial = summary["initial_cash_usd"]
total_pnl = summary["total_pnl_net_usd"]
final = summary["final_cash_usd"]

assert abs(final - (initial + total_pnl)) < 1e-6, "Cash accounting mismatch!"
print("✅ Ledger parity verified")
```

### 4. Determinism Check

```bash
# Generate twice
python -m axiom_bt.portfolio.reporting --run-dir $RUN_DIR --out-dir /tmp/v1
python -m axiom_bt.portfolio.reporting --run-dir $RUN_DIR --out-dir /tmp/v2

# Compare
diff /tmp/v1/portfolio_summary.json /tmp/v2/portfolio_summary.json
# Should output nothing (files identical)
```

---

## Manifest Integration

When `AXIOM_BT_PORTFOLIO_REPORT=1` is set during backtest:
- Portfolio artifacts are generated
- `run_manifest.json` includes them in `result.artifacts_index`

**Verify:**
```bash
jq '.result.artifacts_index' artifacts/backtests/<RUN_ID>/run_manifest.json
```

Expected (if reporting enabled):
```json
[
  "trades.csv",
  "equity_curve.csv",
  "metrics.json",
  "portfolio_ledger.csv",
  "portfolio_summary.json",
  "portfolio_report.md"
]
```

**Default (reporting disabled):**
```json
[
  "trades.csv",
  "equity_curve.csv",
  "metrics.json"
]
```

---

## Troubleshooting

### ModuleNotFoundError: No module named 'axiom_bt'

**Solution:**
```bash
# Always set PYTHONPATH when using CLI
PYTHONPATH=$(pwd)/src python -m axiom_bt.portfolio.reporting ...

# OR install in editable mode
pip install -e .
```

### "Error: trades.csv not found"

**Solution:**
- Ensure run directory contains `trades.csv`
- Check path is correct (absolute or relative)

### Different totals than metrics.json

**Expected:** Portfolio summary uses NET PnL (post-costs).  
If `metrics.json` shows gross PnL, values will differ by total fees/slippage.

**Verify:**
```python
gross_pnl = metrics["total_pnl"]  # From metrics.json
net_pnl = portfolio["total_pnl_net_usd"]  # From portfolio_summary.json
total_costs = portfolio["total_fees_usd"] + portfolio["total_slippage_usd"]

assert abs(gross_pnl - (net_pnl + total_costs)) < 1e-6
```

---

## Quick Start Examples

### Example 1: Test with Sample Run

```bash
# Find a recent run
ls -lt artifacts/backtests/ | head -5

# Generate report
PYTHONPATH=src python -m axiom_bt.portfolio.reporting \
  --run-dir artifacts/backtests/260105_143000_MSFT

# View summary
cat artifacts/backtests/260105_143000_MSFT/portfolio_report.md
```

### Example 2: Batch Processing

```bash
# Generate reports for all runs from today
for run_dir in artifacts/backtests/260105_*; do
  echo "Processing: $run_dir"
  PYTHONPATH=src python -m axiom_bt.portfolio.reporting --run-dir "$run_dir"
done
```

### Example 3: Custom Analysis

```bash
# Generate to custom location for analysis
python -m axiom_bt.portfolio.reporting \
  --run-dir artifacts/backtests/260105_143000_MSFT \
  --out-dir ~/analysis/msft_backtest \
  --initial-cash 25000

# Analyze with pandas
python3 << EOF
import pandas as pd
ledger = pd.read_csv("~/analysis/msft_backtest/portfolio_ledger.csv")
print(ledger[["ts", "event_type", "cash_after", "equity_after"]].tail(10))
EOF
```

---

## Next Steps (UI Integration - Future)

**Pending UI work (not in this release):**
1. Dashboard toggle for `portfolio_report_enabled`
2. Run detail page: display `portfolio_summary.json`
3. Link to download portfolio artifacts

**Current workaround:**
- Use CLI for all portfolio reporting needs
- Set `AXIOM_BT_PORTFOLIO_REPORT=1` globally when needed

---

## Testing Commands Summary

```bash
# Repository setup
cd /home/mirko/data/workspace/droid/traderunner
export PYTHONPATH=$(pwd)/src

# Basic CLI test
python -m axiom_bt.portfolio.reporting --help

# Generate report
python -m axiom_bt.portfolio.reporting \
  --run-dir artifacts/backtests/<RUN_ID>

# Verify files
ls -lh artifacts/backtests/<RUN_ID>/portfolio_*

# Check JSON
jq . artifacts/backtests/<RUN_ID>/portfolio_summary.json

# Run tests
pytest -q tests/test_portfolio_*.py
```

---

**Documentation Version**: 1.0  
**Last Updated**: 2026-01-05  
**Backend Status**: ✅ Complete (Steps A-E)
