"""Spyder helper to inspect composed sweet-spot matches for one as_of_date.

Edit the constants below, run the file in Spyder, and inspect the exported
DataFrames in the variable explorer.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from strategies.perlentaucher_daily_scan.daily_pipeline import run_sweet_spot_daily_pipeline
from strategies.perlentaucher_daily_scan.marketdata_request import (
    DEFAULT_MIN_HISTORY_DAYS,
    build_stock_universe_request,
)
from strategies.perlentaucher_daily_scan.sweet_spot_aggregation import (
    precompute_sweet_spot_aggregation,
)
from strategies.perlentaucher_daily_scan.sweet_spot_cache import (
    DEFAULT_CACHE_PATH,
    DEFAULT_CONFIG_PATH,
    load_sweet_spot_cache,
    load_sweet_spot_config,
    save_sweet_spot_cache,
)


USE_MARKETDATA_API = True
BASE_URL = "http://127.0.0.1:8090"
EXPORT_MERGED_ENDPOINT = "/daily/v2/export_merged"
USE_REFERENCE_CONFIG = True
CONFIG_PATH = DEFAULT_CONFIG_PATH
CACHE_PATH = DEFAULT_CACHE_PATH
WRITE_CACHE = True
RAW_DATA_PATH = (
    ROOT
    / "src"
    / "strategies"
    / "perlentaucher_daily_scan"
    / "data"
    / "marketdata_daily_stock_all_2026-01-06_2026-04-22.parquet"
)
AS_OF_DATE = "2026-04-23"
LOOKBACK_DAYS = DEFAULT_MIN_HISTORY_DAYS
SWEET_SPOT_PAIRS = [
    ("ATAI", "2026-04-17"),
    ("ATAI", "2026-04-20"),
    ("ATAI", "2026-04-21"),
]
MATCH_MODE = "price_vol"
MAX_CANDIDATES = 25
TEST_SYMBOL = "ATAI"

RAW_DF: pd.DataFrame | None = None
PIPELINE_ARTIFACTS = None
PREFILTER_METRICS_DF: pd.DataFrame | None = None
CANDIDATE_DAILY_DF: pd.DataFrame | None = None
FEATURE_HISTORY_DF: pd.DataFrame | None = None
CANDIDATE_FEATURE_DF: pd.DataFrame | None = None
REFERENCE_FEATURE_DF: pd.DataFrame | None = None
MATCHED_DF: pd.DataFrame | None = None
MATCHED_SYMBOL_DF: pd.DataFrame | None = None
SWEET_SPOT_CONFIG = None
SWEET_SPOT_CACHE = None


def select_symbol_rows(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    symbol_norm = str(symbol).strip().upper()
    if not symbol_norm:
        return df.copy().reset_index(drop=True)
    return df.loc[df["symbol"].astype(str).str.upper() == symbol_norm].reset_index(drop=True)


def _default_date_range(*, as_of_date: str, lookback_days: int) -> tuple[str, str]:
    req = build_stock_universe_request(
        date_from=as_of_date,
        date_to=as_of_date,
        params={"min_history_days": lookback_days},
    )
    return req.date_from.isoformat(), req.date_to.isoformat()


def _fetch_marketdata_raw_frame(*, base_url: str, as_of_date: str, lookback_days: int) -> pd.DataFrame:
    date_from, date_to = _default_date_range(as_of_date=as_of_date, lookback_days=lookback_days)
    url = f"{base_url.rstrip('/')}{EXPORT_MERGED_ENDPOINT}"
    payload = {
        "universe": "US",
        "asset_class": "stock",
        "symbol_mode": "ALL",
        "symbols": [],
        "valid_from": date_from,
        "valid_to": date_to,
    }
    response = requests.post(url, json=payload, timeout=300)
    response.raise_for_status()
    meta = response.json()
    merged_path = Path(meta["merged_parquet_path"])
    if not merged_path.exists():
        raise FileNotFoundError(f"marketdata export parquet not found: {merged_path}")
    return pd.read_parquet(merged_path)


def load_raw_frame() -> pd.DataFrame:
    if USE_MARKETDATA_API:
        return _fetch_marketdata_raw_frame(
            base_url=BASE_URL,
            as_of_date=AS_OF_DATE,
            lookback_days=LOOKBACK_DAYS,
        )
    return pd.read_parquet(RAW_DATA_PATH)


def load_sweet_spot_pairs() -> tuple[dict | None, list[tuple[str, str]]]:
    if USE_REFERENCE_CONFIG:
        config = load_sweet_spot_config(CONFIG_PATH)
        pairs = [tuple(pair) for pair in config["sweet_spot_pairs"]]
        return config, pairs
    return None, SWEET_SPOT_PAIRS


def main() -> int:
    raw_df = load_raw_frame()
    config, sweet_spot_pairs = load_sweet_spot_pairs()
    artifacts = run_sweet_spot_daily_pipeline(
        raw_df,
        as_of_date=AS_OF_DATE,
        sweet_spot_pairs=sweet_spot_pairs,
        match_mode=MATCH_MODE,
        max_candidates=MAX_CANDIDATES,
    )
    cache_payload = None
    if config is not None:
        cache_payload = load_sweet_spot_cache(config=config, cache_path=CACHE_PATH)
        if cache_payload is None and WRITE_CACHE:
            reference_artifacts = precompute_sweet_spot_aggregation(
                artifacts.feature_history_df,
                sweet_spot_pairs=sweet_spot_pairs,
            )
            save_sweet_spot_cache(
                config=config,
                reference_artifacts=reference_artifacts,
                cache_path=CACHE_PATH,
            )
            cache_payload = load_sweet_spot_cache(config=config, cache_path=CACHE_PATH)

    matched_df = artifacts.matched_df.copy()
    matched_symbol_df = select_symbol_rows(matched_df, TEST_SYMBOL)

    global RAW_DF, PIPELINE_ARTIFACTS, PREFILTER_METRICS_DF, CANDIDATE_DAILY_DF
    global FEATURE_HISTORY_DF, CANDIDATE_FEATURE_DF, REFERENCE_FEATURE_DF
    global MATCHED_DF, MATCHED_SYMBOL_DF, SWEET_SPOT_CONFIG, SWEET_SPOT_CACHE
    RAW_DF = raw_df
    PIPELINE_ARTIFACTS = artifacts
    PREFILTER_METRICS_DF = artifacts.prefilter_metrics_df
    CANDIDATE_DAILY_DF = artifacts.candidate_daily_df
    FEATURE_HISTORY_DF = artifacts.feature_history_df
    CANDIDATE_FEATURE_DF = artifacts.candidate_feature_df
    REFERENCE_FEATURE_DF = artifacts.reference_feature_df
    MATCHED_DF = matched_df
    MATCHED_SYMBOL_DF = matched_symbol_df
    SWEET_SPOT_CONFIG = config
    SWEET_SPOT_CACHE = cache_payload

    print(f"raw_rows={len(raw_df)}")
    print(f"candidate_symbols={len(artifacts.candidate_symbols)}")
    print(f"reference_rows={len(artifacts.reference_feature_df)}")
    print(f"matched_rows={len(matched_df)}")
    if config is not None:
        print(f"reference_config={CONFIG_PATH}")
        print(f"reference_cache={CACHE_PATH}")
        print(f"cache_loaded={'yes' if cache_payload is not None else 'no'}")
    if TEST_SYMBOL.strip():
        print(f"test_symbol={TEST_SYMBOL.strip().upper()} rows={len(matched_symbol_df)}")
        if not matched_symbol_df.empty:
            print(matched_symbol_df.to_string(index=False))
    else:
        print(matched_df.head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
