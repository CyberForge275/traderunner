"""Harami Break strategy plugin registration for pipeline discovery."""

from __future__ import annotations

import pandas as pd

from strategies.registry import register_strategy

from .intent_generation import generate_intent
from .pattern_detection import enrich_inside_pattern_frame
from .signal_schema import get_signal_frame_schema
from .session_logic import apply_signal_validity
from .strategy import build_strategy


def extend_harami_signal_frame(bars: pd.DataFrame, params: dict) -> pd.DataFrame:
    required = [
        "inside_bar_definition_mode",
        "strict_mode",
        "session_windows",
        "session_timezone",
        "timeframe_minutes",
        "order_validity_policy",
        "order_validity_minutes",
        "order_validity_bars",
    ]
    missing = [k for k in required if k not in params]
    if missing:
        raise ValueError(
            f"harami_break missing required params for signal frame: {', '.join(sorted(missing))}"
        )

    version = str(params.get("strategy_version", "1.0.0"))
    symbol = str(params.get("symbol", "UNKNOWN"))
    timeframe = str(params.get("timeframe", ""))
    df = bars.copy().sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["symbol"] = symbol
    df["timeframe"] = timeframe
    df["strategy_id"] = "harami_break_intraday"
    df["strategy_version"] = version
    df["strategy_tag"] = "hb"

    out = enrich_inside_pattern_frame(
        df,
        definition_mode=str(params["inside_bar_definition_mode"]),
        strict=bool(params["strict_mode"]),
        session_windows=list(params["session_windows"]),
        session_timezone=str(params["session_timezone"]),
    )
    out = apply_signal_validity(
        out,
        timeframe_minutes=int(params["timeframe_minutes"]),
        session_windows=list(params["session_windows"]),
        session_timezone=str(params["session_timezone"]),
        order_validity_policy=str(params["order_validity_policy"]),
        order_validity_minutes=int(params["order_validity_minutes"]),
        order_validity_bars=int(params["order_validity_bars"]),
    )
    out["long_trigger_price"] = out["mother_bar_high"].where(out["is_inside_bar"])
    out["short_trigger_price"] = out["mother_bar_low"].where(out["is_inside_bar"])
    return out


class HaramiBreakPlugin:
    strategy_id = "harami_break_intraday"

    @staticmethod
    def get_schema(version: str):
        return get_signal_frame_schema(version)

    @staticmethod
    def extend_signal_frame(bars, params: dict):
        return extend_harami_signal_frame(bars, params)

    @staticmethod
    def generate_intent(signals_frame, strategy_id: str, strategy_version: str, params: dict):
        return generate_intent(signals_frame, strategy_id, strategy_version, params)


register_strategy(HaramiBreakPlugin())

__all__ = ["build_strategy"]
