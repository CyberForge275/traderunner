import pandas as pd

from trading_dashboard.components.time_columns import add_buy_sell_ny_columns


def test_buy_sell_ny_columns_buy_side():
    df = pd.DataFrame(
        {
            "side": ["BUY"],
            "entry_ts": ["2026-01-01T15:00:00Z"],
            "exit_ts": ["2026-01-01T16:00:00Z"],
        }
    )
    out = add_buy_sell_ny_columns(df)
    assert out.loc[0, "buy_ts_ny"].endswith("-0500")
    assert out.loc[0, "sell_ts_ny"].endswith("-0500")


def test_buy_sell_ny_columns_sell_side():
    df = pd.DataFrame(
        {
            "side": ["SELL"],
            "entry_ts": ["2026-01-01T15:00:00Z"],
            "exit_ts": ["2026-01-01T16:00:00Z"],
        }
    )
    out = add_buy_sell_ny_columns(df)
    # For SELL: buy happens at exit_ts, sell at entry_ts
    assert out.loc[0, "buy_ts_ny"].startswith("2026-01-01 11:00")
    assert out.loc[0, "sell_ts_ny"].startswith("2026-01-01 10:00")


def test_buy_sell_ny_handles_missing():
    df = pd.DataFrame(
        {
            "side": ["BUY"],
            "entry_ts": [None],
            "exit_ts": ["2026-01-01T16:00:00Z"],
        }
    )
    out = add_buy_sell_ny_columns(df)
    assert out.loc[0, "buy_ts_ny"] == ""
    assert out.loc[0, "sell_ts_ny"].endswith("-0500")
