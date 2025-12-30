
from pathlib import Path
import pandas as pd
from axiom_bt.daily import DailyStore

def test_daily_store_contract_validation(tmp_path: Path, monkeypatch) -> None:
    """DailyStore should validate data when ENABLE_CONTRACTS is true."""

    path = tmp_path / "invalid.parquet"

    # Create invalid data (NaN in Open)
    df = pd.DataFrame({
        "Symbol": ["AAPL"],
        "Date": ["2025-01-01"],
        "Open": [None],  # NaN
        "High": [1.5],
        "Low": [0.5],
        "Close": [1.2],
        "Volume": [100],
    })
    df.to_parquet(path)

    store = DailyStore(default_tz="America/New_York")

    # 1. Without flag: should pass (legacy behavior)
    monkeypatch.setenv("ENABLE_CONTRACTS", "false")
    store.load_universe(universe_path=path)

    # 2. With flag: should fail
    monkeypatch.setenv("ENABLE_CONTRACTS", "true")
    import pytest
    with pytest.raises(ValueError, match="DailyFrameSpec validation failed"):
        store.load_universe(universe_path=path)
