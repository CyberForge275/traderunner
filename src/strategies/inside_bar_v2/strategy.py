from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..inside_bar.strategy import InsideBarStrategy
from ..base import Signal


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
            inside_bar_mode,
            min_mother_size,
            max_master_range_mult,
            min_body_ratio,
        )

        if session_filter.get("enabled", False):
            df = self._apply_session_filter(df, session_filter)

        return self._generate_breakout_signals(
            df,
            symbol,
            rrr,
            breakout_confirm,
            execution_lag,
            stop_distance_cap,
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

    def _detect_inside_bars(
        self,
        df: pd.DataFrame,
        mode: str,
        min_mother_size: float,
        max_master_range_mult: float | None,
        min_body_ratio: float,
    ) -> pd.DataFrame:
        df["is_inside_bar"] = False
        df["mother_bar_high"] = np.nan
        df["mother_bar_low"] = np.nan
        df["mother_bar_index"] = -1
        df["inside_origin_index"] = -1
        df["mother_body_ratio"] = np.nan

        strict_mode = mode == "strict"
        for i in range(1, len(df)):
            prev_high = df.iloc[i - 1]["high"]
            prev_low = df.iloc[i - 1]["low"]
            curr_high = df.iloc[i]["high"]
            curr_low = df.iloc[i]["low"]
            atr_value = df.iloc[i - 1]["atr"]
            mother_range = prev_high - prev_low
            body_ratio = df.iloc[i]["prev_body_ratio"]

            if strict_mode:
                is_inside = (curr_high < prev_high) and (curr_low > prev_low)
            else:
                is_inside = (curr_high <= prev_high) and (curr_low >= prev_low)

            if is_inside and min_mother_size > 0 and not np.isnan(atr_value):
                if mother_range < (min_mother_size * atr_value):
                    is_inside = False

            if is_inside and max_master_range_mult is not None and not np.isnan(atr_value):
                if mother_range > (max_master_range_mult * atr_value):
                    is_inside = False

            if is_inside and min_body_ratio > 0 and not np.isnan(body_ratio):
                if body_ratio < min_body_ratio:
                    is_inside = False

            if is_inside:
                df.iloc[i, df.columns.get_loc("is_inside_bar")] = True
                df.iloc[i, df.columns.get_loc("mother_bar_high")] = prev_high
                df.iloc[i, df.columns.get_loc("mother_bar_low")] = prev_low
                df.iloc[i, df.columns.get_loc("mother_bar_index")] = i - 1
                df.iloc[i, df.columns.get_loc("inside_origin_index")] = i
                if not np.isnan(body_ratio):
                    df.iloc[i, df.columns.get_loc("mother_body_ratio")] = body_ratio

        return df

    def _generate_breakout_signals(
        self,
        df: pd.DataFrame,
        symbol: str,
        rrr: float,
        confirm: bool,
        execution_lag: int,
        stop_distance_cap: float | None,
    ) -> List[Signal]:
        signals: List[Signal] = []

        for i in range(len(df)):
            row = df.iloc[i]
            if "in_session" in df.columns and not row.get("in_session", True):
                continue
            if np.isnan(row.get("atr", np.nan)):
                continue

            mother_high = mother_low = None
            inside_atr = None
            inside_index = None

            for j in range(max(0, i - 5), i + 1):
                candidate = df.iloc[j]
                if candidate["is_inside_bar"] and not np.isnan(candidate["mother_bar_high"]):
                    inside_index = int(candidate["inside_origin_index"])
                    if execution_lag > 0 and (i - inside_index) < execution_lag:
                        continue
                    mother_high = candidate["mother_bar_high"]
                    mother_low = candidate["mother_bar_low"]
                    inside_atr = candidate.get("atr", row["atr"])
                    break

            if mother_high is None or mother_low is None:
                continue

            current_close = row["close"]
            high = row["high"]
            low = row["low"]
            atr = inside_atr if inside_atr is not None and not np.isnan(inside_atr) else row["atr"]

            long_breakout = False
            short_breakout = False

            if confirm:
                if current_close > mother_high:
                    long_breakout = True
                elif current_close < mother_low:
                    short_breakout = True
            else:
                if high > mother_high:
                    long_breakout = True
                elif low < mother_low:
                    short_breakout = True

            if long_breakout:
                entry_price = mother_high
                stop_loss = mother_low
                risk = entry_price - stop_loss
                if risk <= 0:
                    continue
                risk_for_target = min(risk, stop_distance_cap) if stop_distance_cap else risk
                take_profit = entry_price + (risk_for_target * rrr)

                signals.append(
                    self.create_signal(
                        timestamp=row["timestamp"],
                        symbol=symbol,
                        signal_type="LONG",
                        confidence=0.85,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        pattern="inside_bar_breakout",
                        mother_bar_high=mother_high,
                        mother_bar_low=mother_low,
                        atr=atr,
                        risk_amount=risk,
                        reward_amount=risk_for_target * rrr,
                        stop_cap_applied=risk_for_target != risk,
                        execution_lag_bars=execution_lag,
                    )
                )
            elif short_breakout:
                entry_price = mother_low
                stop_loss = mother_high
                risk = stop_loss - entry_price
                if risk <= 0:
                    continue
                risk_for_target = min(risk, stop_distance_cap) if stop_distance_cap else risk
                take_profit = entry_price - (risk_for_target * rrr)

                signals.append(
                    self.create_signal(
                        timestamp=row["timestamp"],
                        symbol=symbol,
                        signal_type="SHORT",
                        confidence=0.85,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        pattern="inside_bar_breakout",
                        mother_bar_high=mother_high,
                        mother_bar_low=mother_low,
                        atr=atr,
                        risk_amount=risk,
                        reward_amount=risk_for_target * rrr,
                        stop_cap_applied=risk_for_target != risk,
                        execution_lag_bars=execution_lag,
                    )
                )

        return signals
