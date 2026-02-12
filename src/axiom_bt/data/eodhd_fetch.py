from __future__ import annotations

import os
import logging
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

class NetworkUnavailableError(RuntimeError):
    pass


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

EODHD API Limitations:
    - Interval 1m: Maximum 120 days per request
    - Interval 5m: Maximum 600 days per request
    - No from/to parameters: Returns last 120 days automatically

    For historical data beyond 120 days, use chunked fetching (fetch in
    120-day windows and merge results).

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
    >>> # Fetch TSLA data (gets all available ~120 days max)
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
Version: 2.0 (Simplified fetch - no date range, max 120 days)
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
    try:
        socket.socket()
    except OSError as exc:
        if "Operation not permitted" in str(exc):
            raise NetworkUnavailableError(
                "Network disabled in this runner (socket blocked). Run backtest outside sandbox or enable offline cache mode."
            ) from exc
    safe_params = dict(params)
    if "api_token" in safe_params:
        safe_params["api_token"] = "***"
    try:
        response = requests.get(url, params=params, timeout=30)
    except Exception as exc:
        # Provide transparent network error details (DNS, TLS, proxy, etc.)
        logger.error(
            "EODHD request failed: url=%s params=%s error_type=%s error=%r",
            url,
            safe_params,
            type(exc).__name__,
            exc,
        )
        raise
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
    logger.info(
        "EODHD response: url=%s params=%s status=%s",
        url,
        safe_params,
        response.status_code,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        logger.error(
            "EODHD HTTP error: url=%s params=%s status=%s body=%s",
            url,
            safe_params,
            response.status_code,
            (response.text or "")[:500],
        )
        raise
    return response.json()


def fetch_intraday_1m_to_parquet(
    symbol: str,
    exchange: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    out_dir: Path = Path("artifacts/data_m1"),
    tz: str = "Europe/Berlin",
    use_sample: bool = False,
    save_raw: bool = True,
    filter_rth: bool = True,
    allow_legacy_http_backfill: bool = False,
) -> Path:
    """
    Fetch 1-minute intraday OHLCV data from EODHD and save as parquet.

    Behavior:
        - If start_date/end_date are None: Fetches last 120 days (EODHD default)
        - If start_date/end_date provided: Fetches exact range
        - Validates range ≤ 120 days (EODHD limit for 1m interval)

    EODHD Limitation:
        - 1-minute interval: Maximum 120 days per request
        - Raises ValueError if requested range exceeds 120 days

    Args:
        symbol: Stock ticker (e.g., 'TSLA', 'AAPL')
        exchange: Exchange code (e.g., 'US', 'NASDAQ')
        start_date: Start date 'YYYY-MM-DD' or None for default (last 120 days)
        end_date: End date 'YYYY-MM-DD' or None for default (last 120 days)
        out_dir: Output directory for parquet file (default: artifacts/data_m1)
        tz: Timezone for output timestamp conversion (default: Europe/Berlin)
        use_sample: If True, load sample data instead of calling API (for testing)
        save_raw: If True, save unfiltered data to *_raw.parquet (default: True)
        filter_rth: If True, filter final output to RTH only 09:30-16:00 ET (default: True)

    Returns:
        Path to saved parquet file (RTH-filtered if filter_rth=True, otherwise raw)

    Raises:
        ValueError: If requested date range exceeds 120 days
        SystemExit: If no data returned from EODHD API

    Notes:
        - Raw data saved to {symbol}_raw.parquet contains all hours (Pre+RTH+After)
        - Filtered data saved to {symbol}.parquet contains only RTH (09:30-16:00 ET)
        - M5/M15 aggregation should use RTH-filtered data for accurate signals

    Examples:
        >>> # Default: Last 120 days
        >>> path = fetch_intraday_1m_to_parquet('TSLA', 'US')

        >>> # Specific range (60 days, valid)
        >>> path = fetch_intraday_1m_to_parquet(
        ...     'HOOD', 'US',
        ...     start_date='2024-10-01',
        ...     end_date='2024-11-30'
        ... )

        >>> # Invalid range (> 120 days) raises ValueError
        >>> path = fetch_intraday_1m_to_parquet(
        ...     'SPY', 'US',
        ...     start_date='2024-01-01',
        ...     end_date='2024-06-01'  # 152 days → ValueError!
        ... )
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if os.environ.get("EODHD_OFFLINE") == "1":
        cached_path = out_dir / f"{symbol}.parquet"
        if cached_path.exists():
            logger.info("[%s] EODHD offline: using cached data %s", symbol, cached_path)
            return cached_path
        raw_path = out_dir / f"{symbol}_raw.parquet"
        if raw_path.exists():
            logger.info("[%s] EODHD offline: using cached data %s", symbol, raw_path)
            return raw_path
        raise FileNotFoundError(
            f"EODHD offline mode enabled but cache missing for {symbol}.{exchange}. "
            f"Expected {cached_path} or {raw_path}."
        )
    if not allow_legacy_http_backfill and os.environ.get("ALLOW_LEGACY_HTTP_BACKFILL") != "1":
        raise RuntimeError(
            "Legacy EODHD HTTP backfill is disabled (Option B). "
            "Run marketdata_service.backfill_cli and ensure data exists in MARKETDATA_DATA_ROOT."
        )
    token = _read_token()

    if use_sample or not token:
        if not token and not use_sample:
            raise SystemExit("EODHD token not found. Set EODHD_API_TOKEN or pass use_sample=True.")
        # For sample data, use provided dates or defaults
        sample_start = start_date or "2025-01-01"
        sample_end = end_date or "2025-12-19"
        df = _generate_sample_intraday(symbol, sample_start, sample_end, tz, interval="1m")
    else:
        # Build API request
        url = f"https://eodhd.com/api/intraday/{symbol}.{exchange}"
        payload = {
            "api_token": token,
            "interval": "1m",
            "fmt": "json",
        }

        # Add date range if specified
        if start_date and end_date:
            # Convert dates to UTC timestamps
            start_dt = pd.to_datetime(start_date).tz_localize("UTC")
            end_dt = pd.to_datetime(end_date).tz_localize("UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

            # Check 120-day limit and chunk if necessary
            range_days = (end_dt - start_dt).days
            EODHD_MAX_DAYS_1M = 120
            
            if range_days > EODHD_MAX_DAYS_1M:
                # Auto-chunking for large ranges
                logger.info(
                    f"[{symbol}] Requested {range_days} days exceeds EODHD 120-day limit. "
                    f"Auto-chunking into multiple requests..."
                )
                
                # Split into chunks
                chunks = []
                current_start = start_dt
                while current_start < end_dt:
                    chunk_end = min(current_start + pd.Timedelta(days=EODHD_MAX_DAYS_1M), end_dt)
                    chunks.append((current_start, chunk_end))
                    current_start = chunk_end + pd.Timedelta(seconds=1)  # Avoid overlap
                
                logger.info(f"[{symbol}] Split into {len(chunks)} chunks")
                
                # Fetch each chunk
                chunk_dfs = []
                for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
                    chunk_days = (chunk_end - chunk_start).days
                    logger.info(
                        f"[{symbol}] Fetching chunk {i}/{len(chunks)}: "
                        f"{chunk_start.date()} to {chunk_end.date()} ({chunk_days} days)"
                    )
                    
                    chunk_payload = {
                        "api_token": token,
                        "interval": "1m",
                        "fmt": "json",
                        "from": int(chunk_start.timestamp()),
                        "to": int(chunk_end.timestamp()),
                    }
                    
                    chunk_rows = _request(url, chunk_payload)
                    if not chunk_rows:
                        logger.warning(f"[{symbol}] Chunk {i}/{len(chunks)} returned no data")
                        continue
                    
                    chunk_df = pd.DataFrame(chunk_rows)
                    chunk_df["timestamp"] = pd.to_datetime(chunk_df["timestamp"], unit="s", utc=True).dt.tz_convert(tz)
                    chunk_df = chunk_df.rename(
                        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
                    ).set_index("timestamp")[["Open", "High", "Low", "Close", "Volume"]]
                    
                    chunk_dfs.append(chunk_df)
                    logger.info(f"[{symbol}] Chunk {i}/{len(chunks)}: {len(chunk_df):,} rows")
                
                # Merge all chunks
                if not chunk_dfs:
                    raise SystemExit(f"No data from EODHD for {symbol}.{exchange} (all chunks empty)")
                
                df = pd.concat(chunk_dfs)
                df = df.sort_index()
                df = df[~df.index.duplicated(keep='first')]  # Remove any duplicate timestamps
                
                logger.info(
                    f"[{symbol}] Merged {len(chunks)} chunks: {len(df):,} total rows "
                    f"(deduped from {sum(len(c) for c in chunk_dfs):,})"
                )
            else:
                # Single request (≤120 days)
                from_ts = int(start_dt.timestamp())
                to_ts = int(end_dt.timestamp())
                payload["from"] = from_ts
                payload["to"] = to_ts
                
                rows = _request(url, payload)
                if not rows:
                    range_info = f"{start_date} to {end_date}"
                    raise SystemExit(f"No data from EODHD for {symbol}.{exchange} ({range_info})")
                
                df = pd.DataFrame(rows)
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert(tz)
                df = df.rename(
                    columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
                ).set_index("timestamp")[["Open", "High", "Low", "Close", "Volume"]]

    # Save raw data (all hours) if requested
    if save_raw:
        raw_path = out_dir / f"{symbol}_raw.parquet"
        df.sort_index().to_parquet(raw_path)
        logger.info(f"[{symbol}] Saved raw data: {raw_path} ({len(df):,} rows, all hours)")

    # Filter to RTH if requested
    if filter_rth:
        from axiom_bt.data.session_filter import filter_rth_session

        # Filter to RTH (09:30-16:00 ET)
        df_rth = filter_rth_session(df, tz="America/New_York")
        logger.info(
            f"[{symbol}] Filtered to RTH: {len(df_rth):,} rows "
            f"({len(df_rth)/len(df)*100:.1f}% of raw data)"
        )
        df = df_rth

    # Save final data (RTH-filtered or raw depending on filter_rth)
    path = out_dir / f"{symbol}.parquet"
    df.sort_index().to_parquet(path)
    logger.info(f"[{symbol}] Saved final data: {path} ({len(df):,} rows)")

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
    if os.environ.get("EODHD_OFFLINE") == "1":
        cached_path = out_dir / f"{symbol}.parquet"
        if cached_path.exists():
            logger.info("[%s] EODHD offline: using cached data %s", symbol, cached_path)
            return cached_path
        raise FileNotFoundError(
            f"EODHD offline mode enabled but cache missing for {symbol}.{exchange}. "
            f"Expected {cached_path}."
        )
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
