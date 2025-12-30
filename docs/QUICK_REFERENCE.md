## Rudometkin MOC – Quick Reference (Minute Data Edition)

> **Last Updated**: 2025-12-05

### 1. Fast Commands

From repo root:

```bash
# Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
PYTHONPATH=src python -m pytest tests

# Run dashboard
PYTHONPATH=src streamlit run apps/streamlit/app.py
```

### 2. Backtest Rudometkin from UI

1. Start Streamlit (`streamlit run apps/streamlit/app.py`).
2. In sidebar:
   - Strategy: **Rudometkin MOC**.
   - Universe: point to `data/universe/rudometkin.parquet` (≥300 days D1).
   - Adjust Rudometkin parameters as needed.
3. In **Advanced Parameters**:
   - Choose Manual or YAML.
   - Use **"📋 Preview Effective Configuration"** to verify strategy, symbols,
     date range, and universe path.
4. Click **"Start backtest"**.

### 3. What the Pipeline Does

- **Stage 1 (Daily)**
  - Reads daily universe parquet.
  - Applies Rudometkin filters and ranks candidates.
  - Selects up to `max_daily_signals` per direction per day.
  - Writes filtered daily signals and returns symbol list.

- **Stage 2 (Intraday)**
  - Fetches **M1** for filtered symbols.
  - Resamples to M5/M15 for signal generation; uses M1 for fills.
  - Runs generic replay backtest and produces orders/fills/trades.

### 4. Inspect Performance & Robustness

- Each run writes `artifacts/backtests/<run>/run_log.json`.
- CLI summary:

  ```bash
  PYTHONPATH=src python -m cli.log_inspect artifacts/backtests/<run>/run_log.json
  ```

  Shows total measured time and per-step durations.

- UI summary:
  - Select a run → open **"Run log & performance"** expander.
  - See per-step durations and raw log entries.

### 5. Tests to Run for Rudometkin Changes

- Core:

  ```bash
  PYTHONPATH=src python -m pytest tests/test_rudometkin_moc_strategy.py
  PYTHONPATH=src python -m pytest tests/test_strategy_separation.py
  ```

- Full suite:

  ```bash
  PYTHONPATH=src python -m pytest tests
  ```

These validate:

- Long/short signal logic.
- Universe filtering (column & path).
- Two-stage capability flags and pipeline hooks.
- Rudometkin pipeline import without Streamlit.
