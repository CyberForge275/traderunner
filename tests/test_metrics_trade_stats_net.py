import pandas as pd

from axiom_bt.metrics import trade_stats


def test_trade_stats_uses_net_and_gross_columns_when_present():
    trades = pd.DataFrame(
        [
            {"pnl": 5.0, "gross_pnl": 5.0, "net_pnl": 4.0},
            {"pnl": -3.0, "gross_pnl": -3.0, "net_pnl": -4.0},
        ]
    )

    stats = trade_stats(trades)
    assert stats["gross_pnl"] == 2.0
    assert stats["net_pnl"] == 0.0
