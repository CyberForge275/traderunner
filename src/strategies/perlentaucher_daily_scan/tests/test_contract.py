from __future__ import annotations

import pandas as pd

import strategies.config.managers  # noqa: F401 - trigger manager registration
from strategies.config.registry import config_manager_registry
from strategies.registry import get_strategy
from strategies.perlentaucher_daily_scan.daily_pipeline import normalize_daily_ohlcv_frame
from strategies.perlentaucher_daily_scan.reference_set import build_reference_set
from strategies.perlentaucher_daily_scan.slope_features import build_slope_feature_history_frame
from strategies.perlentaucher_daily_scan.sweet_spot_cache import save_sweet_spot_cache


def test_strategy_registry_lookup_works() -> None:
    plugin = get_strategy("perlentaucher_daily_scan")
    assert plugin.strategy_id == "perlentaucher_daily_scan"


def test_config_manager_registry_lookup_works() -> None:
    manager = config_manager_registry.get_manager("perlentaucher_daily_scan")
    assert manager is not None


def test_extend_signal_frame_returns_schema_compatible_placeholder() -> None:
    plugin = get_strategy("perlentaucher_daily_scan")
    bars = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-04-21T00:00:00Z"], utc=True),
            "symbol": ["AAPL"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.5],
            "close": [10.5],
            "volume": [100000.0],
        }
    )
    params = {
        "enabled": True,
        "timeframe_minutes": 1440,
        "match_mode": "price_vol",
        "use_volume_prefilter": True,
        "reference_set": "default",
        "min_history_days": 107,
        "max_candidates": 25,
        "sweet_spot_config": {
            "reference_set": "default",
            "sweet_spot_pairs": [["MISSING", "2020-01-01"]],
        },
    }

    out = plugin.extend_signal_frame(bars, params)
    assert len(out) == 1
    assert out.loc[0, "strategy_id"] == "perlentaucher_daily_scan"
    assert out.loc[0, "eligibility_reason"] == "REFERENCE_SET_UNAVAILABLE"


def test_extend_signal_frame_matches_when_reference_features_are_injected() -> None:
    plugin = get_strategy("perlentaucher_daily_scan")
    bars = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-04-21T00:00:00Z", "2026-04-21T00:00:00Z"],
                utc=True,
            ),
            "symbol": ["AAPL", "MSFT"],
            "open": [10.0, 10.0],
            "high": [11.0, 11.0],
            "low": [9.5, 9.5],
            "close": [10.5, 10.5],
            "volume": [100000.0, 100000.0],
            "price_short": [1.05, 8.0],
            "price_mid": [0.22, 8.0],
            "price_l_long": [2.05, 8.0],
            "vol_short": [1.55, 8.0],
            "vol_mid": [0.52, 8.0],
            "vol_l_long": [2.55, 8.0],
        }
    )
    params = {
        "enabled": True,
        "timeframe_minutes": 1440,
        "match_mode": "price_vol",
        "use_volume_prefilter": True,
        "reference_set": "default",
        "min_history_days": 107,
        "max_candidates": 25,
        "reference_features": [
            {
                "symbol": "IONQ",
                "price_short": 1.0,
                "price_mid": 0.2,
                "price_l_long": 2.0,
                "vol_short": 1.5,
                "vol_mid": 0.5,
                "vol_l_long": 2.5,
            },
            {
                "symbol": "QS",
                "price_short": 1.1,
                "price_mid": 0.22,
                "price_l_long": 2.1,
                "vol_short": 1.6,
                "vol_mid": 0.55,
                "vol_l_long": 2.6,
            },
            {
                "symbol": "AMPX",
                "price_short": 1.2,
                "price_mid": 0.24,
                "price_l_long": 2.2,
                "vol_short": 1.7,
                "vol_mid": 0.6,
                "vol_l_long": 2.7,
            },
        ],
    }

    out = plugin.extend_signal_frame(bars, params)
    aapl = out.loc[out["symbol"] == "AAPL"].iloc[0]
    msft = out.loc[out["symbol"] == "MSFT"].iloc[0]

    assert aapl["eligibility_reason"] == "MATCHED"
    assert aapl["candidate_rank"] == 1.0
    assert aapl["validity_class"] == "CANDIDATE"
    assert msft["eligibility_reason"] == "NO_MATCH"
    assert pd.isna(msft["candidate_rank"])


