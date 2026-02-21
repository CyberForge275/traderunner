import pandas as pd

from strategies.confirmed_breakout import extend_insidebar_signal_frame_from_core
from strategies.confirmed_breakout.models import RawSignal


EXPECTED_COLUMNS = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "symbol",
    "timeframe",
    "strategy_id",
    "strategy_version",
    "strategy_tag",
    "atr",
    "inside_bar",
    "mother_high",
    "mother_low",
    "breakout_long",
    "breakout_short",
    "signal_side",
    "signal_reason",
    "entry_price",
    "stop_price",
    "take_profit_price",
    "template_id",
    "exit_ts",
    "exit_reason",
    "mother_ts",
    "inside_ts",
    "trigger_ts",
    "breakout_level",
    "order_expired",
    "order_expire_reason",
    "oco_group_id",
]


def _bars() -> pd.DataFrame:
    ts = pd.date_range("2026-02-16 14:30:00+00:00", periods=9, freq="5min")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0, 100.5, 100.8, 102.0, 101.6, 101.3, 103.0, 102.8, 102.7],
            # Keep mother/inside ranges around ratio ~0.8 for accepted fixtures.
            "high": [101.2, 100.9, 101.1, 102.0, 101.8, 101.5, 103.2, 102.9, 102.8],
            "low": [100.2, 100.1, 100.6, 101.0, 101.0, 101.0, 102.4, 102.3, 102.5],
            "close": [101.0, 100.7, 100.9, 101.2, 101.2, 101.1, 103.1, 102.6, 102.75],
            "volume": [1000] * 9,
        }
    )


def _params(**overrides) -> dict:
    base = {
        "symbol": "TEST",
        "timeframe": "M5",
        "timeframe_minutes": 5,
        "strategy_version": "1.0.0",
        "inside_bar_definition_mode": "mb_high__ib_high_and_close_in_mb_range",
    }
    base.update(overrides)
    return base


def test_confirmed_breakout_intraday_schema_unchanged(monkeypatch):
    bars = _bars()

    def _signals(*_args, **_kwargs):
        ts = pd.to_datetime(bars.loc[2, "timestamp"], utc=True)
        return [
            RawSignal(
                timestamp=ts,
                side="BUY",
                entry_price=101.0,
                stop_loss=100.5,
                take_profit=102.0,
                metadata={"ib_idx": 1, "sig_idx": 2},
            )
        ]

    monkeypatch.setattr("strategies.confirmed_breakout.InsideBarCore.process_data", _signals)

    out = extend_insidebar_signal_frame_from_core(bars, _params())

    assert list(out.columns) == EXPECTED_COLUMNS
    assert pd.api.types.is_bool_dtype(out["breakout_long"])
    assert pd.api.types.is_bool_dtype(out["breakout_short"])
    assert pd.api.types.is_bool_dtype(out["inside_bar"])
    assert out["signal_side"].dtype == object


def test_same_color_required_and_continuation_filters_one_side_only(monkeypatch):
    bars = _bars()

    def _signals(*_args, **_kwargs):
        return [
            # GG -> only BUY should remain
            RawSignal(
                timestamp=pd.to_datetime(bars.loc[2, "timestamp"], utc=True),
                side="BUY",
                entry_price=101.0,
                stop_loss=100.5,
                take_profit=102.0,
                metadata={"ib_idx": 1, "sig_idx": 2},
            ),
            RawSignal(
                timestamp=pd.to_datetime(bars.loc[2, "timestamp"], utc=True),
                side="SELL",
                entry_price=101.0,
                stop_loss=101.5,
                take_profit=100.0,
                metadata={"ib_idx": 1, "sig_idx": 2},
            ),
            # RR -> only SELL should remain
            RawSignal(
                timestamp=pd.to_datetime(bars.loc[5, "timestamp"], utc=True),
                side="BUY",
                entry_price=101.1,
                stop_loss=100.9,
                take_profit=101.8,
                metadata={"ib_idx": 4, "sig_idx": 5},
            ),
            RawSignal(
                timestamp=pd.to_datetime(bars.loc[5, "timestamp"], utc=True),
                side="SELL",
                entry_price=101.1,
                stop_loss=101.4,
                take_profit=100.5,
                metadata={"ib_idx": 4, "sig_idx": 5},
            ),
            # Mixed (GR) -> both sides must be dropped (same_color required)
            RawSignal(
                timestamp=pd.to_datetime(bars.loc[8, "timestamp"], utc=True),
                side="BUY",
                entry_price=102.75,
                stop_loss=102.5,
                take_profit=103.2,
                metadata={"ib_idx": 7, "sig_idx": 8},
            ),
            RawSignal(
                timestamp=pd.to_datetime(bars.loc[8, "timestamp"], utc=True),
                side="SELL",
                entry_price=102.75,
                stop_loss=102.9,
                take_profit=102.2,
                metadata={"ib_idx": 7, "sig_idx": 8},
            ),
        ]

    monkeypatch.setattr("strategies.confirmed_breakout.InsideBarCore.process_data", _signals)

    out = extend_insidebar_signal_frame_from_core(bars, _params())
    signal_rows = out[out["signal_side"].notna()].copy()

    gg_rows = signal_rows[signal_rows["timestamp"] == pd.to_datetime(bars.loc[2, "timestamp"], utc=True)]
    rr_rows = signal_rows[signal_rows["timestamp"] == pd.to_datetime(bars.loc[5, "timestamp"], utc=True)]
    mixed_rows = signal_rows[signal_rows["timestamp"] == pd.to_datetime(bars.loc[8, "timestamp"], utc=True)]

    assert set(gg_rows["signal_side"].tolist()) == {"BUY"}
    assert set(rr_rows["signal_side"].tolist()) == {"SELL"}
    assert mixed_rows.empty


