
from pathlib import Path
import pandas as pd
from axiom_bt.intraday import IntradayStore, Timeframe

def test_intraday_store_contract_validation(tmp_path: Path, monkeypatch) -> None:
    """IntradayStore should validate data when ENABLE_CONTRACTS is true."""

    path = tmp_path / "INVALID_INTRADAY.parquet"

    # Create invalid data (Negative Volume)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=1, freq="5min", tz="UTC"),
        "Open": [1.0],
        "High": [1.5],
        "Low": [0.5],
        "Close": [1.2],
        "Volume": [-100],  # Negative volume
    })
    df.to_parquet(path)

    # Patch DATA_M5 in the intraday module where it is used
    import axiom_bt.intraday
    monkeypatch.setattr(axiom_bt.intraday, "DATA_M5", tmp_path)

    store = IntradayStore(default_tz="America/New_York")

    # 1. Without flag: should pass
    monkeypatch.setenv("ENABLE_CONTRACTS", "false")
    store.load("invalid_intraday", timeframe=Timeframe.M5)

    # 2. With flag: should fail
    monkeypatch.setenv("ENABLE_CONTRACTS", "true")
    import pytest
    with pytest.raises(ValueError, match="IntradayFrameSpec validation failed"):
        store.load("invalid_intraday", timeframe=Timeframe.M5)
