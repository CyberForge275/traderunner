from trading_dashboard.callbacks.run_backtest_callback import resolve_strategy_run_inputs
from trading_dashboard.callbacks.ssot_backtest_config_callback import resolve_run_control_policy


def test_perlentaucher_backtest_ui_policy_hides_symbol_and_timeframe_controls() -> None:
    policy = resolve_run_control_policy("perlentaucher_daily_scan")

    assert policy["symbols_style"] == {"display": "none"}
    assert policy["timeframe_style"] == {"display": "none"}
    assert policy["symbol_input_value"] == "ALL"
    assert policy["timeframe_value"] == "D1"


def test_non_perlentaucher_backtest_ui_policy_stays_visible() -> None:
    policy = resolve_run_control_policy("insidebar_intraday")

    assert policy["symbols_style"] == {"display": "block"}
    assert policy["timeframe_style"] == {"display": "block"}
    assert policy["symbol_input_value"] is None
    assert policy["timeframe_value"] is None


def test_perlentaucher_run_inputs_are_forced_to_all_and_d1() -> None:
    symbols, timeframe = resolve_strategy_run_inputs(
        "perlentaucher_daily_scan",
        "AAPL,MSFT",
        "M5",
    )

    assert symbols == "ALL"
    assert timeframe == "D1"


def test_other_strategy_run_inputs_are_unchanged() -> None:
    symbols, timeframe = resolve_strategy_run_inputs(
        "insidebar_intraday",
        "AAPL,MSFT",
        "M5",
    )

    assert symbols == "AAPL,MSFT"
    assert timeframe == "M5"
