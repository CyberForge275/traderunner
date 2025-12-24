from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


class DailySourceType(str, Enum):
    """Supported sources for daily OHLCV data."""

    UNIVERSE = "universe"
    SYMBOL = "symbol"  # reserved for potential per-symbol daily files


@dataclass(frozen=True)
class DailySpec:
    """Specification of a requested daily OHLCV window.

    Attributes
    ----------
    symbols:
        Iterable of ticker strings; empty means "all symbols" in the universe.
    start:
        Inclusive start date (YYYY-MM-DD or datetime.date).
    end:
        Inclusive end date (YYYY-MM-DD or datetime.date).
    tz:
        IANA timezone name; timestamps are converted to this timezone.
    source_type:
        Where to load the data from (currently universe-only).
    universe_path:
        Path to a universe parquet file when using UNIVERSE source_type.
    """

    symbols: Iterable[str]
    start: str | date
    end: str | date
    tz: str = "America/New_York"
    source_type: DailySourceType = DailySourceType.UNIVERSE
    universe_path: Optional[Path] = None


class DailyStore:
    """Central service for loading daily OHLCV data (D1)."""

    def __init__(self, *, default_tz: str = "America/New_York") -> None:
        self._default_tz = default_tz

    def load_universe(self, *, universe_path: Path, tz: Optional[str] = None) -> pd.DataFrame:
        """Load and normalize a universe parquet to a standard D1 frame."""

        if not universe_path.exists():
            raise FileNotFoundError(f"Universe parquet not found: {universe_path}")

        raw = pd.read_parquet(universe_path)
        df = _normalize_universe_frame(raw, tz or self._default_tz)

        # v2 Data Contract Validation
        import os
        if os.environ.get("ENABLE_CONTRACTS", "false").lower() == "true":
            from axiom_bt.contracts import DailyFrameSpec
            # Contract expects TitleCase columns, but we use lowercase internally
            # Create a view with TitleCase columns for validation
            validation_view = df.rename(columns={
                "open": "Open", "high": "High", "low": "Low",
                "close": "Close", "volume": "Volume"
            })
            DailyFrameSpec.assert_valid(validation_view)

        return df

    def load_window(self, spec: DailySpec, *, lookback_days: int = 0) -> pd.DataFrame:
        """Load a date-window slice of daily data for one or more symbols."""

        if spec.source_type != DailySourceType.UNIVERSE:
            raise NotImplementedError("Only universe-based daily data is supported")

        if spec.universe_path is None:
            raise ValueError("DailySpec.universe_path is required for UNIVERSE source_type")

        df = self.load_universe(universe_path=spec.universe_path, tz=spec.tz)

        symbols = {s.strip().upper() for s in spec.symbols if s.strip()}
        if symbols:
            df = df[df["symbol"].isin(symbols)]

        start = _to_timestamp(spec.start, tz=spec.tz or self._default_tz)
        end = _to_timestamp(spec.end, tz=spec.tz or self._default_tz)

        if lookback_days > 0:
            start = start - pd.Timedelta(days=lookback_days)

        mask = (df["timestamp"] >= start) & (df["timestamp"] <= end)
        return df.loc[mask].copy()


def _to_timestamp(value: str | date, tz: str) -> pd.Timestamp:
    """Convert a date-like value to a tz-aware timestamp in the given timezone.

    Daily bars are naturally date-based, so we localize naive dates directly in
    the target timezone instead of going through UTC first (which would shift
    the calendar day for US markets).
    """

    if isinstance(value, date):
        base = pd.Timestamp(value)
    else:
        base = pd.to_datetime(value)

    if base.tzinfo is None:
        return base.tz_localize(tz)
    return base.tz_convert(tz)


def _normalize_universe_frame(raw: pd.DataFrame, target_tz: str) -> pd.DataFrame:
    """Normalize a universe daily parquet (e.g. rudometkin) to a standard frame.

    Output columns: ['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume']
    """

    df = raw.copy()

    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index(level=0)

    if "symbol" not in df.columns:
        first_col = df.columns[0]
        df = df.rename(columns={first_col: "symbol"})

    df["symbol"] = df["symbol"].astype(str).str.upper()

    if "timestamp" not in df.columns:
        if "Date" in df.columns:
            df = df.rename(columns={"Date": "timestamp"})
        else:
            candidates = [c for c in df.columns if c != "symbol"]
            if not candidates:
                raise ValueError("Cannot infer timestamp column from universe parquet")
            df = df.rename(columns={candidates[0]: "timestamp"})

    # Treat daily bars as date-based: localize directly into target_tz to keep
    # the trading date stable (avoid UTC -> local shifts).
    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize(target_tz)
    else:
        ts = ts.dt.tz_convert(target_tz)
    df["timestamp"] = ts

    rename_map: dict[str, str] = {}
    for col in df.columns:
        lower = col.lower()
        if lower == "open":
            rename_map[col] = "open"
        elif lower == "high":
            rename_map[col] = "high"
        elif lower == "low":
            rename_map[col] = "low"
        elif lower == "close":
            rename_map[col] = "close"
        elif lower == "volume":
            rename_map[col] = "volume"
    df = df.rename(columns=rename_map)

    required = ["symbol", "timestamp", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Universe parquet missing required columns: {missing}")

    df = df[required].sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    return df
