from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from axiom_bt.fs import DATA_M1, DATA_M5, DATA_M15, ensure_layout
from axiom_bt.data.eodhd_fetch import fetch_intraday_1m_to_parquet, resample_m1


class Timeframe(str, Enum):
    """Supported intraday timeframes for the central store."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"


@dataclass(frozen=True)
class IntradaySpec:
    """Specification for ensuring intraday data.

    Attributes
    ----------
    symbols:
        Iterable of ticker strings; will be normalized to upper-case.
    start:
        Inclusive start date (YYYY-MM-DD or datetime.date).
    end:
        Inclusive end date (YYYY-MM-DD or datetime.date).
    timeframe:
        Target bar timeframe (M1/M5/M15); controls which resamples are created.
    tz:
        IANA timezone name in which bars are interpreted and returned.
    """

    symbols: Iterable[str]
    start: str | date
    end: str | date
    timeframe: Timeframe
    tz: str = "America/New_York"


class IntradayStore:
    """Central service for ensuring and loading intraday OHLCV data.

    All strategies should use this instead of accessing parquet files directly.
    """

    def __init__(self, *, default_tz: str = "America/New_York") -> None:
        ensure_layout()
        self._default_tz = default_tz

    def ensure(
        self,
        spec: IntradaySpec,
        *,
        force: bool = False,
        use_sample: bool = False,
    ) -> Dict[str, List[str]]:
        """Ensure required intraday data exists on disk.

        Returns a mapping of symbol -> list of actions taken.
        """

        symbols = sorted({s.strip().upper() for s in spec.symbols if s.strip()})
        if not symbols:
            return {}

        start_str = _to_date_str(spec.start)
        end_str = _to_date_str(spec.end)
        tz = spec.tz or self._default_tz

        actions: Dict[str, List[str]] = {}

        for symbol in symbols:
            sym_actions: List[str] = []
            m1_path = DATA_M1 / f"{symbol}.parquet"

            if force or not m1_path.exists():
                fetch_intraday_1m_to_parquet(
                    symbol=symbol,
                    exchange="US",
                    start=start_str,
                    end=end_str,
                    out_dir=DATA_M1,
                    tz=tz,
                    use_sample=use_sample,
                )
                sym_actions.append("fetch_m1")
            else:
                sym_actions.append("use_cached_m1")

            resample_m1(m1_path, DATA_M5, interval="5min", tz=tz)
            sym_actions.append("resample_m5")

            if spec.timeframe == Timeframe.M15:
                resample_m1(m1_path, DATA_M15, interval="15min", tz=tz)
                sym_actions.append("resample_m15")

            actions[symbol] = sym_actions

        return actions

    def load(
        self,
        symbol: str,
        *,
        timeframe: Timeframe,
        tz: Optional[str] = None,
    ) -> pd.DataFrame:
        """Load normalized intraday OHLCV for one symbol/timeframe."""

        symbol = symbol.strip().upper()
        path = self.path_for(symbol, timeframe=timeframe)

        if not path.exists():
            raise FileNotFoundError(f"Intraday parquet not found: {path}")

        frame = pd.read_parquet(path)
        df = _normalize_ohlcv_frame(frame, target_tz=tz or self._default_tz)

        # v2 Data Contract Validation
        import os
        if os.environ.get("ENABLE_CONTRACTS", "false").lower() == "true":
            from axiom_bt.contracts import IntradayFrameSpec
            # Contract expects TitleCase columns, but we use lowercase internally
            validation_view = df.rename(columns={
                "open": "Open", "high": "High", "low": "Low", 
                "close": "Close", "volume": "Volume"
            })
            IntradayFrameSpec.assert_valid(validation_view, tz=tz or self._default_tz)

        return df

    def has_symbol(self, symbol: str, *, timeframe: Timeframe) -> bool:
        symbol = symbol.strip().upper()
        return self.path_for(symbol, timeframe=timeframe).exists()

    def path_for(self, symbol: str, *, timeframe: Timeframe) -> Path:
        symbol = symbol.strip().upper()
        if timeframe == Timeframe.M1:
            base = DATA_M1
        elif timeframe == Timeframe.M5:
            base = DATA_M5
        elif timeframe == Timeframe.M15:
            base = DATA_M15
        else:
            raise ValueError(f"Unsupported timeframe for intraday store: {timeframe}")
        return base / f"{symbol}.parquet"


def _to_date_str(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return value


def _normalize_ohlcv_frame(frame: pd.DataFrame, target_tz: str) -> pd.DataFrame:
    """Normalize raw parquet to a standard OHLCV frame.

    - Accepts either a datetime index or a 'timestamp' column.
    - Ensures tz-aware index in ``target_tz``.
    - Ensures columns: open, high, low, close, volume.
    """

    df = frame.copy()

    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df = df.drop(columns=["timestamp"])
        df.index = ts
    elif isinstance(df.index, pd.DatetimeIndex):
        ts = pd.to_datetime(df.index, errors="coerce", utc=True)
        df.index = ts
    else:
        raise ValueError("Frame must have datetime index or 'timestamp' column")

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    df = df.sort_index()
    df.index = df.index.tz_convert(target_tz)
    df.index.name = "timestamp"

    col_map = {c.lower(): c for c in df.columns}
    required_raw = ["open", "high", "low", "close", "volume"]
    missing = [name for name in required_raw if name not in col_map]
    if missing:
        raise ValueError(f"Intraday parquet missing required columns: {missing}")

    ordered = df[[col_map[name] for name in required_raw]].copy()
    ordered.columns = required_raw
    return ordered
