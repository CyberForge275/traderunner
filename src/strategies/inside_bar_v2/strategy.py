from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..base import Signal
from ..inside_bar.strategy import InsideBarStrategy


class InsideBarStrategyV2(InsideBarStrategy):
    """Inside Bar strategy with enhanced filtering and risk controls."""

    @property
    def name(self) -> str:  # pragma: no cover - simple property
        return "inside_bar_v2"

    @property
    def description(self) -> str:  # pragma: no cover - simple property
        return (
            "Inside Bar breakout strategy with ATR guards, body filters, execution lag, "
            "and stop-distance capping."
        )

    @property
    def config_schema(self) -> Dict[str, Any]:  # pragma: no cover - schema composition
        base_schema = super().config_schema
        properties = dict(base_schema["properties"])
        properties.update(
            {
                "max_master_range_atr_mult": {
                    "type": ["number", "null"],
                    "minimum": 0.0,
                    "default": None,
                    "description": "Reject IB if master range exceeds this ATR multiple.",
                },
                "min_master_body_ratio": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.5,
                    "description": "Minimum real body ratio for master candle.",
                },
                "execution_lag_bars": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 0,
                    "description": "Bars to wait before arming breakout orders.",
                },
                "stop_distance_cap": {
                    "type": ["number", "null"],
                    "minimum": 0.0,
                    "default": None,
                    "description": "Cap for stop distance; target recomputed using cap.",
                },
            }
        )
        base_schema["properties"] = properties
        return base_schema

    def generate_signals(
        self, data: pd.DataFrame, symbol: str, config: Dict[str, Any]
    ) -> List[Signal]:
        self.validate_data(data)
        df = self.preprocess_data(data.copy())

        if len(df) < 2:
            return []

        atr_period = config.get("atr_period", 14)
        rrr = float(config.get("risk_reward_ratio", 1.0))
        inside_bar_mode = config.get("inside_bar_mode", "inclusive")
        if inside_bar_mode == "single":
            inside_bar_mode = "inclusive"
        min_mother_size = float(config.get("min_mother_bar_size", 0.0))
        breakout_confirm = config.get("breakout_confirmation", True)
        session_filter = config.get("session_filter", {"enabled": False})

        max_master_range_mult = config.get("max_master_range_atr_mult")
        if max_master_range_mult is not None:
            try:
                max_master_range_mult = float(max_master_range_mult)
            except (TypeError, ValueError):
                max_master_range_mult = None
        min_body_ratio = float(config.get("min_master_body_ratio", 0.0))
        if min_body_ratio < 0:
            min_body_ratio = 0.0
        execution_lag = int(config.get("execution_lag_bars", 0))
        if execution_lag < 0:
            execution_lag = 0
        stop_distance_cap = config.get("stop_distance_cap")
        if stop_distance_cap is not None:
            try:
                stop_distance_cap = float(stop_distance_cap)
            except (TypeError, ValueError):
                stop_distance_cap = None
        if stop_distance_cap is not None and stop_distance_cap <= 0:
            stop_distance_cap = None

        df = self._calculate_indicators(df, atr_period)
        df = self._detect_inside_bars(
            df,
            mode=inside_bar_mode,
            min_mother_size=min_mother_size,
            max_master_range_mult=max_master_range_mult,
            min_body_ratio=min_body_ratio,
        )

        if session_filter.get("enabled", False):
            df = self._apply_session_filter(df, session_filter)

        return self._generate_breakout_signals(
            df,
            symbol=symbol,
            rrr=rrr,
            confirm=breakout_confirm,
            execution_lag=execution_lag,
            stop_distance_cap=stop_distance_cap,
            confidence=0.85,
        )

    # --- helpers -----------------------------------------------------------------

    def _calculate_indicators(self, df: pd.DataFrame, atr_period: int) -> pd.DataFrame:
        df["prev_close"] = df["close"].shift(1)
        df["prev_open"] = df["open"].shift(1)
        df["prev_high"] = df["high"].shift(1)
        df["prev_low"] = df["low"].shift(1)

        df["tr1"] = df["high"] - df["low"]
        df["tr2"] = (df["high"] - df["prev_close"]).abs()
        df["tr3"] = (df["low"] - df["prev_close"]).abs()
        df["true_range"] = df[["tr1", "tr2", "tr3"]].max(axis=1)

        if atr_period <= 1:
            atr_period = 1
        alpha = 1.0 / atr_period
        df["atr"] = df["true_range"].ewm(alpha=alpha, adjust=False).mean()
        df["prev_range"] = df["prev_high"] - df["prev_low"]

        with np.errstate(divide="ignore", invalid="ignore"):
            df["prev_body_ratio"] = (
                (df["prev_close"] - df["prev_open"]).abs()
                / df["prev_range"].replace(0, np.nan)
            )

        return df
