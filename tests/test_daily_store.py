from __future__ import annotations

from pathlib import Path

import pandas as pd

from axiom_bt.daily import DailySpec, DailyStore, DailySourceType


def test_daily_store_load_universe_normalizes_schema(tmp_path: Path) -> None:
    """DailyStore.load_universe should standardize rudometkin-like universe parquet."""

    path = tmp_path / "rudometkin.parquet"

    # Simulate rudometkin universe: symbol + Date + OHLCV
    df = pd.DataFrame(
        {
            "Symbol": ["AAPL", "AAPL"],
            "Date": ["2025-01-01", "2025-01-02"],
            "Open": [1.0, 2.0],
            "High": [1.5, 2.5],
            "Low": [0.5, 1.5],
            "Close": [1.2, 2.2],
            "Volume": [100, 200],
        }
    )
    df.to_parquet(path)

    store = DailyStore(default_tz="America/New_York")
    universe = store.load_universe(universe_path=path)

    assert list(universe.columns) == [
        "symbol",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    assert set(universe["symbol"]) == {"AAPL"}
    assert universe["timestamp"].dt.tz is not None


def test_daily_store_load_window_with_lookback(tmp_path: Path) -> None:
    path = tmp_path / "universe.parquet"

    df = pd.DataFrame(
        {
            "Symbol": ["AAPL"] * 5,
            "Date": pd.date_range("2025-01-01", periods=5, freq="D"),
            "Open": range(5),
            "High": range(5),
            "Low": range(5),
            "Close": range(5),
            "Volume": [100] * 5,
        }
    )
    df.to_parquet(path)

    store = DailyStore(default_tz="America/New_York")
    spec = DailySpec(
        symbols=["AAPL"],
        start="2025-01-04",
        end="2025-01-05",
        tz="America/New_York",
        source_type=DailySourceType.UNIVERSE,
        universe_path=path,
    )

    window = store.load_window(spec, lookback_days=2)

    # With start=2025-01-04 and lookback_days=2 we expect at least
    # 2 extra days of history plus the requested range in the
    # target timezone.
    dates = sorted(window["timestamp"].dt.date.unique())
    assert len(dates) >= 3

