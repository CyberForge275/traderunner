import pandas as pd

from strategies.inside_bar.session_logic import generate_signals
from strategies.inside_bar.config import InsideBarConfig, SessionFilter
from strategies.intent_registry import get_strategy_adapter
from axiom_bt.pipeline.fill_model import generate_fills


def generate_intent(signals_frame, strategy_id, strategy_version, params):
    return get_strategy_adapter(strategy_id).generate_intent(
        signals_frame, strategy_id, strategy_version, params
    )


def _bars():
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2025-01-01 15:20:00+00:00",
                    "2025-01-01 15:25:00+00:00",
                    "2025-01-01 15:30:00+00:00",
                ],
                utc=True,
            ),
            "open": [100.0, 100.0, 100.0],
            "high": [102.0, 101.0, 101.0],
            "low": [98.0, 99.0, 99.0],
            "close": [101.0, 100.0, 100.0],
            "atr": [1.0, 1.0, 1.0],
            "is_inside_bar": [False, True, False],
            "mother_bar_high": [102.0, 102.0, 102.0],
            "mother_bar_low": [98.0, 98.0, 98.0],
        }
    )


def _config():
    cfg = InsideBarConfig(
        inside_bar_definition_mode="mb_body_oc__ib_hl",
        atr_period=8,
        risk_reward_ratio=2.0,
        min_mother_bar_size=0.5,
        breakout_confirmation=True,
        inside_bar_mode="inclusive",
        session_timezone="America/New_York",
        session_windows=["09:30-16:00"],
        max_trades_per_session=1,
        entry_level_mode="mother_bar",
        stop_distance_cap_ticks=40,
        tick_size=0.01,
        order_validity_policy="session_end",
        order_validity_minutes=60,
        valid_from_policy="signal_ts",
        trigger_must_be_within_session=True,
        netting_mode="one_position_per_symbol",
    )
    # attach timeframe_minutes dynamically (config does not declare it)
    setattr(cfg, "timeframe_minutes", 5)
    return cfg


def test_signal_ts_is_next_bar_start():
    df = _bars()
    cfg = _config()
    signals = generate_signals(df, "TEST", cfg)
    assert signals, "signals should be generated"
    ib_ts = pd.to_datetime("2025-01-01 15:25:00+00:00", utc=True)
    expected = ib_ts + pd.Timedelta(minutes=5)
    assert signals[0].timestamp == expected


def test_events_intent_signal_ts_next_bar():
    df = _bars()
    cfg = _config()
    signals = generate_signals(df, "TEST", cfg)
    sf = pd.DataFrame([
        {
            "timestamp": signals[0].timestamp,
            "symbol": "TEST",
            "signal_side": signals[0].side,
            "signal_reason": "inside_bar",
            "entry_price": signals[0].entry_price,
            "stop_price": signals[0].stop_loss,
            "take_profit_price": signals[0].take_profit,
            "template_id": "tmpl_buy",
            "oco_group_id": "g1",
        }
    ])
    art = generate_intent(
        sf,
        "insidebar_intraday",
        "1.0.2",
        {
            "order_validity_policy": "session_end",
            "session_timezone": "America/New_York",
            "session_filter": ["09:30-16:00"],
            "valid_from_policy": "signal_ts",
            "timeframe_minutes": 5,
        },
    )
    assert pd.to_datetime(art.events_intent.iloc[0]["signal_ts"], utc=True) == signals[0].timestamp


def test_no_fill_before_signal_ts():
    bars = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
            "2025-01-01 15:25:00+00:00",
            "2025-01-01 15:30:00+00:00",
                ],
                utc=True,
            ),
            "open": [100.0, 100.0],
            "high": [120.0, 120.0],
            "low": [80.0, 80.0],
            "close": [100.0, 100.0],
        }
    )
    intents = pd.DataFrame(
        [
            {
                "template_id": "tmpl_buy",
                "signal_ts": pd.to_datetime("2025-01-01 15:30:00+00:00", utc=True),
                "symbol": "TEST",
                "side": "BUY",
                "entry_price": 110.0,
                "stop_price": 100.0,
                "take_profit_price": 120.0,
                "strategy_id": "insidebar_intraday",
                "strategy_version": "1.0.2",
                "oco_group_id": "g1",
                "order_valid_to_ts": pd.to_datetime("2025-01-01 15:30:00+00:00", utc=True),
            }
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
    assert fills.iloc[0]["fill_ts"] == pd.to_datetime("2025-01-01 15:30:00+00:00", utc=True)
