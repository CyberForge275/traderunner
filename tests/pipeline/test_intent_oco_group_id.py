import pandas as pd

from axiom_bt.pipeline.signals import generate_intent


def _signal_row(ts, side, entry, stop, tp, template_id, oco_group_id):
    return {
        "timestamp": pd.to_datetime(ts, utc=True),
        "symbol": "TEST",
        "signal_side": side,
        "signal_reason": "inside_bar",
        "entry_price": entry,
        "stop_price": stop,
        "take_profit_price": tp,
        "template_id": template_id,
        "oco_group_id": oco_group_id,
    }


def test_generate_intent_requires_oco_group_id_for_signals():
    df = pd.DataFrame([
        _signal_row("2025-01-01 15:00:00+00:00", "BUY", 110.0, 100.0, 120.0, "tmpl_buy", "g1"),
        _signal_row("2025-01-01 15:00:00+00:00", "SELL", 90.0, 100.0, 80.0, "tmpl_sell", "g1"),
    ])
    art = generate_intent(df, "insidebar_intraday", "1.0.2", {
        "order_validity_policy": "session_end",
        "session_timezone": "America/New_York",
        "session_filter": ["09:30-16:00"],
        "valid_from_policy": "signal_ts",
        "timeframe_minutes": 5,
    })
    assert set(art.events_intent["oco_group_id"]) == {"g1"}
