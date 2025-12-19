from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests


__all__ = [
    "fetch_intraday_1m_to_parquet",
    "resample_m1",
    "resample_m1_to_m5",
    "resample_m1_to_m15",
    "fetch_eod_daily_to_parquet",
]

"""
EODHD Data Fetching Service

This module provides functions to fetch intraday and daily OHLCV data from the
EODHD API and save it as parquet files for use in backtesting.

Key Features:
    - Fetches 1-minute intraday data (up to 120 days history)
    - Resamples M1 → M5, M15 for performance
    - Handles timezone conversion (UTC → target timezone)
    - Sample data generation for testing without API token
    - Simplified fetch: Gets ALL available data (no date range)

Architecture:
    EODHD API → fetch_intraday_1m_to_parquet() → M1 parquet
                                                  ↓
                                           resample_m1()
                                                  ↓
                                              M5/M15 parquet

API Documentation: 
    https://eodhd.com/financial-apis/intraday-historical-data-api

Rate Limits: 
    Varies by subscription (typically 100k requests/day)

Environment Variables:
    EODHD_API_TOKEN: Your EODHD API token (required unless use_sample=True)

Example Usage:
    >>> from axiom_bt.data.eodhd_fetch import fetch_intraday_1m_to_parquet
    >>> from pathlib import Path
    >>> 
    >>> # Fetch TSLA data (gets all available ~60 days)
    >>> path = fetch_intraday_1m_to_parquet(
    ...     symbol='TSLA',
    ...     exchange='US',
    ...     start_date='2025-12-01',  # Parameters kept for compatibility
    ...     end_date='2025-12-19',    # but currently ignored
    ...     out_dir=Path('artifacts/data_m1'),
    ...     tz='America/New_York'
    ... )
    >>> print(f"Data saved to: {path}")

Author: Droid Trading Team
Last Modified: 2025-12-19
Version: 2.0 (Simplified fetch - no date range)
"""



def _read_token() -> Optional[str]:
    token = os.environ.get("EODHD_API_TOKEN")
    """
    Read EODHD API token from environment or config file.
    
    Search order:
        1. EODHD_API_TOKEN environment variable
        2. ~/.config/ib_project/credentials.toml
        3. ~/.config/axiom_bt/credentials.toml
        4. ./configs/credentials.toml
    
    Returns:
        str | None: API token if found, None otherwise
    """
    if token:
        return token.strip()

    for cfg in (
        Path.home() / ".config/ib_project/credentials.toml",
        Path.home() / ".config/axiom_bt/credentials.toml",
        Path.cwd() / "configs/credentials.toml",
    ):
        if cfg.exists():
            for line in cfg.read_text().splitlines():
                if "EODHD_API_TOKEN" in line:
                    return line.split("=")[1].strip().strip('"').strip("'")
    return None


def _standardize_ohlcv(df: pd.DataFrame, tz: str | None = None) -> pd.DataFrame:
    df = df.copy()
    """
    Standardize OHLCV DataFrame schema and timezone.
    
    Transformations:
        1. Rename columns to canonical (Open, High, Low, Close, Volume)
        2. Parse timestamp to DatetimeIndex
        3. Localize to UTC if naive
        4. Convert to target timezone
        5. Sort by timestamp
    
    Args:
        df: Raw DataFrame
        tz: Target timezone
    
    Returns:
        pd.DataFrame: Standardized with tz-aware index
    """

    if not isinstance(df.index, pd.DatetimeIndex):
        ts_col = next((c for c in df.columns if c.lower() in {"ts", "timestamp", "time", "date", "datetime"}), None)
        if ts_col is None:
            raise ValueError("Input data requires a datetime index or timestamp column")
        idx = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
        df = df.drop(columns=[ts_col])
        df.index = idx

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC", nonexistent="shift_forward", ambiguous="NaT")
    if tz:
        df.index = df.index.tz_convert(tz)

    mapping = {}
    aliases = {
        "Open": {"open", "o"},
        "High": {"high", "h"},
        "Low": {"low", "l"},
        "Close": {"close", "c"},
        "Volume": {"volume", "vol", "v"},
    }
    lower_lookup = {c.lower(): c for c in df.columns}
    for target, names in aliases.items():
        for name in names:
            if name in lower_lookup:
                mapping[lower_lookup[name]] = target
                break

    df = df.rename(columns=mapping)
    missing = {"Open", "High", "Low", "Close", "Volume"} - set(df.columns)
    if missing:
        raise KeyError(f"Missing OHLCV columns: {sorted(missing)}")

    df = df.sort_index()
    df.index.name = "timestamp"
    return df[["Open", "High", "Low", "Close", "Volume"]]


def _generate_sample_intraday(
    symbol: str,
    start_date: str,
    end_date: str,
    tz: str,
    interval: str = "1m",
) -> pd.DataFrame:
    freq_map = {"1m": "1min", "5m": "5min", "15m": "15min"}
    rule = freq_map.get(interval, "1min")
    start = pd.to_datetime(start_date).tz_localize("UTC")
    end = pd.to_datetime(end_date).tz_localize("UTC") + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)
    index = pd.date_range(start=start, end=end, freq=rule, tz="UTC")
    rng = np.random.default_rng(abs(hash(symbol)) % 2**32)
    close = 100 + np.cumsum(rng.normal(0, 0.15, len(index)))
    high = close + rng.normal(0.2, 0.05, len(index))
    low = close - rng.normal(0.2, 0.05, len(index))
    open_price = close + rng.normal(0, 0.05, len(index))
    volume = rng.integers(20_000, 120_000, len(index))
    df = pd.DataFrame(
        {
            "Open": open_price,
            "High": np.maximum.reduce([high, open_price, close]),
            "Low": np.minimum.reduce([low, open_price, close]),
            "Close": close,
            "Volume": volume,
        },
        index=index,
    )
    if tz:
        df.index = df.index.tz_convert(tz)
    df.index.name = "timestamp"
    return df