def test_range_ratio_gate_blocks_outside_band_and_zero_mother_range(monkeypatch):
    bars = _bars()
    # ratio=0.73 for GG candidate at ib_idx=1 -> allowed with tunable min=0.72
    bars.loc[0, ["high", "low"]] = [101.2, 100.2]  # mother range=1.0
    bars.loc[1, ["high", "low"]] = [100.93, 100.20]  # inside range=0.73

    # ratio=0.70 for RR candidate at ib_idx=4 -> blocked
    bars.loc[3, ["high", "low"]] = [102.0, 101.0]  # mother range=1.0
    bars.loc[4, ["high", "low"]] = [101.75, 101.05]  # inside range=0.70

    # mother_range<=0 for GG candidate at ib_idx=7 -> blocked
    bars.loc[6, ["high", "low"]] = [102.5, 102.5]
    bars.loc[7, "close"] = 102.9  # make inside candle green to avoid color filter being the blocker

    def _signals(*_args, **_kwargs):
        return [
            RawSignal(
                timestamp=pd.to_datetime(bars.loc[2, "timestamp"], utc=True),
                side="BUY",
                entry_price=101.0,
                stop_loss=100.5,
                take_profit=102.0,
                metadata={"ib_idx": 1, "sig_idx": 2},
            ),
            RawSignal(
                timestamp=pd.to_datetime(bars.loc[5, "timestamp"], utc=True),
                side="SELL",
                entry_price=101.1,
                stop_loss=101.4,
                take_profit=100.5,
                metadata={"ib_idx": 4, "sig_idx": 5},
            ),
            RawSignal(
                timestamp=pd.to_datetime(bars.loc[8, "timestamp"], utc=True),
                side="BUY",
                entry_price=102.75,
                stop_loss=102.5,
                take_profit=103.2,
                metadata={"ib_idx": 7, "sig_idx": 8},
            ),
        ]

    monkeypatch.setattr("strategies.confirmed_breakout.InsideBarCore.process_data", _signals)

    out = extend_insidebar_signal_frame_from_core(
        bars,
        _params(mother_range_ratio_min=0.72, mother_range_ratio_max=0.912),
    )
    signal_rows = out[out["signal_side"].notna()].copy()

    kept_ts = signal_rows["timestamp"].tolist()
    assert kept_ts == [pd.to_datetime(bars.loc[2, "timestamp"], utc=True)]


def test_range_ratio_tunable_overrides_and_invalid_values_fallback(monkeypatch):
    bars = _bars()
    bars.loc[0, ["high", "low"]] = [101.2, 100.2]  # mother range=1.0
    bars.loc[1, ["high", "low"]] = [100.93, 100.20]  # inside range=0.73

    def _signals(*_args, **_kwargs):
        return [
            RawSignal(
                timestamp=pd.to_datetime(bars.loc[2, "timestamp"], utc=True),
                side="BUY",
                entry_price=101.0,
                stop_loss=100.5,
                take_profit=102.0,
                metadata={"ib_idx": 1, "sig_idx": 2},
            ),
        ]

    monkeypatch.setattr("strategies.confirmed_breakout.InsideBarCore.process_data", _signals)

    # Tight tunables should block ratio 0.73
    out_tight = extend_insidebar_signal_frame_from_core(
        bars,
        _params(mother_range_ratio_min=0.8, mother_range_ratio_max=0.9),
    )
    assert out_tight[out_tight["signal_side"].notna()].empty

    # Invalid tunables should fall back to defaults (0.751..0.912), so 0.73 is blocked.
    out_invalid = extend_insidebar_signal_frame_from_core(
        bars,
        _params(mother_range_ratio_min=-1, mother_range_ratio_max=2),
    )
    assert out_invalid[out_invalid["signal_side"].notna()].empty
