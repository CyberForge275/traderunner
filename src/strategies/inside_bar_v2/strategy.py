from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..base import Signal
from ..inside_bar.strategy import InsideBarStrategy


# Independent versioning for the v2 variant
STRATEGY_VERSION_V2 = "1.0.0"


class InsideBarStrategyV2(InsideBarStrategy):
    """Inside Bar strategy with enhanced filtering and risk controls."""

    @property
    def name(self) -> str:  # pragma: no cover - simple property
        return "inside_bar_v2"

    @property
    def version(self) -> str:  # pragma: no cover - simple property
        return STRATEGY_VERSION_V2

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

    def _detect_inside_bars(
        self,
        df: pd.DataFrame,
        *,
        mode: str,
        min_mother_size: float,
        max_master_range_mult: float | None,
        min_body_ratio: float,
    ) -> pd.DataFrame:
        """Detect inside bars with additional ATR/body filters.

        This mirrors the unified core behaviour but adds:
        - max_master_range_atr_mult: reject patterns where the mother bar
          range is disproportionately large vs ATR
        - min_master_body_ratio: require a minimum real-body ratio on the
          mother candle
        """

        df = df.copy()

        prev_high = df["prev_high"]
        prev_low = df["prev_low"]
        prev_range = df["prev_range"]

        if mode == "strict":
            inside = (df["high"] < prev_high) & (df["low"] > prev_low)
        else:  # inclusive by default
            inside = (df["high"] <= prev_high) & (df["low"] >= prev_low)

        inside = inside & prev_high.notna() & prev_low.notna()

        if min_mother_size > 0:
            size_ok = prev_range >= (min_mother_size * df["atr"])
            inside = inside & size_ok.fillna(False)

        if max_master_range_mult is not None:
            cap_ok = prev_range <= (max_master_range_mult * df["atr"])
            inside = inside & cap_ok.fillna(False)

        if min_body_ratio > 0:
            body_ok = df["prev_body_ratio"] >= min_body_ratio
            inside = inside & body_ok.fillna(False)

        df["is_inside_bar"] = inside
        df["mother_bar_high"] = prev_high.where(inside)
        df["mother_bar_low"] = prev_low.where(inside)

        return df

    def _apply_session_filter(self, df: pd.DataFrame, session_filter: Dict[str, Any]) -> pd.DataFrame:
        """Filter to a specific intraday session window (inclusive hours)."""

        start_hour = int(session_filter.get("start_hour", 0))
        end_hour = int(session_filter.get("end_hour", 23))

        ts = pd.to_datetime(df["timestamp"])
        hours = ts.dt.hour
        mask = (hours >= start_hour) & (hours <= end_hour)

        return df.loc[mask].copy()

    def _generate_breakout_signals(
        self,
        df: pd.DataFrame,
        *,
        symbol: str,
        rrr: float,
        confirm: bool,
        execution_lag: int,
        stop_distance_cap: float | None,
        confidence: float,
    ) -> List[Signal]:
        """Generate breakout signals with execution lag and stop capping."""

        signals: List[Signal] = []

        inside_mask = df.get("is_inside_bar", pd.Series(False, index=df.index)).fillna(False)
        if not inside_mask.any():
            return signals

        signaled_patterns: set[int] = set()

        for idx in range(1, len(df)):
            current = df.iloc[idx]

            recent_inside = df.iloc[:idx][inside_mask[:idx]]
            if recent_inside.empty:
                continue

            last_inside = recent_inside.iloc[-1]
            last_inside_idx = recent_inside.index[-1]

            if last_inside_idx in signaled_patterns:
                continue

            bars_since_inside = idx - last_inside_idx
            if bars_since_inside <= execution_lag:
                # Not yet armed
                continue

            mother_high = last_inside["mother_bar_high"]
            mother_low = last_inside["mother_bar_low"]
            if pd.isna(mother_high) or pd.isna(mother_low):
                continue

            if confirm:
                compare_high = current["close"]
                compare_low = current["close"]
            else:
                compare_high = current["high"]
                compare_low = current["low"]

            # LONG breakout
            if compare_high > mother_high:
                entry = float(mother_high)
                sl = float(mother_low)
                risk = entry - sl
                if risk <= 0:
                    continue

                effective_risk = risk
                stop_cap_applied = False
                if stop_distance_cap is not None and risk > stop_distance_cap:
                    effective_risk = stop_distance_cap
                    stop_cap_applied = True

                tp = entry + (effective_risk * rrr)

                meta: Dict[str, Any] = {
                    "pattern": "inside_bar_breakout",
                    "mother_high": float(mother_high),
                    "mother_low": float(mother_low),
                    "atr": float(current.get("atr", 0.0))
                    if pd.notna(current.get("atr", np.nan))
                    else 0.0,
                    "risk": risk,
                    "reward": effective_risk * rrr,
                    "stop_cap_applied": stop_cap_applied,
                    "execution_lag_bars": execution_lag,
                }

                signal = self.create_signal(
                    timestamp=current["timestamp"],
                    symbol=symbol,
                    signal_type="LONG",
                    confidence=confidence,
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    **meta,
                )
                signals.append(signal)
                signaled_patterns.add(last_inside_idx)

            # SHORT breakout
            elif compare_low < mother_low:
                entry = float(mother_low)
                sl = float(mother_high)
                risk = sl - entry
                if risk <= 0:
                    continue

                effective_risk = risk
                stop_cap_applied = False
                if stop_distance_cap is not None and risk > stop_distance_cap:
                    effective_risk = stop_distance_cap
                    stop_cap_applied = True

                tp = entry - (effective_risk * rrr)

                meta = {
                    "pattern": "inside_bar_breakout",
                    "mother_high": float(mother_high),
                    "mother_low": float(mother_low),
                    "atr": float(current.get("atr", 0.0))
                    if pd.notna(current.get("atr", np.nan))
                    else 0.0,
                    "risk": risk,
                    "reward": effective_risk * rrr,
                    "stop_cap_applied": stop_cap_applied,
                    "execution_lag_bars": execution_lag,
                }

                signal = self.create_signal(
                    timestamp=current["timestamp"],
                    symbol=symbol,
                    signal_type="SHORT",
                    confidence=confidence,
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    **meta,
                )
                signals.append(signal)
                signaled_patterns.add(last_inside_idx)

        return signals