def _generate_sample_daily(
    symbol: str,
    start_date: str,
    end_date: str,
    tz: str,
) -> pd.DataFrame:
    start = pd.to_datetime(start_date).tz_localize("UTC")
    end = pd.to_datetime(end_date).tz_localize("UTC")
    index = pd.date_range(start=start, end=end, freq="D", tz="UTC")
    rng = np.random.default_rng(abs(hash(symbol)) % 2**32)
    close = 120 + np.cumsum(rng.normal(0, 0.8, len(index)))
    high = close + rng.normal(1.2, 0.3, len(index))
    low = close - rng.normal(1.2, 0.3, len(index))
    open_price = close + rng.normal(0, 0.5, len(index))
    volume = rng.integers(1_000_000, 5_000_000, len(index))
    df = pd.DataFrame(
        {
            "Open": open_price,
            "High": np.maximum.reduce([high, open_price, close]),
            "Low": np.minimum.reduce([low, open_price, close]),
            "Close": close,
            "AdjClose": close,
            "Volume": volume,
        },
        index=index,
    )
    if tz:
        df.index = df.index.tz_convert(tz)
    df.index.name = "timestamp"
    return df


def _request(url: str, params: dict) -> list:
    response = requests.get(url, params=params, timeout=30)
    """
    Make HTTP GET request to EODHD API with 30s timeout.
    
    Args:
        url: API endpoint URL
        params: Query parameters (includes api_token)
    
    Returns:
        list: JSON response array
        
    Raises:
        requests.HTTPError: If status 4xx/5xx
        requests.Timeout: If exceeds 30s
    """
    response.raise_for_status()
    return response.json()


def fetch_intraday_1m_to_parquet(
    symbol: str,
    exchange: str,
    start_date: str,
    end_date: str,
    out_dir: Path,
    tz: str = "Europe/Berlin",
    use_sample: bool = False,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    token = _read_token()

    if use_sample or not token:
        if not token and not use_sample:
            raise SystemExit("EODHD token not found. Set EODHD_API_TOKEN or pass use_sample=True.")
        df = _generate_sample_intraday(symbol, start_date, end_date, tz, interval="1m")
    else:
        rows = []
        for day in pd.date_range(start_date, end_date, freq="D"):
            start_ts = int(datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=timezone.utc).timestamp())
            end_ts = int(datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc).timestamp())
            url = f"https://eodhd.com/api/intraday/{symbol}.{exchange}"
            payload = {
                "api_token": token,
                "interval": "1m",
                "from": start_ts,
                "to": end_ts,
                "fmt": "json",
            }
            rows.extend(_request(url, payload))
        if not rows:
            raise SystemExit(f"No data from EODHD for {symbol}.{exchange} {start_date}..{end_date}")
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert(tz)
        df = df.rename(
            columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
        ).set_index("timestamp")[["Open", "High", "Low", "Close", "Volume"]]

    path = out_dir / f"{symbol}.parquet"
    df.sort_index().to_parquet(path)
    return path


def resample_m1(
    m1_parquet: Path,
    out_dir: Path,
    interval: str = "5min",
    tz: str | None = None,
    min_m1_rows: int = 200,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    symbol = m1_parquet.stem
    df_raw = pd.read_parquet(m1_parquet)
    df = _standardize_ohlcv(df_raw, tz=tz)

    if len(df) < min_m1_rows:
        first = df.index.min()
        last = df.index.max()
        raise ValueError(
            f"[ABORT] {symbol} M1 too small for resample: rows={len(df)} (<{min_m1_rows}). Range: {first}..{last}"
        )

    agg = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }
    resampled = df.resample(interval).agg(agg).dropna(how="any")
    if len(resampled) < 10:
        raise ValueError(f"[ABORT] {symbol} resample produced only {len(resampled)} rows (interval {interval}).")

    path = out_dir / f"{symbol}.parquet"
    resampled.to_parquet(path)
    print(f"[OK] {symbol}: {len(resampled)} rows → {path}")
    return path


def resample_m1_to_m5(m1_parquet: Path, out_dir: Path, tz: str | None = None) -> Path:
    return resample_m1(m1_parquet, out_dir, interval="5min", tz=tz)


def resample_m1_to_m15(m1_parquet: Path, out_dir: Path, tz: str | None = None) -> Path:
    return resample_m1(m1_parquet, out_dir, interval="15min", tz=tz)


def fetch_eod_daily_to_parquet(
    symbol: str,
    exchange: str,
    start_date: str,
    end_date: str,
    out_dir: Path,
    tz: str = "America/New_York",
    use_sample: bool = False,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    token = _read_token()

    if use_sample or not token:
        if not token and not use_sample:
            raise SystemExit("EODHD token not found. Set EODHD_API_TOKEN or pass use_sample=True.")
        df = _generate_sample_daily(symbol, start_date, end_date, tz)
    else:
        url = f"https://eodhd.com/api/eod/{symbol}.{exchange}"
        payload = {
            "api_token": token,
            "from": start_date,
            "to": end_date,
            "fmt": "json",
        }
        rows = _request(url, payload)
        if not rows:
            raise SystemExit(f"No EOD data for {symbol}.{exchange} {start_date}..{end_date}")
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(tz)
        df = df.rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "adjusted_close": "AdjClose",
                "volume": "Volume",
            }
        ).set_index("timestamp")[["Open", "High", "Low", "Close", "AdjClose", "Volume"]]

    path = out_dir / f"{symbol}.parquet"
    df.sort_index().to_parquet(path)
    return path
