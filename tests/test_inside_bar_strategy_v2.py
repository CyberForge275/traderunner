import pandas as pd
import pytest

from strategies.inside_bar_v2.strategy import InsideBarStrategyV2


def _make_sample_frame() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01 09:00", periods=8, freq="5min")
    rows = []
    prices = [
        (100.0, 104.0, 96.0, 102.0),  # warm-up bar
        (102.0, 110.0, 100.0, 108.0),  # mother bar
        (108.0, 108.5, 101.5, 104.0),  # inside bar
        (104.0, 112.0, 103.5, 111.0),  # breakout
        (111.0, 113.0, 109.0, 110.5),
        (110.5, 111.5, 109.5, 110.0),
        (110.0, 110.5, 108.0, 108.5),
        (108.5, 109.0, 107.5, 108.0),
    ]
    for ts, (open_, high, low, close) in zip(timestamps, prices):
        rows.append(
            {
                "timestamp": ts.isoformat(),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1_000,
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture
def strategy_v2() -> InsideBarStrategyV2:
    return InsideBarStrategyV2()


def test_v2_generates_signal_with_cap(strategy_v2: InsideBarStrategyV2):
    data = _make_sample_frame()
    config = {
        "atr_period": 3,
        "risk_reward_ratio": 1.0,
        "inside_bar_mode": "inclusive",
        "min_mother_bar_size": 0.0,
        "breakout_confirmation": True,
        "min_master_body_ratio": 0.5,
        "execution_lag_bars": 0,
        "stop_distance_cap": 5.0,
    }

    signals = strategy_v2.generate_signals(data, "TEST", config)
    assert signals, "Expected at least one signal"
    long_signal = next(sig for sig in signals if sig.signal_type == "LONG")
    assert long_signal.entry_price == pytest.approx(110.0)
    assert long_signal.stop_loss == pytest.approx(100.0)
    assert long_signal.take_profit == pytest.approx(115.0)
    assert bool(long_signal.metadata.get("stop_cap_applied")) is True
    assert long_signal.metadata.get("execution_lag_bars") == 0


def test_v2_execution_lag_blocks_early_trigger(strategy_v2: InsideBarStrategyV2):
    data = _make_sample_frame()
    config = {
        "atr_period": 3,
        "risk_reward_ratio": 1.0,
        "inside_bar_mode": "inclusive",
        "min_mother_bar_size": 0.0,
        "breakout_confirmation": True,
        "min_master_body_ratio": 0.5,
        "execution_lag_bars": 3,
    }

    signals = strategy_v2.generate_signals(data, "TEST", config)
    assert not signals, "Signals should be delayed beyond available bars when lag is high"


def test_v2_filters_by_atr_and_body(strategy_v2: InsideBarStrategyV2):
    data = _make_sample_frame()
    config_atr = {
        "atr_period": 3,
        "risk_reward_ratio": 1.0,
        "inside_bar_mode": "inclusive",
        "min_mother_bar_size": 0.0,
        "breakout_confirmation": True,
        "min_master_body_ratio": 0.5,
        "max_master_range_atr_mult": 0.1,
    }

    suppressed = strategy_v2.generate_signals(data, "TEST", config_atr)
    assert not suppressed, "ATR suppression should reject the setup"

    config_body = {
        "atr_period": 3,
        "risk_reward_ratio": 1.0,
        "inside_bar_mode": "inclusive",
        "min_mother_bar_size": 0.0,
        "breakout_confirmation": True,
        "min_master_body_ratio": 0.95,
    }

    body_filtered = strategy_v2.generate_signals(data, "TEST", config_body)
    assert not body_filtered, "Body ratio filter should reject master candle"
