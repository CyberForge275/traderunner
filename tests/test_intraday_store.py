from __future__ import annotations

from pathlib import Path

import pandas as pd

from axiom_bt.intraday import IntradayStore, Timeframe


def test_intraday_store_normalizes_frame(tmp_path: Path, monkeypatch) -> None:
    """IntradayStore.load should normalize timestamp index and OHLCV columns."""

    # Create a dummy M5 parquet with timestamp column and OHLCV in title case
    path = tmp_path / "AAPL.parquet"
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=3, freq="5min", tz="UTC"),
            "Open": [1.0, 2.0, 3.0],
            "High": [1.5, 2.5, 3.5],
            "Low": [0.5, 1.5, 2.5],
            "Close": [1.2, 2.2, 3.2],
            "Volume": [100, 200, 300],
        }
    )
    df.to_parquet(path)

    # Patch DATA_M5 location to our tmp_path
    import axiom_bt.fs as fs

    monkeypatch.setattr(fs, "DATA_M5", tmp_path)

    store = IntradayStore(default_tz="America/New_York")
    frame = store.load("aapl", timeframe=Timeframe.M5)

    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert frame.index.name == "timestamp"
    assert frame.index.tz is not None
    # Ensure we converted to the configured timezone
    assert str(frame.index.tz) == "America/New_York"

