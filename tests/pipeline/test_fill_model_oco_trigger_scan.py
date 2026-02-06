import pandas as pd
import numpy as np

from axiom_bt.pipeline.fill_model import generate_fills


def _bars(ts_list, opens, highs, lows, closes):
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(ts_list, utc=True),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
        }
    )


def _intent_row(template_id, side, signal_ts, entry, stop, tp, oco_group_id, valid_to):
    return {
        "template_id": template_id,
        "signal_ts": pd.to_datetime(signal_ts, utc=True),
        "symbol": "TEST",
        "side": side,
        "entry_price": entry,
        "stop_price": stop,
        "take_profit_price": tp,
        "strategy_id": "insidebar_intraday",
        "strategy_version": "1.0.2",
        "oco_group_id": oco_group_id,
        "order_valid_to_ts": pd.to_datetime(valid_to, utc=True),
    }


def test_no_fill_without_trigger_scan():
    bars = _bars(
        ["2025-01-01 10:00:00+00:00", "2025-01-01 10:05:00+00:00"],
        [100, 100],
        [101, 101],
        [99, 99],
        [100, 100],
    )
    intents = pd.DataFrame(
        [
            _intent_row(
                "tmpl_1",
                "BUY",
                "2025-01-01 10:00:00+00:00",
                105.0,
                95.0,
                110.0,
                "g1",
                "2025-01-01 10:05:00+00:00",
            )
        ]
    )
    fills = generate_fills(
        intents,
        bars,
        order_validity_policy="session_end",
        session_timezone="America/New_York",
        session_filter=["09:30-16:00"],
    ).fills
    assert (fills["reason"] == "signal_fill").sum() == 0


def test_oco_cancel_on_first_fill():
    bars = _bars(
        [
            "2025-01-01 10:00:00+00:00",
            "2025-01-01 10:05:00+00:00",
        ],
        [100, 100],
        [111, 111],
        [99, 99],
        [105, 105],
    )
    intents = pd.DataFrame(
        [
            _intent_row(
                "tmpl_buy",
                "BUY",
                "2025-01-01 10:00:00+00:00",
                110.0,
                100.0,
                120.0,
                "g2",
                "2025-01-01 10:05:00+00:00",
            ),
            _intent_row(
                "tmpl_sell",
                "SELL",
                "2025-01-01 10:00:00+00:00",
                90.0,
                100.0,
                80.0,
                "g2",
                "2025-01-01 10:05:00+00:00",
            ),
        ]
    )
    fills = generate_fills(
        intents,
        bars,
        order_validity_policy="session_end",
        session_timezone="America/New_York",
        session_filter=["09:30-16:00"],
    ).fills
    assert (fills["reason"] == "signal_fill").sum() == 1
    assert (fills["reason"] == "order_cancelled_oco").sum() == 1
    cancelled = fills[fills["reason"] == "order_cancelled_oco"].iloc[0]
    assert cancelled["template_id"] == "tmpl_sell"


def test_ambiguous_same_bar_no_fill():
    bars = _bars(
        ["2025-01-01 10:00:00+00:00"],
        [100],
        [120],
        [80],
        [100],
    )
    intents = pd.DataFrame(
        [
            _intent_row(
                "tmpl_buy",
                "BUY",
                "2025-01-01 10:00:00+00:00",
                110.0,
                100.0,
                120.0,
                "g3",
                "2025-01-01 10:00:00+00:00",
            ),
            _intent_row(
                "tmpl_sell",
                "SELL",
                "2025-01-01 10:00:00+00:00",
                90.0,
                100.0,
                80.0,
                "g3",
                "2025-01-01 10:00:00+00:00",
            ),
        ]
    )
    fills = generate_fills(
        intents,
        bars,
        order_validity_policy="session_end",
        session_timezone="America/New_York",
        session_filter=["09:30-16:00"],
    ).fills
    assert (fills["reason"] == "signal_fill").sum() == 0
    assert (fills["reason"] == "order_ambiguous_no_fill").sum() == 2


def test_netting_blocks_second_group():
    bars = _bars(
        [
            "2025-01-01 10:00:00+00:00",
            "2025-01-01 10:05:00+00:00",
            "2025-01-01 10:10:00+00:00",
        ],
        [100, 100, 100],
        [111, 111, 111],
        [99, 99, 99],
        [105, 105, 105],
    )
    intents = pd.DataFrame(
        [
            _intent_row(
                "tmpl_buy_1",
                "BUY",
                "2025-01-01 10:00:00+00:00",
                110.0,
                100.0,
                120.0,
                "g1",
                "2025-01-01 10:10:00+00:00",
            ),
            _intent_row(
                "tmpl_sell_1",
                "SELL",
                "2025-01-01 10:00:00+00:00",
                90.0,
                100.0,
                80.0,
                "g1",
                "2025-01-01 10:10:00+00:00",
            ),
            _intent_row(
                "tmpl_buy_2",
                "BUY",
                "2025-01-01 10:05:00+00:00",
                110.0,
                100.0,
                120.0,
                "g2",
                "2025-01-01 10:10:00+00:00",
            ),
            _intent_row(
                "tmpl_sell_2",
                "SELL",
                "2025-01-01 10:05:00+00:00",
                90.0,
                100.0,
                80.0,
                "g2",
                "2025-01-01 10:10:00+00:00",
            ),
        ]
    )
    fills = generate_fills(
        intents,
        bars,
        order_validity_policy="session_end",
        session_timezone="America/New_York",
        session_filter=["09:30-16:00"],
    ).fills
    assert (fills["reason"] == "signal_fill").sum() == 1
    assert (fills["reason"] == "order_rejected_netting_open_position").sum() == 1
