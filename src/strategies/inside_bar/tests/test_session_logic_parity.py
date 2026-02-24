import pandas as pd

from ..config import InsideBarConfig
from ..session_logic import generate_signals


def test_session_logic_outputs_are_stable_for_reference_fixture():
    df = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2025-01-02T10:00:00Z"),
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "atr": 1.0,
                "is_inside_bar": False,
                "mother_bar_high": None,
                "mother_bar_low": None,
            },
            {
                "timestamp": pd.Timestamp("2025-01-02T10:05:00Z"),
                "open": 101.0,
                "high": 104.0,
                "low": 96.0,
                "close": 101.0,
                "atr": 1.0,
                "is_inside_bar": True,
                "mother_bar_high": 105.0,
                "mother_bar_low": 95.0,
                "mother_body_fraction": 0.2,
                "inside_body_fraction": 0.1,
            },
            {
                "timestamp": pd.Timestamp("2025-01-02T10:10:00Z"),
                "open": 101.0,
                "high": 106.0,
                "low": 94.0,
                "close": 102.0,
                "atr": 1.0,
                "is_inside_bar": False,
                "mother_bar_high": None,
                "mother_bar_low": None,
            },
        ]
    )

    cfg = InsideBarConfig(
        inside_bar_definition_mode="mb_body_oc__ib_hl",
        atr_period=1,
        risk_reward_ratio=2.0,
        min_mother_bar_size=0.0,
        breakout_confirmation=True,
        inside_bar_mode="inclusive",
        session_timezone="UTC",
        session_windows=["00:00-23:59"],
        timeframe_minutes=5,
        order_validity_policy="session_end",
        valid_from_policy="signal_ts",
        stop_cap_atr=10.0,
        max_position_pct=100.0,
        min_mother_body_fraction=0.0,
        min_inside_body_fraction=0.0,
        max_pattern_age_candles=None,
        max_deviation_atr=None,
        max_position_loss_pct_equity=None,
    )

    signals = generate_signals(df, "TEST", cfg)

    assert len(signals) == 2
    snapshot = [
        (
            s.side,
            s.timestamp.isoformat(),
            s.entry_price,
            s.stop_loss,
            s.take_profit,
            s.metadata["mother_high"],
            s.metadata["mother_low"],
        )
        for s in signals
    ]
    assert snapshot == [
        ("BUY", "2025-01-02T10:10:00+00:00", 105.0, 95.0, 125.0, 105.0, 95.0),
        ("SELL", "2025-01-02T10:10:00+00:00", 95.0, 105.0, 75.0, 105.0, 95.0),
    ]
