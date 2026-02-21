import pandas as pd
import pytest

from strategies.intent_registry import get_strategy_adapter


def _generate_intent(signals_frame, strategy_id, strategy_version, params):
    return get_strategy_adapter(strategy_id).generate_intent(
        signals_frame, strategy_id, strategy_version, params
    )


@pytest.mark.parametrize(
    ("strategy_id", "strategy_version"),
    [("insidebar_intraday", "1.0.3"), ("confirmed_breakout_intraday", "1.0.1")],
)
def test_valid_from_policy_signal_ts_is_respected(strategy_id, strategy_version):
    ts = pd.Timestamp("2025-05-09 14:15:00+00:00")
    signals_frame = pd.DataFrame(
        [
            {
                "template_id": "tpl_1",
                "timestamp": ts,
                "symbol": "HOOD",
                "signal_side": "BUY",
                "entry_price": 100.0,
                "stop_price": 99.0,
                "take_profit_price": 102.0,
                "oco_group_id": "g1",
            }
        ]
    )
    params = {
        "valid_from_policy": "signal_ts",
        "timeframe_minutes": 15,
    }

    artifacts = _generate_intent(signals_frame, strategy_id, strategy_version, params=params)
    row = artifacts.events_intent.iloc[0]
    assert row["dbg_effective_valid_from_policy"] == "signal_ts"
    assert pd.Timestamp(row["dbg_valid_from_ts_utc"]).tz_convert("UTC") == ts


@pytest.mark.parametrize(
    ("strategy_id", "strategy_version"),
    [("insidebar_intraday", "1.0.3"), ("confirmed_breakout_intraday", "1.0.1")],
)
def test_valid_from_policy_next_bar_adds_one_timeframe(strategy_id, strategy_version):
    ts = pd.Timestamp("2025-05-09 14:15:00+00:00")
    signals_frame = pd.DataFrame(
        [
            {
                "template_id": "tpl_2",
                "timestamp": ts,
                "symbol": "HOOD",
                "signal_side": "SELL",
                "entry_price": 100.0,
                "stop_price": 101.0,
                "take_profit_price": 98.0,
                "oco_group_id": "g2",
            }
        ]
    )
    params = {
        "valid_from_policy": "next_bar",
        "timeframe_minutes": 15,
    }

    artifacts = _generate_intent(signals_frame, strategy_id, strategy_version, params=params)
    row = artifacts.events_intent.iloc[0]
    assert row["dbg_effective_valid_from_policy"] == "next_bar"
    assert pd.Timestamp(row["dbg_valid_from_ts_utc"]).tz_convert("UTC") == ts + pd.Timedelta(minutes=15)
