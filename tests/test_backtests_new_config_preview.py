from trading_dashboard.layouts.backtests import create_backtests_layout
from trading_dashboard.ui_ids import RUN


def test_new_backtest_config_preview_shows_base_yaml_parameters():
    layout = create_backtests_layout()
    text = str(layout)

    assert RUN.CONFIG_PREVIEW in text
    assert "backtest.initial_cash" in text
    assert "backtest.fixed_qty" in text
    assert "costs.commission_bps" in text
    assert "costs.slippage_bps" in text