def test_generate_intent_returns_empty_contract_artifacts() -> None:
    plugin = get_strategy("perlentaucher_daily_scan")
    signals = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-04-21T00:00:00Z"], utc=True),
            "symbol": ["AAPL"],
        }
    )
    out = plugin.generate_intent(
        signals,
        "perlentaucher_daily_scan",
        "1.0.0",
        params={},
    )
    assert hasattr(out, "events_intent")
    assert hasattr(out, "signals_frame")
    assert hasattr(out, "intent_hash")
    assert out.events_intent.empty


def _build_daily_symbol_frame(
    symbol: str,
    dates: pd.DatetimeIndex,
    *,
    base_close: float,
    last_closes: list[float],
    base_volume: float,
    last_volumes: list[float],
) -> pd.DataFrame:
    closes = [base_close] * (len(dates) - len(last_closes)) + list(last_closes)
    volumes = [base_volume] * (len(dates) - len(last_volumes)) + list(last_volumes)
    lows = [c - 0.5 for c in closes]
    opens = [c - 0.1 for c in closes]
    highs = [c + 0.2 for c in closes]
    return pd.DataFrame(
        {
            "symbol": symbol,
            "timestamp": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def test_extend_signal_frame_uses_sweet_spot_config_with_daily_history() -> None:
    plugin = get_strategy("perlentaucher_daily_scan")
    dates = pd.date_range("2025-10-01", periods=140, freq="B", tz="UTC")
    shared_last_closes = [6.0, 6.2, 6.5, 7.0, 7.5, 8.5, 9.5]
    shared_last_volumes = [650_000.0, 670_000.0, 690_000.0, 710_000.0, 730_000.0, 750_000.0, 770_000.0]

    bars = pd.concat(
        [
            _build_daily_symbol_frame(
                "AAPL",
                dates,
                base_close=5.0,
                last_closes=shared_last_closes,
                base_volume=200_000.0,
                last_volumes=shared_last_volumes,
            ),
            _build_daily_symbol_frame(
                "MSFT",
                dates,
                base_close=5.0,
                last_closes=[5.0, 5.1, 5.3, 5.6, 6.0, 6.5, 7.1],
                base_volume=200_000.0,
                last_volumes=[650_000.0, 660_000.0, 670_000.0, 680_000.0, 690_000.0, 700_000.0, 710_000.0],
            ),
            _build_daily_symbol_frame(
                "IONQ",
                dates,
                base_close=20.0,
                last_closes=[c + 15.0 for c in shared_last_closes],
                base_volume=200_000.0,
                last_volumes=shared_last_volumes,
            ),
        ],
        ignore_index=True,
    )
    params = {
        "enabled": True,
        "timeframe_minutes": 1440,
        "match_mode": "price_vol",
        "use_volume_prefilter": True,
        "reference_set": "default",
        "min_history_days": 107,
        "max_candidates": 25,
        "sweet_spot_config": {
            "reference_set": "default",
            "sweet_spot_pairs": [
                ["IONQ", str(dates[-3].date())],
                ["IONQ", str(dates[-2].date())],
                ["IONQ", str(dates[-1].date())],
            ],
        },
    }

    out = plugin.extend_signal_frame(bars, params)

    assert list(out["symbol"]) == ["AAPL", "MSFT"]
    aapl = out.loc[out["symbol"] == "AAPL"].iloc[0]
    msft = out.loc[out["symbol"] == "MSFT"].iloc[0]
    assert aapl["eligibility_reason"] == "MATCHED"
    assert aapl["candidate_rank"] == 1.0
    assert aapl["signal_side"] == "BUY"
    assert aapl["signal_reason"] == "SWEET_SPOT_MATCH"
    assert aapl["entry_price"] == aapl["close"]
    assert aapl["stop_price"] == aapl["close"] * 0.70
    assert pd.isna(aapl["take_profit_price"])
    assert aapl["template_id"].startswith("pts_AAPL_")
    assert aapl["oco_group_id"].startswith("AAPL_")
    assert aapl["validity_class"] == "CANDIDATE"
    assert msft["eligibility_reason"] == "NO_MATCH"
    assert pd.isna(msft["signal_side"])


def test_extend_signal_frame_uses_injected_sweet_spot_cache_payload() -> None:
    plugin = get_strategy("perlentaucher_daily_scan")
    dates = pd.date_range("2025-10-01", periods=140, freq="B", tz="UTC")
    bars = pd.concat(
        [
            _build_daily_symbol_frame(
                "AAPL",
                dates,
                base_close=5.0,
                last_closes=[6.0, 6.2, 6.5, 7.0, 7.5, 8.5, 9.5],
                base_volume=200_000.0,
                last_volumes=[650_000.0, 670_000.0, 690_000.0, 710_000.0, 730_000.0, 750_000.0, 770_000.0],
            ),
            _build_daily_symbol_frame(
                "MSFT",
                dates,
                base_close=5.0,
                last_closes=[5.0, 5.1, 5.3, 5.6, 6.0, 6.5, 7.1],
                base_volume=200_000.0,
                last_volumes=[650_000.0, 660_000.0, 670_000.0, 680_000.0, 690_000.0, 700_000.0, 710_000.0],
            ),
        ],
        ignore_index=True,
    )
    normalized = normalize_daily_ohlcv_frame(
        bars.rename(columns={"timestamp": "date"})
    )
    feature_history = build_slope_feature_history_frame(
        normalized,
        as_of_date=str(dates[-1].date()),
    )
    aapl_feature = feature_history.loc[feature_history["symbol"] == "AAPL"].sort_values("as_of_date").iloc[-1]
    reference_frame = pd.DataFrame(
        [
            {
                "symbol": "IONQ",
                "price_short": float(aapl_feature["price_short"]),
                "price_mid": float(aapl_feature["price_mid"]),
                "price_l_long": float(aapl_feature["price_l_long"]),
                "vol_short": float(aapl_feature["vol_short"]),
                "vol_mid": float(aapl_feature["vol_mid"]),
                "vol_l_long": float(aapl_feature["vol_l_long"]),
            }
        ]
    )
    artifacts = build_reference_set(reference_frame)
    params = {
        "enabled": True,
        "timeframe_minutes": 1440,
        "match_mode": "price_vol",
        "use_volume_prefilter": True,
        "reference_set": "default",
        "min_history_days": 107,
        "max_candidates": 25,
        "sweet_spot_config": {
            "reference_set": "default",
            "sweet_spot_pairs": [["IONQ", "2026-04-17"]],
        },
        "sweet_spot_cache_payload": {
            "config": {"reference_set": "default", "sweet_spot_pairs": [["IONQ", "2026-04-17"]]},
            "reference_frame": artifacts.reference_frame.to_dict(orient="records"),
            "native_ranges": artifacts.native_ranges,
            "zscore_ranges": artifacts.zscore_ranges,
        },
    }

    out = plugin.extend_signal_frame(bars, params)
    aapl = out.loc[out["symbol"] == "AAPL"].iloc[0]
    assert aapl["eligibility_reason"] == "MATCHED"
    assert aapl["signal_side"] == "BUY"
    assert aapl["entry_price"] == aapl["close"]
    assert aapl["stop_price"] == aapl["close"] * 0.70
    assert pd.isna(aapl["take_profit_price"])


def test_generate_intent_emits_next_day_buy_intent_for_matched_rows() -> None:
    plugin = get_strategy("perlentaucher_daily_scan")
    signals = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-05-06T00:00:00Z", "2026-05-06T00:00:00Z"], utc=True),
            "symbol": ["AAPL", "MSFT"],
            "signal_ts": pd.to_datetime(["2026-05-06T00:00:00Z", "2026-05-06T00:00:00Z"], utc=True),
            "signal_side": ["BUY", pd.NA],
            "signal_reason": ["SWEET_SPOT_MATCH", pd.NA],
            "entry_price": [10.0, pd.NA],
            "stop_price": [7.0, pd.NA],
            "take_profit_price": [float("nan"), pd.NA],
            "template_id": ["pts_AAPL_20260506_000000_BUY", pd.NA],
            "oco_group_id": ["AAPL_2026-05-06T00:00:00+00:00_perlentaucher_daily_scan_1.0.0", pd.NA],
            "eligibility_reason": ["MATCHED", "NO_MATCH"],
        }
    )

    out = plugin.generate_intent(
        signals,
        "perlentaucher_daily_scan",
        "1.0.0",
        params={},
    )

    assert len(out.events_intent) == 1
    row = out.events_intent.iloc[0]
    assert row["symbol"] == "AAPL"
    assert row["side"] == "BUY"
    assert row["entry_price"] == 10.0
    assert row["stop_price"] == 7.0
    assert pd.isna(row["take_profit_price"])
    assert pd.to_datetime(row["order_valid_from_ts"], utc=True) == pd.Timestamp("2026-05-07T00:00:00Z")
    assert pd.to_datetime(row["order_valid_to_ts"], utc=True) == pd.Timestamp("2026-05-07T00:00:00Z")
    assert row["order_valid_to_reason"] == "next_day_only"
