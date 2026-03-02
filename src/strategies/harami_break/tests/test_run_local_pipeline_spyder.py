from strategies.harami_break.tools.run_local_pipeline_spyder import _assemble_strategy_params


def test_assemble_strategy_params_enables_compound_sizing_by_default():
    params = _assemble_strategy_params(
        core={"session_timezone": "America/New_York"},
        tunable={"strict_mode": False},
        strategy_version="1.0.0",
        symbol="HOOD",
        timeframe="M5",
        requested_end="2026-02-26",
        lookback_days=30,
        commission_bps=2.0,
        slippage_bps=1.0,
    )

    assert params["backtesting"]["compound_sizing"] is True
    assert params["backtesting"]["compound_equity_basis"] == "cash_only"
    assert params["fees_bps"] == 2.0
    assert params["slippage_bps"] == 1.0
