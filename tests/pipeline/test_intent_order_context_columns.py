import pandas as pd

from axiom_bt.pipeline.signals import generate_intent


def test_generate_intent_adds_sig_context_columns():
    ts = pd.Timestamp("2026-01-15T14:35:00Z")
    signals_frame = pd.DataFrame(
        [
            {
                "template_id": "ib_tpl_1",
                "timestamp": ts,
                "symbol": "HOOD",
                "signal_side": "BUY",
                "entry_price": 100.0,
                "stop_price": 99.0,
                "take_profit_price": 102.0,
                "exit_ts": pd.NaT,
                "exit_reason": None,
                "atr": 0.5,
                "mother_high": 101.0,
                "mother_low": 98.0,
                "inside_bar": True,
            }
        ]
    )

    artifacts = generate_intent(signals_frame, "insidebar_intraday", "1.0.1", params={})
    events_intent = artifacts.events_intent

    assert "sig_atr" in events_intent.columns
    assert "sig_mother_high" in events_intent.columns
    assert "sig_mother_low" in events_intent.columns
    assert "sig_inside_bar" in events_intent.columns

    row = events_intent.iloc[0]
    assert row["sig_atr"] == 0.5
    assert row["sig_mother_high"] == 101.0
    assert row["sig_mother_low"] == 98.0
    assert row["sig_inside_bar"] == True
