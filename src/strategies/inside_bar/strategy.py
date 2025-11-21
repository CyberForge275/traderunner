"""Inside Bar Pattern Trading Strategy.

This strategy detects inside bar patterns and generates trading signals based on
breakouts from the pattern. An inside bar is a candlestick that is completely
contained within the previous bar's high and low range.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..base import BaseStrategy, Signal


class InsideBarStrategy(BaseStrategy):
    """Inside Bar pattern recognition strategy.

    This strategy identifies inside bar patterns and generates signals when:
    1. An inside bar is detected (current bar is within previous bar's range)
    2. Price breaks out above/below the mother bar (the bar containing the inside bar)
    3. Risk management using ATR for stop losses and take profits

    Features:
    - Configurable ATR period for volatility-based stops
    - Risk-reward ratio management
    - Session filtering (optional)
    - Multiple inside bar modes (single, sequence)
    """

    @property
    def name(self) -> str:
        """Return strategy name."""
        return "inside_bar_v1"

    @property
    def description(self) -> str:
        """Return strategy description."""
        return (
            "Inside Bar breakout strategy with ATR-based risk management. "
            "Detects inside bar patterns and generates signals on breakouts "
            "with configurable risk-reward ratios."
        )

    @property
    def config_schema(self) -> Dict[str, Any]:
        """Return configuration schema."""
        return {
            "type": "object",
            "properties": {
                "atr_period": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 14,
                    "description": "Period for ATR calculation",
                },
                "risk_reward_ratio": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 10.0,
                    "default": 2.0,
                    "description": "Risk-reward ratio (take_profit / stop_loss)",
                },
                "inside_bar_mode": {
                    "type": "string",
                    "enum": ["inclusive", "strict", "sequence", "single"],
                    "default": "inclusive",
                    "description": "Mode for inside bar detection",
                },
                "min_mother_bar_size": {
                    "type": "number",
                    "minimum": 0.0,
                    "default": 0.0,
                    "description": "Minimum size of mother bar as multiple of ATR",
                },
                "breakout_confirmation": {
                    "type": "boolean",
                    "default": True,
                    "description": (
                        "Require breakout confirmation (close beyond mother bar)"
                    ),
                },
                "session_filter": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean", "default": False},
                        "start_hour": {"type": "integer", "minimum": 0, "maximum": 23},
                        "end_hour": {"type": "integer", "minimum": 0, "maximum": 23},
                    },
                    "description": "Optional session time filtering",
                },
            },
            "required": ["atr_period", "risk_reward_ratio"],
        }

    def generate_signals(
        self, data: pd.DataFrame, symbol: str, config: Dict[str, Any]
    ) -> List[Signal]:
        """Generate Inside Bar signals.

        Args:
            data: OHLCV DataFrame with columns: timestamp, open, high, low,
                close, volume
            symbol: Trading symbol
            config: Strategy configuration

        Returns:
            List of Signal objects
        """
        # Validate input data
        self.validate_data(data)

        # Preprocess data
        df = self.preprocess_data(data.copy())

        if len(df) < 2:
            return []

        # Extract configuration
        atr_period = config.get("atr_period", 14)
        rrr = config.get("risk_reward_ratio", 2.0)
        inside_bar_mode = config.get("inside_bar_mode", "inclusive")
        if inside_bar_mode == "single":
            inside_bar_mode = "inclusive"
        min_mother_size = config.get("min_mother_bar_size", 0.0)
        breakout_confirm = config.get("breakout_confirmation", True)
        session_filter = config.get("session_filter", {"enabled": False})

        # Calculate technical indicators
        df = self._calculate_indicators(df, atr_period)

        df = self._detect_inside_bars(
            df,
            mode=inside_bar_mode,
            min_mother_size=min_mother_size,
            max_master_range_mult=None,
            min_body_ratio=None,
        )

        if session_filter.get("enabled", False):
            df = self._apply_session_filter(df, session_filter)

        return self._generate_breakout_signals(
            df,
            symbol=symbol,
            rrr=rrr,
            confirm=breakout_confirm,
            execution_lag=0,
            stop_distance_cap=None,
            confidence=0.8,
        )

    def _calculate_indicators(self, df: pd.DataFrame, atr_period: int) -> pd.DataFrame:
        """Calculate technical indicators including ATR."""
        # Calculate True Range
        df["prev_close"] = df["close"].shift(1)
        df["prev_open"] = df["open"].shift(1)
        df["tr1"] = df["high"] - df["low"]
        df["tr2"] = abs(df["high"] - df["prev_close"])
        df["tr3"] = abs(df["low"] - df["prev_close"])
        df["true_range"] = df[["tr1", "tr2", "tr3"]].max(axis=1)

        # Calculate ATR (Average True Range)
        df["atr"] = df["true_range"].rolling(window=atr_period).mean()

        # Calculate previous bar's range
        df["prev_high"] = df["high"].shift(1)
        df["prev_low"] = df["low"].shift(1)
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
        min_body_ratio: float | None,
    ) -> pd.DataFrame:
        """Vectorized detection of inside bars with optional filters."""

        strict_mode = mode == "strict"
        sequence_mode = mode == "sequence"

        high = df["high"]
        low = df["low"]
        prev_high = df["prev_high"]
        prev_low = df["prev_low"]
        atr = df["atr"]
        mother_range = df["prev_range"]

        if strict_mode:
            inside_mask = (high < prev_high) & (low > prev_low)
        else:
            inside_mask = (high <= prev_high) & (low >= prev_low)

        inside_mask &= prev_high.notna() & prev_low.notna()

        if min_mother_size > 0:
            size_ok = mother_range >= (min_mother_size * atr)
            inside_mask &= size_ok.fillna(False)

        if max_master_range_mult is not None:
            range_ok = mother_range <= (max_master_range_mult * atr)
            inside_mask &= range_ok.fillna(False)

        if min_body_ratio is not None and min_body_ratio > 0:
            body_ratio = df.get("prev_body_ratio")
            if body_ratio is None:
                prev_open = df["prev_open"]
                prev_close = df["prev_close"]
                with np.errstate(divide="ignore", invalid="ignore"):
                    body_ratio = (prev_close - prev_open).abs() / mother_range.replace(0, np.nan)
            inside_mask &= (body_ratio >= min_body_ratio).fillna(False)

        mother_high = prev_high.where(inside_mask)
        mother_low = prev_low.where(inside_mask)

        if sequence_mode:
            prev_inside = inside_mask.shift(1, fill_value=False)
            mother_high = mother_high.where(~(inside_mask & prev_inside), mother_high.shift(1))
            mother_low = mother_low.where(~(inside_mask & prev_inside), mother_low.shift(1))

        df["is_inside_bar"] = inside_mask
        df["mother_bar_high"] = mother_high
        df["mother_bar_low"] = mother_low

        return df

    def _apply_session_filter(
        self, df: pd.DataFrame, session_config: Dict
    ) -> pd.DataFrame:
        """Apply session time filter."""
        if not session_config.get("enabled", False):
            return df

        start_hour = session_config.get("start_hour", 0)
        end_hour = session_config.get("end_hour", 23)

        # Extract hour from timestamp
        if "timestamp" in df.columns:
            df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour

            # Create session mask
            if start_hour <= end_hour:
                session_mask = (df["hour"] >= start_hour) & (df["hour"] <= end_hour)
            else:  # Overnight session
                session_mask = (df["hour"] >= start_hour) | (df["hour"] <= end_hour)

            df["in_session"] = session_mask
        else:
            df["in_session"] = True

        return df

    def _generate_breakout_signals(
        self,
        df: pd.DataFrame,
        symbol: str,
        rrr: float,
        confirm: bool,
        execution_lag: int,
        stop_distance_cap: float | None,
        confidence: float,
    ) -> List[Signal]:
        """Vectorized breakout detection and signal construction."""

        inside_mask = df["is_inside_bar"].fillna(False)
        if not inside_mask.any():
            return []

        df = df.copy()
        index_values = df.index.to_numpy()

        df["inside_event_origin"] = np.where(inside_mask, index_values, np.nan)
        df["active_event"] = pd.Series(df["inside_event_origin"]).ffill()

        active_mask = df["active_event"].notna()
        if not active_mask.any():
            return []

        df["mother_high_active"] = (
            pd.Series(np.where(inside_mask, df["mother_bar_high"], np.nan)).ffill()
        )
        df["mother_low_active"] = (
            pd.Series(np.where(inside_mask, df["mother_bar_low"], np.nan)).ffill()
        )

        atr_event = pd.Series(np.where(inside_mask, df["atr"], np.nan)).ffill()
        df["atr_event"] = atr_event.fillna(df["atr"])

        df["bars_since_inside"] = np.nan
        df.loc[active_mask, "bars_since_inside"] = (
            df.loc[active_mask]
            .groupby("active_event", observed=False)
            .cumcount()
        )

        if "in_session" in df.columns:
            session_series = df["in_session"].reindex(df.index, fill_value=True)
        else:
            session_series = pd.Series(True, index=df.index)
        session_series = session_series.fillna(True).astype(bool)

        lag_ok = df["bars_since_inside"].fillna(np.inf) >= execution_lag

        long_compare = df["close"] if confirm else df["high"]
        short_compare = df["close"] if confirm else df["low"]

        mother_high_active = df["mother_high_active"]
        mother_low_active = df["mother_low_active"]

        valid_active = (
            active_mask
            & mother_high_active.notna()
            & mother_low_active.notna()
            & session_series
            & lag_ok
        )

        long_condition = valid_active & (long_compare > mother_high_active)
        short_condition = valid_active & (short_compare < mother_low_active)

        if not (long_condition.any() or short_condition.any()):
            return []

        candidates = []
        if long_condition.any():
            long_df = df.loc[long_condition, [
                "timestamp",
                "active_event",
                "mother_high_active",
                "mother_low_active",
                "atr_event",
                "bars_since_inside",
            ]].copy()
            long_df["direction"] = "LONG"
            long_df["entry_price"] = long_df["mother_high_active"]
            long_df["stop_loss"] = long_df["mother_low_active"]
            long_df["risk"] = long_df["entry_price"] - long_df["stop_loss"]
            long_df["row_index"] = long_df.index
            candidates.append(long_df)

        if short_condition.any():
            short_df = df.loc[short_condition, [
                "timestamp",
                "active_event",
                "mother_high_active",
                "mother_low_active",
                "atr_event",
                "bars_since_inside",
            ]].copy()
            short_df["direction"] = "SHORT"
            short_df["entry_price"] = short_df["mother_low_active"]
            short_df["stop_loss"] = short_df["mother_high_active"]
            short_df["risk"] = short_df["stop_loss"] - short_df["entry_price"]
            short_df["row_index"] = short_df.index
            candidates.append(short_df)

        if not candidates:
            return []

        trigger_df = pd.concat(candidates, axis=0)
        trigger_df = trigger_df[trigger_df["risk"] > 0]
        if trigger_df.empty:
            return []

        trigger_df["direction_priority"] = np.where(trigger_df["direction"] == "LONG", 0, 1)
        trigger_df = trigger_df.sort_values(
            ["timestamp", "direction_priority"], kind="stable"
        )
        trigger_df = trigger_df.drop_duplicates(subset="active_event", keep="first")

        signals: List[Signal] = []
        for row in trigger_df.itertuples():
            atr_value = float(getattr(row, "atr_event", np.nan))
            entry_price = float(row.entry_price)
            stop_loss = float(row.stop_loss)
            risk = float(row.risk)
            if risk <= 0:
                continue

            risk_for_target = risk
            stop_cap_applied = False
            if stop_distance_cap is not None and stop_distance_cap > 0:
                if risk_for_target > stop_distance_cap:
                    risk_for_target = stop_distance_cap
                    stop_cap_applied = True

            if row.direction == "LONG":
                take_profit = entry_price + (risk_for_target * rrr)
            else:
                take_profit = entry_price - (risk_for_target * rrr)

            bars_value = getattr(row, "bars_since_inside", np.nan)
            bars_int = int(bars_value) if not pd.isna(bars_value) else None

            metadata = {
                "pattern": "inside_bar_breakout",
                "mother_bar_high": float(row.mother_high_active),
                "mother_bar_low": float(row.mother_low_active),
                "atr": atr_value,
                "risk_amount": risk,
                "reward_amount": risk_for_target * rrr,
                "bars_since_inside": bars_int,
                "execution_lag_bars": execution_lag,
            }
            if stop_distance_cap is not None:
                metadata["stop_cap_applied"] = stop_cap_applied

            signal = self.create_signal(
                timestamp=df.loc[row.row_index, "timestamp"],
                symbol=symbol,
                signal_type=row.direction,
                confidence=confidence,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                **metadata,
            )
            signals.append(signal)

        return signals

    def get_required_data_columns(self) -> List[str]:
        """Return required data columns."""
        return ["timestamp", "open", "high", "low", "close", "volume"]

    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Preprocess data for inside bar detection."""
        df = super().preprocess_data(data)

        # Ensure data is sorted by timestamp
        if "timestamp" in df.columns:
            df = df.sort_values("timestamp").reset_index(drop=True)

        # Remove any duplicate timestamps
        if "timestamp" in df.columns:
            df = df.drop_duplicates(subset=["timestamp"], keep="last")

        return df
