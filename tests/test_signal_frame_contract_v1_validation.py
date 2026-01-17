import pandas as pd
import pytest

from axiom_bt.contracts.signal_frame_contract_v1 import (
    ColumnSpec,
    SignalFrameSchemaV1,
    validate_signal_frame_v1,
    SignalFrameContractError,
)


def _schema():
    base = [
        ColumnSpec("timestamp", "datetime64[ns, UTC]", False, "base"),
        ColumnSpec("open", "float64", False, "base"),
        ColumnSpec("high", "float64", False, "base"),
        ColumnSpec("low", "float64", False, "base"),
        ColumnSpec("close", "float64", False, "base"),
        ColumnSpec("volume", "float64", False, "base"),
    ]
    generic = [
        ColumnSpec("symbol", "string", False, "generic"),
        ColumnSpec("timeframe", "string", False, "generic"),
        ColumnSpec("strategy_id", "string", False, "generic"),
        ColumnSpec("strategy_version", "string", False, "generic"),
        ColumnSpec("strategy_tag", "string", False, "generic"),
    ]
    strategy = [
        ColumnSpec("sig_long", "bool", False, "strategy"),
        ColumnSpec("sig_short", "bool", False, "strategy"),
        ColumnSpec("sig_side", "string", False, "strategy"),
        ColumnSpec("sig_reason", "string", False, "strategy"),
        ColumnSpec("sig_id", "string", False, "strategy"),
    ]
    return SignalFrameSchemaV1(
        strategy_id="s",
        strategy_tag="t",
        version="1.0.0",
        required_base=base,
        required_generic=generic,
        required_strategy=strategy,
    )


def _frame():
    ts = pd.date_range("2025-01-01", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": [1, 2, 3],
            "high": [1, 2, 3],
            "low": [1, 2, 3],
            "close": [1, 2, 3],
            "volume": [1, 1, 1],
            "symbol": "X",
            "timeframe": "M5",
            "strategy_id": "s",
            "strategy_version": "1.0.0",
            "strategy_tag": "t",
            "sig_long": [True, False, False],
            "sig_short": [False, False, True],
            "sig_side": ["LONG", "FLAT", "SHORT"],
            "sig_reason": ["r", "none", "r"],
            "sig_id": ["a", "b", "c"],
        }
    )
    return df


def test_valid_frame_passes():
    df = _frame()
    validate_signal_frame_v1(df, _schema())


def test_missing_column_fails():
    df = _frame().drop(columns=["sig_id"])
    with pytest.raises(SignalFrameContractError):
        validate_signal_frame_v1(df, _schema())


def test_sig_long_short_exclusive():
    df = _frame()
    df.loc[0, "sig_short"] = True
    with pytest.raises(SignalFrameContractError):
        validate_signal_frame_v1(df, _schema())


def test_sig_side_mismatch():
    df = _frame()
    df.loc[0, "sig_side"] = "FLAT"
    with pytest.raises(SignalFrameContractError):
        validate_signal_frame_v1(df, _schema())


def test_timestamp_naive_fails():
    df = _frame()
    df["timestamp"] = pd.date_range("2025-01-01", periods=3, freq="5min")  # naive
    with pytest.raises(SignalFrameContractError):
        validate_signal_frame_v1(df, _schema())
