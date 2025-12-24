
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from signals import cli_rudometkin_moc
from signals import cli_inside_bar
from axiom_bt.contracts.signal_schema import SignalOutputSpec

@pytest.fixture
def mock_rudometkin_strategy():
    strategy = MagicMock()
    # Mock signal object
    signal = MagicMock()
    signal.timestamp = pd.Timestamp("2025-01-01 10:00:00", tz="UTC")
    signal.signal_type = "LONG"
    signal.entry_price = 100.0
    signal.stop_loss = 99.0
    signal.take_profit = 102.0
    signal.metadata = {"setup": "test_setup", "score": 0.9}

    strategy.generate_signals.return_value = [signal]
    return strategy

@pytest.fixture
def mock_inside_bar_strategy():
    strategy = MagicMock()
    # Mock signal object
    signal = MagicMock()
    signal.timestamp = pd.Timestamp("2025-01-01 10:00:00", tz="UTC")
    signal.signal_type = "LONG"
    signal.entry_price = 100.0
    signal.stop_loss = 99.0
    signal.take_profit = 102.0
    signal.metadata = {"setup": "inside_bar"}

    strategy.generate_signals.return_value = [signal]
    return strategy

def test_rudometkin_cli_validation(mock_rudometkin_strategy, tmp_path):
    """Test that Rudometkin CLI validates signals and outputs correct columns."""

    # Mock data
    df = pd.DataFrame({
        "Open": [100], "High": [101], "Low": [99], "Close": [100], "Volume": [1000]
    }, index=pd.DatetimeIndex(["2025-01-01 10:00:00"], tz="UTC"))

    with patch("signals.cli_rudometkin_moc._load_ohlcv", return_value=df), \
         patch("strategies.factory.create_strategy", return_value=mock_rudometkin_strategy), \
         patch("signals.cli_rudometkin_moc._infer_symbols", return_value=["TEST"]), \
         patch("pathlib.Path.exists", return_value=True):

        output_file = tmp_path / "signals.csv"
        args = [
            "--symbols", "TEST",
            "--output", str(output_file),
            "--data-path", str(tmp_path),
            "--current-snapshot", str(tmp_path / "current.csv")
        ]

        ret = cli_rudometkin_moc.main(args)
        assert ret == 0

        # Check output
        out_df = pd.read_csv(output_file)
        assert "strategy" in out_df.columns
        assert "strategy_version" in out_df.columns
        assert out_df.iloc[0]["strategy"] == "rudometkin_moc"
        assert out_df.iloc[0]["long_entry"] == 100.0

def test_inside_bar_cli_validation(mock_inside_bar_strategy, tmp_path):
    """Test that Inside Bar CLI validates signals and outputs correct columns."""

    # Mock IntradayStore
    with patch("signals.cli_inside_bar.IntradayStore") as MockStore, \
         patch("strategies.factory.create_strategy", return_value=mock_inside_bar_strategy), \
         patch("signals.cli_inside_bar._infer_symbols", return_value=["TEST"]):

        store = MockStore.return_value
        df = pd.DataFrame({
            "open": [100], "high": [101], "low": [99], "close": [100], "volume": [1000]
        }, index=pd.DatetimeIndex(["2025-01-01 10:00:00"], tz="UTC"))
        store.load.return_value = df

        output_file = tmp_path / "signals_ib.csv"
        args = [
            "--symbols", "TEST",
            "--output", str(output_file),
            "--data-path", str(tmp_path),
            "--current-snapshot", str(tmp_path / "current_ib.csv"),
            # Use a wide session window so the mocked timestamp always falls inside
            "--sessions", "09:00-12:00",
        ]

        ret = cli_inside_bar.main(args)
        assert ret == 0

        # Check output
        out_df = pd.read_csv(output_file)
        assert "strategy" in out_df.columns
        assert "strategy_version" in out_df.columns
        assert out_df.iloc[0]["strategy"] == "inside_bar"
        assert out_df.iloc[0]["long_entry"] == 100.0
