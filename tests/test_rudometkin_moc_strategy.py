"""Tests for the Rudometkin MOC strategy implementation."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.strategies.rudometkin_moc.strategy import RudometkinMOCStrategy
from src.strategies.rudometkin_moc import pipeline as rudometkin_pipeline


@pytest.fixture
def base_dataframe() -> pd.DataFrame:
    """Create a base OHLCV frame with 210 trading days."""

    length = 210
    start = datetime(2022, 1, 3)
    dates = [start + timedelta(days=i) for i in range(length)]

    close = np.linspace(50, 120, length)
    open_price = close * 1.002  # small gap up
    high = np.maximum(open_price, close) * 1.01
    low = np.minimum(open_price, close) * 0.99
    volume = np.full(length, 2_000_000)

    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


@pytest.fixture
def universe_file(tmp_path: Path) -> Path:
    path = tmp_path / "rudometkin.parquet"
    frame = pd.DataFrame({"symbol": ["TEST", "SPY"]})
    frame.to_parquet(path)
    return path


@pytest.fixture
def strategy(monkeypatch: pytest.MonkeyPatch) -> RudometkinMOCStrategy:
    """Instantiate the strategy with patched indicator calculations."""

    strat = RudometkinMOCStrategy()

    def fake_indicators(
        df: pd.DataFrame,
        *,
        adx_period: int,
        sma_period: int,
        crsi_rank: int,
        crsi_price: int,
        crsi_streak: int,
    ) -> pd.DataFrame:
        df = df.copy()

        def _series(name: str, default: float) -> pd.Series:
            if name in df.columns:
                return df[name].astype(float).fillna(default)
            return pd.Series(default, index=df.index, dtype=float)

        df["sma200"] = df["close"] - 1
        df["atr2"] = 0.02 * df["close"]
        df["atr10"] = 0.05 * df["close"]
        df["atr40"] = 0.05 * df["close"]
        df["roc5"] = _series("override_roc5", 5.0)
        df["adx"] = _series("override_adx", 50.0)
        df["crsi"] = _series("override_crsi", 50.0)
        df["avg_vol50"] = df["volume"].rolling(50, min_periods=50).mean()
        return df

    monkeypatch.setattr(strat, "_calculate_indicators", fake_indicators)
    return strat


def test_long_signal_generation(
    strategy: RudometkinMOCStrategy,
    base_dataframe: pd.DataFrame,
    universe_file: Path,
) -> None:
    """Strategy should emit a long signal when the long setup is satisfied."""

    df = base_dataframe.copy()
    df.loc[df.index[-1], "open"] = df.loc[df.index[-1], "close"] * 1.05
    df.loc[df.index[-1], "override_roc5"] = 12.5

    signals = strategy.generate_signals(
        df,
        symbol="TEST",
        config={"universe_path": str(universe_file)},
    )

    assert len(signals) == 1
    sig = signals[0]
    assert sig.signal_type == "LONG"
    expected_entry = df.loc[df.index[-1], "close"] * (1 - 0.035)
    assert pytest.approx(sig.entry_price, rel=1e-6) == expected_entry
    assert sig.metadata.get("setup") == "moc_long"
    assert sig.metadata.get("exit_type") == "MOC"
    assert sig.metadata.get("score") == pytest.approx(0.05)


def test_short_signal_generation(
    strategy: RudometkinMOCStrategy,
    base_dataframe: pd.DataFrame,
    universe_file: Path,
) -> None:
    """Strategy should emit a short signal when the short setup is satisfied."""

    df = base_dataframe.copy()
    df.loc[df.index[-1], "override_crsi"] = 85.0
    df.loc[df.index[-1], "override_roc5"] = 18.0
    df.loc[df.index[-1], "open"] = df.loc[df.index[-1], "close"]

    signals = strategy.generate_signals(
        df,
        symbol="TEST",
        config={"universe_path": str(universe_file)},
    )

    assert len(signals) == 1
    sig = signals[0]
    assert sig.signal_type == "SHORT"
    expected_entry = df.loc[df.index[-1], "close"] * (1 + 0.05)
    assert pytest.approx(sig.entry_price, rel=1e-6) == expected_entry
    assert sig.metadata.get("setup") == "moc_short"
    assert sig.metadata.get("score") == pytest.approx(18.0)


def test_universe_column_filters_symbols(
    strategy: RudometkinMOCStrategy,
    base_dataframe: pd.DataFrame,
    universe_file: Path,
) -> None:
    """Universe column should block symbols that are not members."""

    df = base_dataframe.copy()
    df["in_rui"] = True
    df.loc[df.index[-1], "in_rui"] = False
    df.loc[df.index[-1], "open"] = df.loc[df.index[-1], "close"] * 1.05

    signals = strategy.generate_signals(
        df,
        symbol="TEST",
        config={
            "universe_column": "in_rui",
            "universe_path": str(universe_file),
        },
    )

    assert signals == []


def test_universe_path_filters_unknown_symbol(
    strategy: RudometkinMOCStrategy,
    base_dataframe: pd.DataFrame,
    universe_file: Path,
) -> None:
    df = base_dataframe.copy()
    df.loc[df.index[-1], "override_crsi"] = 85.0
    df.loc[df.index[-1], "override_roc5"] = 18.0
    df.loc[df.index[-1], "open"] = df.loc[df.index[-1], "close"]

    signals = strategy.generate_signals(
        df,
        symbol="UNKNOWN",
        config={"universe_path": str(universe_file)},
    )

    assert signals == []


def test_run_daily_scan_missing_universe_columns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_daily_scan should return [] when symbol/date columns are missing."""

    # Create a malformed universe parquet (no symbol / date columns)
    bad_universe = tmp_path / "bad_universe.parquet"
    pd.DataFrame({"ts_id": [1, 2, 3]}).to_parquet(bad_universe)

    class DummyFetch:
        timeframe = "D1"
        start = None
        end = None
        use_sample = False
        force_refresh = False
        data_dir = tmp_path
        data_dir_m1 = tmp_path

        def symbols_to_fetch(self):  # pragma: no cover - not used here
            return []

        def needs_force_refresh(self):  # pragma: no cover - not used here
            return False

        def stale_reasons(self):  # pragma: no cover - not used here
            return {}

    class DummyStrategyMeta:
        strategy_name = "rudometkin_moc"
        timezone = "Europe/Berlin"
        orders_source = tmp_path / "signals.csv"
        default_strategy_config = {"universe_path": str(bad_universe)}

    class DummyPipeline:
        run_name = "test_run"
        fetch = DummyFetch()
        symbols = ["TEST"]
        strategy = DummyStrategyMeta()
        config_path = None
        config_payload = None

    # In a non-Streamlit environment, this should simply return []
    result = rudometkin_pipeline.run_daily_scan(DummyPipeline(), max_daily_signals=5)
    assert result == []
