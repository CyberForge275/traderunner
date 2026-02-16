"""Confirmed Breakout strategy package - unified implementation."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .core import InsideBarCore, InsideBarConfig
from .models import RawSignal
from .config import load_config, get_default_config_path, load_default_config

from strategies.registry import register_strategy
from .signal_schema import get_signal_frame_schema
from .intent_generation import generate_intent

logger = logging.getLogger(__name__)

STRATEGY_ID = "confirmed_breakout_intraday"
STRATEGY_TAG = "cb"


def _core_config_from_params(params: dict) -> InsideBarConfig:
    # Keep mapping consistent with InsideBarStrategy.generate_signals()
    if "inside_bar_definition_mode" not in params:
        raise ValueError(
            "inside_bar_definition_mode is required in params (no code default)"
        )
    core_params = {
        # Core
        "inside_bar_definition_mode": params["inside_bar_definition_mode"],
        "atr_period": params.get("atr_period", 14),
        "risk_reward_ratio": params.get("risk_reward_ratio", 2.0),
        "min_mother_bar_size": params.get("min_mother_bar_size", 0.5),
        "breakout_confirmation": params.get("breakout_confirmation", True),
        "inside_bar_mode": params.get("inside_bar_mode", "inclusive"),
        # Session & TZ
        "session_timezone": params.get("session_timezone", "Europe/Berlin"),
        "session_windows": params.get("session_filter")
            or params.get("session_windows", ["15:00-16:00", "16:00-17:00"]),
        "max_trades_per_session": params.get("max_trades_per_session", 1),
        # Order validity
        "order_validity_policy": params.get("order_validity_policy", "session_end"),
        "order_validity_minutes": params.get("validity_minutes")
            or params.get("order_validity_minutes", 60),
        "valid_from_policy": params.get("valid_from_policy", "signal_ts"),
        # Entry/SL sizing
        "entry_level_mode": params.get("entry_level_mode", "mother_bar"),
        "stop_distance_cap_ticks": params.get("stop_distance_cap_ticks", 40),
        "tick_size": params.get("tick_size", 0.01),
        # MVP: Trigger and Netting
        "trigger_must_be_within_session": params.get("trigger_must_be_within_session", True),
        "netting_mode": params.get("netting_mode", "one_position_per_symbol"),
        # Trailing
        "trailing_enabled": params.get("trailing_enabled", False),
        "trailing_trigger_tp_pct": params.get("trailing_trigger_tp_pct", 0.70),
        "trailing_risk_remaining_pct": params.get("trailing_risk_remaining_pct", 0.50),
        "trailing_apply_mode": params.get("trailing_apply_mode", "next_bar"),
        "max_position_pct": params.get("max_position_pct", 100.0),
    }
    return InsideBarConfig(**core_params)


def extend_insidebar_signal_frame_from_core(
    bars,
    params: dict,
):
    """Build SignalFrame from core.process_data (single SSOT)."""
    version = params.get("strategy_version", "1.0.0")
    schema = get_signal_frame_schema(version)
    from axiom_bt.utils.trace import trace_ui
    trace_ui(
        step="confirmed_breakout_extend_start",
        run_id=params.get("run_id"),
        strategy_id=STRATEGY_ID,
        strategy_version=version,
        file=__file__,
        func="extend_insidebar_signal_frame_from_core",
    )

    df = bars.copy()
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # Pre-materialize schema columns
    for col in schema.all_columns():
        if col.name not in df.columns:
            if col.dtype == "bool":
                df[col.name] = False
            elif col.dtype.startswith("datetime64"):
                df[col.name] = pd.NaT
            elif col.dtype.startswith(("float", "int")):
                df[col.name] = np.nan
            else:
                df[col.name] = pd.NA

    # Metadata columns
    df["symbol"] = params.get("symbol", "UNKNOWN")
    df["timeframe"] = params.get("timeframe", "")
    df["strategy_id"] = STRATEGY_ID
    df["strategy_version"] = version
    df["strategy_tag"] = schema.strategy_tag
    df["template_id"] = pd.NA

    # Default indicator values (required by schema)
    df["atr"] = 0.0
    df["inside_bar"] = False
    df["mother_high"] = np.nan
    df["mother_low"] = np.nan
    df["breakout_long"] = False
    df["breakout_short"] = False
    # Debug-only columns (no behavior impact)
    df["mother_ts"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    df["inside_ts"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    df["trigger_ts"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    df["breakout_level"] = np.nan
    df["order_expired"] = False
    df["order_expire_reason"] = pd.NA

    # Core SSOT: generate signals only via process_data()
    core = InsideBarCore(_core_config_from_params(params))
    signals = core.process_data(df, params.get("symbol", "UNKNOWN"))
    trace_ui(
        step="confirmed_breakout_core_done",
        run_id=params.get("run_id"),
        strategy_id=STRATEGY_ID,
        strategy_version=version,
        file=__file__,
        func="extend_insidebar_signal_frame_from_core",
        extra={"signals": len(signals)},
    )

    # Map signals into frame (allow multiple legs per bar via row append)
    appended_rows = []
    for sig in signals:
        ts = pd.to_datetime(sig.timestamp, utc=True)
        meta = sig.metadata or {}
        sig_idx = meta.get("sig_idx") or meta.get("signal_idx") or meta.get("bar_index")
        if isinstance(sig_idx, (int, float)) and 0 <= int(sig_idx) < len(df):
            idx = int(sig_idx)
        else:
            match_idx = df.index[df["timestamp"] == ts]
            if match_idx.empty:
                logger.warning(
                    "InsideBarCore signal timestamp not found in frame (symbol=%s, ts=%s)",
                    df.at[0, "symbol"] if len(df) else "UNKNOWN",
                    ts,
                )
                continue
            idx = int(match_idx[0])

        base_template_id = f"{STRATEGY_TAG}_{df.at[idx, 'symbol']}_{ts.strftime('%Y%m%d_%H%M%S')}"
        oco_group_id = f"{df.at[idx, 'symbol']}_{ts.isoformat()}_{df.at[idx, 'strategy_id']}_{df.at[idx, 'strategy_version']}_{base_template_id}"
        leg_suffix = "BUY" if sig.side == "BUY" else "SELL"

        row = df.loc[idx].copy()
        row["signal_side"] = sig.side
        row["signal_reason"] = "inside_bar"
        row["entry_price"] = sig.entry_price
        row["stop_price"] = sig.stop_loss
        row["take_profit_price"] = sig.take_profit
        row["template_id"] = f"{base_template_id}_{leg_suffix}"
        row["oco_group_id"] = oco_group_id
        # Debug-only: trigger timestamp uses the signal bar timestamp
        row["trigger_ts"] = ts
        # Debug-only: breakout_level is entry basis if no explicit level exists
        row["breakout_level"] = sig.entry_price
        row["order_expired"] = False
        row["order_expire_reason"] = pd.NA

        if sig.side == "BUY":
            row["breakout_long"] = True
            row["breakout_short"] = False
        else:
            row["breakout_long"] = False
            row["breakout_short"] = True

        if "mother_high" in meta:
            row["mother_high"] = meta["mother_high"]
        if "mother_low" in meta:
            row["mother_low"] = meta["mother_low"]
        if "atr" in meta:
            row["atr"] = meta["atr"]

        ib_idx = meta.get("ib_idx")
        if isinstance(ib_idx, (int, float)) and 0 <= int(ib_idx) < len(df):
            ib_idx = int(ib_idx)
            # Mark the IB row itself for indicators
            df.at[ib_idx, "inside_bar"] = True
            if "mother_high" in meta:
                df.at[ib_idx, "mother_high"] = meta["mother_high"]
            if "mother_low" in meta:
                df.at[ib_idx, "mother_low"] = meta["mother_low"]
            if "atr" in meta:
                df.at[ib_idx, "atr"] = meta["atr"]
            # Debug-only: inside/mother timestamps from bar indices
            inside_ts = df.at[ib_idx, "timestamp"]
            df.at[ib_idx, "inside_ts"] = inside_ts
            row["inside_ts"] = inside_ts
            if ib_idx > 0:
                mother_ts = df.at[ib_idx - 1, "timestamp"]
                df.at[ib_idx, "mother_ts"] = mother_ts
                row["mother_ts"] = mother_ts

        appended_rows.append(row)

    if appended_rows:
        df = pd.concat([df, pd.DataFrame(appended_rows)], ignore_index=True)

    return df


class InsideBarPlugin:
    strategy_id = STRATEGY_ID

    @staticmethod
    def get_schema(version: str):
        return get_signal_frame_schema(version)

    @staticmethod
    def extend_signal_frame(bars, params: dict):
        return extend_insidebar_signal_frame_from_core(bars, params)

    @staticmethod
    def generate_intent(signals_frame, strategy_id: str, strategy_version: str, params: dict):
        return generate_intent(signals_frame, strategy_id, strategy_version, params)


register_strategy(InsideBarPlugin())

__version__ = "1.0.0"

__all__ = [
    "InsideBarCore",
    "InsideBarConfig",
    "RawSignal",
    "load_config",
    "get_default_config_path",
    "load_default_config",
]
