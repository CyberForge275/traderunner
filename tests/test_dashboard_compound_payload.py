import pytest
from trading_dashboard.callbacks.run_backtest_callback import build_config_params

def test_build_config_params_legacy():
    snapshot = {
        "core": {"param1": 1},
        "tunable": {"param2": 2}
    }
    # Toggle OFF
    params = build_config_params(
        "insidebar_intraday", 
        "1.0.0", 
        snapshot, 
        [], 
        "cash_only"
    )
    
    assert params["param1"] == 1
    assert params["strategy_version"] == "1.0.0"
    assert "backtesting" not in params

def test_build_config_params_compound_on():
    snapshot = {
        "core": {"param1": 1},
        "tunable": {"param2": 2}
    }
    # Toggle ON
    params = build_config_params(
        "insidebar_intraday", 
        "1.0.0", 
        snapshot, 
        ["enabled"], 
        "cash_only"
    )
    
    assert params["backtesting"]["compound_sizing"] is True
    assert params["backtesting"]["compound_equity_basis"] == "cash_only"

def test_build_config_params_defaults():
    snapshot = {}
    # Toggle ON, No basis provided -> default cash_only
    params = build_config_params(
        "insidebar_intraday", 
        "1.0.0", 
        snapshot, 
        ["enabled"], 
        None
    )
    
    assert params["backtesting"]["compound_equity_basis"] == "cash_only"


def test_build_config_params_confirmed_breakout():
    snapshot = {
        "core": {"atr_period": 8},
        "tunable": {"lookback_candles": 50},
    }
    params = build_config_params(
        "confirmed_breakout_intraday",
        "1.0.0",
        snapshot,
        [],
        "cash_only",
    )
    assert params["atr_period"] == 8
    assert params["lookback_candles"] == 50
    assert params["strategy_version"] == "1.0.0"
