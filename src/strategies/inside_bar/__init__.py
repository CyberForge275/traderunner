"""InsideBar strategy package - Unified implementation."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .core import InsideBarCore, InsideBarConfig
from .models import RawSignal
from .config import (
    build_inside_bar_config,
    load_config,
    get_default_config_path,
    load_default_config,
)

from strategies.registry import register_strategy
from .signal_schema import get_signal_frame_schema
from .intent_generation import generate_intent

logger = logging.getLogger(__name__)

def _core_config_from_params(params: dict) -> InsideBarConfig:
    return build_inside_bar_config(params)


def extend_insidebar_signal_frame_from_core(
    bars,
    params: dict,
):
    """Build SignalFrame from core.process_data (single SSOT)."""
    version = params.get("strategy_version", "1.0.0")
    schema = get_signal_frame_schema(version)
    from axiom_bt.utils.trace import trace_ui
    trace_ui(
        step="insidebar_extend_start",
        run_id=params.get("run_id"),
        strategy_id="insidebar_intraday",
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
    df["strategy_id"] = "insidebar_intraday"
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
    df["breakout_long_close_confirmed"] = False
    df["breakout_short_close_confirmed"] = False
    df["entry_long_effective"] = False
    df["entry_short_effective"] = False
    # Debug-only columns (no behavior impact)
    df["mother_ts"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    df["inside_ts"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    df["trigger_ts"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    df["breakout_level"] = np.nan
    df["order_expired"] = False
    df["order_expire_reason"] = pd.NA
    df["setup_armed_ts"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    df["confirm_ts"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    df["entry_valid_from_ts"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    df["window_idx"] = np.nan
    df["setup_expire_reason"] = pd.NA
    df["mother_body_fraction"] = np.nan
    df["inside_body_fraction"] = np.nan
    df["inside_bar_reject_reason"] = pd.NA

    core = InsideBarCore(_core_config_from_params(params))
    # Mirror pattern-level diagnostics into the frame for audit artifacts.
    analysis_df = core.calculate_atr(df.copy())
    analysis_df = core.detect_inside_bars(analysis_df)
    for col in ("mother_body_fraction", "inside_body_fraction", "inside_bar_reject_reason"):
        if col in analysis_df.columns:
            df[col] = analysis_df[col].values

    # Core SSOT: generate signals only via process_data()
    signals = core.process_data(df, params.get("symbol", "UNKNOWN"))
    trace_ui(
        step="insidebar_core_done",
        run_id=params.get("run_id"),
        strategy_id="insidebar_intraday",
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

        base_template_id = f"ib_{df.at[idx, 'symbol']}_{ts.strftime('%Y%m%d_%H%M%S')}"
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
            row["entry_long_effective"] = bool(meta.get("entry_long_effective", True))
            row["entry_short_effective"] = bool(meta.get("entry_short_effective", False))
        else:
            row["breakout_long"] = False
            row["breakout_short"] = True
            row["entry_long_effective"] = bool(meta.get("entry_long_effective", False))
            row["entry_short_effective"] = bool(meta.get("entry_short_effective", True))
        if "breakout_long_close_confirmed" in meta:
            row["breakout_long_close_confirmed"] = bool(meta["breakout_long_close_confirmed"])
        if "breakout_short_close_confirmed" in meta:
            row["breakout_short_close_confirmed"] = bool(meta["breakout_short_close_confirmed"])
        if "setup_armed_ts" in meta and pd.notna(meta["setup_armed_ts"]):
            row["setup_armed_ts"] = pd.to_datetime(meta["setup_armed_ts"], utc=True)
        if "confirm_ts" in meta and pd.notna(meta["confirm_ts"]):
            row["confirm_ts"] = pd.to_datetime(meta["confirm_ts"], utc=True)
        if "entry_valid_from_ts" in meta and pd.notna(meta["entry_valid_from_ts"]):
            row["entry_valid_from_ts"] = pd.to_datetime(meta["entry_valid_from_ts"], utc=True)
        if "window_idx" in meta and meta["window_idx"] is not None:
            row["window_idx"] = float(meta["window_idx"])
        if "setup_expire_reason" in meta and pd.notna(meta["setup_expire_reason"]):
            row["setup_expire_reason"] = str(meta["setup_expire_reason"])

        if "mother_high" in meta:
            row["mother_high"] = meta["mother_high"]
        if "mother_low" in meta:
            row["mother_low"] = meta["mother_low"]
        if "atr" in meta:
            row["atr"] = meta["atr"]
        if "mother_body_fraction" in meta:
            row["mother_body_fraction"] = meta["mother_body_fraction"]
        if "inside_body_fraction" in meta:
            row["inside_body_fraction"] = meta["inside_body_fraction"]

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
    strategy_id = "insidebar_intraday"

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

__version__ = "2.0.0"

__all__ = [
    "InsideBarCore",
    "InsideBarConfig",
    "RawSignal",
    "load_config",
    "get_default_config_path",
    "load_default_config",
]
