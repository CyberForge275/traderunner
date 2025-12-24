import pandas as pd

from trading_dashboard.plots.trade_inspector_plot import build_trade_chart


def test_build_trade_chart_stable_layout():
    trade = pd.Series({
        "entry_ts": "2024-01-01T10:00:00Z",
        "exit_ts": "2024-01-01T10:05:00Z",
        "entry_price": 100.0,
        "exit_price": 101.0,
    })
    bars = pd.DataFrame(
        {
            "open": [99.5, 100.5],
            "high": [100.5, 101.5],
            "low": [99.0, 100.0],
            "close": [100.4, 101.0],
        },
        index=pd.to_datetime(["2024-01-01T10:00:00Z", "2024-01-01T10:05:00Z"], utc=True),
    )

    fig1 = build_trade_chart(trade, bars)
    fig2 = build_trade_chart(trade, bars)

    assert fig1.layout.height == 600
    assert fig1.layout.width == 900
    assert fig1.layout.uirevision == "constant"
    assert fig1.layout.height == fig2.layout.height
    assert fig1.layout.width == fig2.layout.width
