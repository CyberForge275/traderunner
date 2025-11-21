"""Rudometkin Market-On-Close long/short strategy implementation.

This port follows Alexei Rudometkin's RealTest specification and mirrors the
logic of ``rudometkin_moc_long_short.rts``. The system works on daily bars,
trades liquid Russell 1000 names, enters via next-day limit orders, and exits on
the entry day's close (Market-On-Close).

Key features:
    * Dual long/short mean-reversion playbook with shared risk template
    * ADX-based trend strength filter and Connors RSI overbought trigger
    * Liquidity filters (price floor, 50-day average volume) and optional
      universe membership column
    * Vectorised indicator calculations aligned with RealTest definitions
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

import numpy as np
import pandas as pd

from ..base import BaseStrategy, Signal


class RudometkinMOCStrategy(BaseStrategy):
    """Rudometkin MOC Long/Short Strategy."""

    _DEFAULT_UNIVERSE_PATH = "data/universe/rudometkin.parquet"

    @property
    def name(self) -> str:
        """Return strategy name."""
        return "rudometkin_moc"

    @property
    def description(self) -> str:
        """Return strategy description."""
        return (
            "Alexei Rudometkin's Market-On-Close long/short mean reversion system. "
            "Buys deep pullbacks in strong uptrends and fades parabolic spikes "
            "with next-day limit orders, exiting on the entry day's close."
        )

    @property
    def config_schema(self) -> Dict[str, Any]:
        """Return configuration schema."""
        return {
            "type": "object",
            "properties": {
                "entry_stretch1": {
                    "type": "number",
                    "default": 0.035,
                    "description": "Long entry discount (3.5%)",
                },
                "entry_stretch2": {
                    "type": "number",
                    "default": 0.05,
                    "description": "Short entry premium (5.0%)",
                },
                "universe_path": {
                    "type": "string",
                    "default": self._DEFAULT_UNIVERSE_PATH,
                    "description": "Path to parquet universe file listing tradable symbols",
                },
                "min_price": {
                    "type": "number",
                    "default": 10.0,
                    "description": "Minimum closing price to qualify for universe",
                },
                "min_average_volume": {
                    "type": "integer",
                    "default": 1_000_000,
                    "description": "Minimum 50-day average volume for universe",
                },
                "universe_column": {
                    "type": "string",
                    "default": None,
                    "description": (
                        "Optional boolean column indicating Russell 1000 membership"
                    ),
                },
                "adx_period": {
                    "type": "integer",
                    "default": 5,
                    "description": "ADX period",
                },
                "adx_threshold": {
                    "type": "number",
                    "default": 35.0,
                    "description": "Minimum ADX value",
                },
                "sma_period": {
                    "type": "integer",
                    "default": 200,
                    "description": "Trend filter SMA period",
                },
                "crsi_rank_period": {
                    "type": "integer",
                    "default": 100,
                    "description": "Connors RSI percent-rank lookback (lenRocRank)",
                },
                "crsi_price_rsi": {
                    "type": "integer",
                    "default": 2,
                    "description": "Connors RSI price RSI period (lenRsiPrice)",
                },
                "crsi_streak_rsi": {
                    "type": "integer",
                    "default": 2,
                    "description": "Connors RSI streak RSI period (lenRsiStreak)",
                },
                "crsi_threshold": {
                    "type": "number",
                    "default": 70.0,
                    "description": "Minimum Connors RSI value for shorts",
                },
                "long_pullback_threshold": {
                    "type": "number",
                    "default": 0.03,
                    "description": "Minimum intraday drop (fraction of open) for longs",
                },
                "atr40_ratio_bounds": {
                    "type": "object",
                    "properties": {
                        "min": {"type": "number", "default": 0.01},
                        "max": {"type": "number", "default": 0.10},
                    },
                    "default": {"min": 0.01, "max": 0.10},
                    "description": "Valid ATR(40)/close range for shorts",
                },
                "atr2_ratio_bounds": {
                    "type": "object",
                    "properties": {
                        "min": {"type": "number", "default": 0.01},
                        "max": {"type": "number", "default": 0.20},
                    },
                    "default": {"min": 0.01, "max": 0.20},
                    "description": "Valid ATR(2)/close range for shorts",
                },
            },
        }

    def get_required_data_columns(self) -> List[str]:
        """Return required OHLCV columns."""
        return ["timestamp", "open", "high", "low", "close", "volume"]

    def generate_signals(
        self, data: pd.DataFrame, symbol: str, config: Dict[str, Any]
    ) -> List[Signal]:
        """Generate trading signals."""
        self.validate_data(data)
        df = self.preprocess_data(data.copy())
        df = df.sort_values("timestamp").reset_index(drop=True)

        if len(df) < config.get("sma_period", 200):
            return []

        params = self._extract_parameters(config)

        df = self._calculate_indicators(
            df,
            adx_period=params["adx_period"],
            sma_period=params["sma_period"],
            crsi_rank=params["crsi_rank_period"],
            crsi_price=params["crsi_price_rsi"],
            crsi_streak=params["crsi_streak_rsi"],
        )

        allowed_symbols = self._get_universe_symbols(params.get("universe_path"))
        symbol_key = symbol.upper()
        if allowed_symbols is not None and symbol_key not in allowed_symbols:
            return []

        universe_mask = self._build_universe_mask(
            df,
            min_price=params["min_price"],
            min_avg_volume=params["min_average_volume"],
            universe_column=params["universe_column"],
        )

        if not universe_mask.any():
            return []

        long_mask, short_mask = self._evaluate_setups(
            df,
            universe_mask,
            params=params,
        )

        signals: List[Signal] = []

        if long_mask.any():
            signals.extend(
                self._build_signals(
                    df,
                    indices=np.flatnonzero(long_mask.to_numpy()),
                    symbol=symbol,
                    direction="LONG",
                    entry_multiplier=1 - params["entry_stretch1"],
                    score_series=df["atr10"] / df["close"],
                    setup_name="moc_long",
                )
            )

        if short_mask.any():
            signals.extend(
                self._build_signals(
                    df,
                    indices=np.flatnonzero(short_mask.to_numpy()),
                    symbol=symbol,
                    direction="SHORT",
                    entry_multiplier=1 + params["entry_stretch2"],
                    score_series=df["roc5"],
                    setup_name="moc_short",
                )
            )

        return signals

    # ------------------------------------------------------------------
    # Indicator & setup helpers
    # ------------------------------------------------------------------

    def _extract_parameters(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Collect configuration parameters with defaults."""

        def _ratio_bounds(key: str, default: Dict[str, float]) -> Dict[str, float]:
            raw = config.get(key, default)
            if not isinstance(raw, dict):
                return default
            min_val = float(raw.get("min", default["min"]))
            max_val = float(raw.get("max", default["max"]))
            if min_val > max_val:
                min_val, max_val = max_val, min_val
            return {"min": min_val, "max": max_val}

        return {
            "entry_stretch1": float(config.get("entry_stretch1", 0.035)),
            "entry_stretch2": float(config.get("entry_stretch2", 0.05)),
            "universe_path": config.get(
                "universe_path", self._DEFAULT_UNIVERSE_PATH
            ),
            "min_price": float(config.get("min_price", 10.0)),
            "min_average_volume": float(config.get("min_average_volume", 1_000_000)),
            "universe_column": config.get("universe_column"),
            "adx_period": int(config.get("adx_period", 5)),
            "adx_threshold": float(config.get("adx_threshold", 35.0)),
            "sma_period": int(config.get("sma_period", 200)),
            "crsi_rank_period": int(config.get("crsi_rank_period", 100)),
            "crsi_price_rsi": int(config.get("crsi_price_rsi", 2)),
            "crsi_streak_rsi": int(config.get("crsi_streak_rsi", 2)),
            "crsi_threshold": float(config.get("crsi_threshold", 70.0)),
            "long_pullback_threshold": float(
                config.get("long_pullback_threshold", 0.03)
            ),
            "atr40_ratio_bounds": _ratio_bounds(
                "atr40_ratio_bounds", {"min": 0.01, "max": 0.10}
            ),
            "atr2_ratio_bounds": _ratio_bounds(
                "atr2_ratio_bounds", {"min": 0.01, "max": 0.20}
            ),
        }

    def _calculate_indicators(
        self,
        df: pd.DataFrame,
        *,
        adx_period: int,
        sma_period: int,
        crsi_rank: int,
        crsi_price: int,
        crsi_streak: int,
    ) -> pd.DataFrame:
        """Compute indicators required by the strategy."""

        price = df["close"].astype(float)

        df["sma200"] = price.rolling(window=sma_period, min_periods=sma_period).mean()

        df["atr2"] = self._calc_atr(df, period=2)
        df["atr10"] = self._calc_atr(df, period=10)
        df["atr40"] = self._calc_atr(df, period=40)

        df["roc5"] = price.pct_change(5) * 100.0
        df["adx"] = self._calc_adx(df, period=adx_period)
        df["crsi"] = self._calc_connors_rsi(
            df,
            len_roc_rank=crsi_rank,
            len_rsi_price=crsi_price,
            len_rsi_streak=crsi_streak,
        )
        df["avg_vol50"] = df["volume"].rolling(50, min_periods=50).mean()

        return df

    def _build_universe_mask(
        self,
        df: pd.DataFrame,
        *,
        min_price: float,
        min_avg_volume: float,
        universe_column: Optional[str],
    ) -> pd.Series:
        """Construct the universe membership mask."""

        price_ok = df["close"] >= min_price
        volume_ok = df["avg_vol50"].fillna(0) >= min_avg_volume

        if universe_column and universe_column in df.columns:
            membership = df[universe_column].astype(bool)
        else:
            membership = pd.Series(True, index=df.index)

        universe = price_ok & volume_ok & membership
        return universe.fillna(False)

    def _evaluate_setups(
        self,
        df: pd.DataFrame,
        universe_mask: pd.Series,
        *,
        params: Dict[str, Any],
    ) -> tuple[pd.Series, pd.Series]:
        """Evaluate long and short setup conditions."""

        adx = df["adx"].fillna(0)
        close = df["close"].astype(float)

        long_dip = (df["open"] - close) / df["open"].replace(0, np.nan)
        long_mask = (
            universe_mask
            & (close > df["sma200"].fillna(np.nan))
            & (adx > params["adx_threshold"])
            & (long_dip > params["long_pullback_threshold"])
        )

        atr40_ratio = df["atr40"] / close.replace(0, np.nan)
        atr2_ratio = df["atr2"] / close.replace(0, np.nan)
        short_mask = (
            universe_mask
            & (adx > params["adx_threshold"])
            & (df["crsi"] > params["crsi_threshold"])
            & (atr40_ratio >= params["atr40_ratio_bounds"]["min"])
            & (atr40_ratio <= params["atr40_ratio_bounds"]["max"])
            & (atr2_ratio >= params["atr2_ratio_bounds"]["min"])
            & (atr2_ratio <= params["atr2_ratio_bounds"]["max"])
        )

        return long_mask.fillna(False), short_mask.fillna(False)

    def _build_signals(
        self,
        df: pd.DataFrame,
        *,
        indices: Iterable[int],
        symbol: str,
        direction: str,
        entry_multiplier: float,
        score_series: pd.Series,
        setup_name: str,
    ) -> List[Signal]:
        """Construct Signal objects for the selected indices."""

        signals: List[Signal] = []
        close = df.loc[indices, "close"].to_numpy(dtype=float)
        timestamps = df.loc[indices, "timestamp"].to_list()
        atr40 = df.loc[indices, "atr40"].to_numpy(dtype=float)
        atr2 = df.loc[indices, "atr2"].to_numpy(dtype=float)
        scores = score_series.loc[indices].to_numpy(dtype=float)

        for idx, ts, price, atr40_value, atr2_value, score in zip(
            indices, timestamps, close, atr40, atr2, scores
        ):
            if not np.isfinite(price):
                continue

            entry_price = price * entry_multiplier
            meta_payload = {
                "order_type": "LIMIT",
                "time_in_force": "DAY",
                "exit_type": "MOC",
                "setup": setup_name,
                "score": float(score) if np.isfinite(score) else None,
                "atr40": float(atr40_value) if np.isfinite(atr40_value) else None,
                "atr2": float(atr2_value) if np.isfinite(atr2_value) else None,
            }

            signals.append(
                self.create_signal(
                    timestamp=ts,
                    symbol=symbol,
                    signal_type=direction,
                    confidence=1.0,
                    entry_price=float(entry_price),
                    **{k: v for k, v in meta_payload.items() if v is not None},
                )
            )

        return signals

    # ------------------------------------------------------------------
    # Indicator primitives
    # ------------------------------------------------------------------

    def _get_universe_symbols(self, path: Optional[str]) -> Optional[Set[str]]:
        """Load the universe symbol set from parquet, caching per path."""

        if not path:
            return None

        cache_attr = "_universe_cache"
        if not hasattr(self, cache_attr):
            setattr(self, cache_attr, {})
        cache: Dict[str, Optional[Set[str]]] = getattr(self, cache_attr)

        normalized = str(path)
        if normalized in cache:
            return cache[normalized]

        try:
            frame = pd.read_parquet(normalized)
        except (OSError, ValueError, FileNotFoundError):
            cache[normalized] = None
            return None

        symbol_columns = [
            col
            for col in frame.columns
            if frame[col].dtype == object or pd.api.types.is_string_dtype(frame[col])
        ]
        preferred = None
        for candidate in ("symbol", "Symbol", "ticker", "Ticker"):
            if candidate in frame.columns:
                preferred = candidate
                break
        column = preferred or (symbol_columns[0] if symbol_columns else None)
        if column is None:
            cache[normalized] = None
            return None

        values = (
            frame[column]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
        )
        symbols = {sym for sym in values if sym}
        cache[normalized] = symbols if symbols else None
        return cache[normalized]

    def _calc_atr(self, df: pd.DataFrame, *, period: int) -> pd.Series:
        """Return Wilder-style ATR for the given period."""

        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close_prev = df["close"].shift(1).astype(float)

        tr_components = pd.concat(
            [
                (high - low).abs(),
                (high - close_prev).abs(),
                (low - close_prev).abs(),
            ],
            axis=1,
        )
        true_range = tr_components.max(axis=1)
        return true_range.ewm(alpha=1 / period, adjust=False).mean()

    def _calc_adx(self, df: pd.DataFrame, *, period: int) -> pd.Series:
        """Calculate Average Directional Index using Wilder smoothing."""

        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close_prev = df["close"].shift(1).astype(float)

        tr_components = pd.concat(
            [
                (high - low).abs(),
                (high - close_prev).abs(),
                (low - close_prev).abs(),
            ],
            axis=1,
        )
        true_range = tr_components.max(axis=1)

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        alpha = 1 / period
        atr_smooth = true_range.ewm(alpha=alpha, adjust=False).mean()
        plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
            alpha=alpha, adjust=False
        ).mean() / atr_smooth
        minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
            alpha=alpha, adjust=False
        ).mean() / atr_smooth

        di_sum = plus_di + minus_di
        dx = (100 * (plus_di - minus_di).abs() / di_sum).replace([np.inf, -np.inf], np.nan)
        return dx.ewm(alpha=alpha, adjust=False).mean()

    def _calc_connors_rsi(
        self,
        df: pd.DataFrame,
        *,
        len_roc_rank: int,
        len_rsi_price: int,
        len_rsi_streak: int,
    ) -> pd.Series:
        """Connors RSI matching RealTest's CRSI(lenRocRank, lenRsiPrice, lenRsiStreak)."""

        price = df["close"].astype(float)
        delta = price.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        alpha_price = 1 / max(len_rsi_price, 1)
        avg_gain = gain.ewm(alpha=alpha_price, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha_price, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        price_rsi = 100 - (100 / (1 + rs))

        direction = np.sign(delta).fillna(0.0)
        streak_groups = (direction != direction.shift()).cumsum()
        streak_counts = (
            df.groupby(streak_groups, observed=False).cumcount() + 1
        ) * direction

        streak_delta = streak_counts.diff()
        streak_gain = streak_delta.clip(lower=0)
        streak_loss = -streak_delta.clip(upper=0)

        alpha_streak = 1 / max(len_rsi_streak, 1)
        streak_avg_gain = streak_gain.ewm(alpha=alpha_streak, adjust=False).mean()
        streak_avg_loss = streak_loss.ewm(alpha=alpha_streak, adjust=False).mean()
        streak_rs = streak_avg_gain / streak_avg_loss.replace(0, np.nan)
        streak_rsi = 100 - (100 / (1 + streak_rs))

        roc1 = price.pct_change(1)
        percent_rank = roc1.rolling(len_roc_rank).rank(pct=True) * 100.0

        return (price_rsi + streak_rsi + percent_rank) / 3.0
