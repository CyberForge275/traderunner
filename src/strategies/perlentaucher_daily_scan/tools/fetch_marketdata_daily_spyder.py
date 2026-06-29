"""Spyder-friendly helper to fetch unfiltered US daily stock data in memory.

This script talks to marketdata-monorepo via the local HTTP API and uses the
parquet-oriented endpoint for better performance:
    POST /daily/v2/export_merged

Default behavior:
- fetch US stock daily data
- symbol_mode=ALL (no filtering yet)
- last 107 calendar days ending today
- read the returned merged parquet
- normalize to Traderunner daily contract
- run Perlentaucher prefilter
- stop at a breakpoint for Spyder inspection
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import sys

import pandas as pd
import requests

# Allow direct Spyder execution without relying on PYTHONPATH=src:.
ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from strategies.perlentaucher_daily_scan.daily_pipeline import (
    filter_daily_frame_to_candidates,
    normalize_daily_ohlcv_frame,
    select_prefilter_candidate_symbols,
)
from strategies.perlentaucher_daily_scan.marketdata_request import (
    DEFAULT_MIN_HISTORY_DAYS,
    build_stock_universe_request,
)
from strategies.perlentaucher_daily_scan.slope_features import (
    build_inspection_view,
    build_slope_feature_frame,
)


BASE_URL = "http://127.0.0.1:8090"
EXPORT_MERGED_ENDPOINT = "/daily/v2/export_merged"

MARKET = "US"
ASSET_CLASS = "stock"
SYMBOL_MODE = "ALL"
MIN_HISTORY_DAYS = DEFAULT_MIN_HISTORY_DAYS
AS_OF_DATE = date.today().isoformat()


def build_request_payload(*, date_from: str, date_to: str) -> dict:
    return {
        "universe": MARKET,
        "asset_class": ASSET_CLASS,
        "symbol_mode": SYMBOL_MODE,
        "symbols": [],
        "valid_from": date_from,
        "valid_to": date_to,
    }


def default_date_range(*, lookback_days: int = MIN_HISTORY_DAYS) -> tuple[str, str]:
    req = build_stock_universe_request(
        date_from=date.today().isoformat(),
        date_to=date.today().isoformat(),
        params={"min_history_days": lookback_days},
    )
    return req.date_from.isoformat(), req.date_to.isoformat()


def fetch_daily_stock_data(*, base_url: str, date_from: str, date_to: str) -> tuple[pd.DataFrame, dict]:
    url = f"{base_url.rstrip('/')}{EXPORT_MERGED_ENDPOINT}"
    payload = build_request_payload(date_from=date_from, date_to=date_to)

    response = requests.post(url, json=payload, timeout=300)
    response.raise_for_status()
    meta = response.json()

    merged_path = Path(meta["merged_parquet_path"])
    if not merged_path.exists():
        raise FileNotFoundError(f"marketdata export parquet not found: {merged_path}")

    df = pd.read_parquet(merged_path)
    return df, meta


def main() -> int:
    # Spyder users can edit these values directly before running the script.
    date_from, date_to = default_date_range()

    raw_df, meta = fetch_daily_stock_data(
        base_url=BASE_URL,
        date_from=date_from,
        date_to=date_to,
    )
    daily_df = normalize_daily_ohlcv_frame(raw_df)
    prefilter_metrics_df, candidate_symbols = select_prefilter_candidate_symbols(
        daily_df,
        as_of_date=AS_OF_DATE,
    )
    candidate_daily_df = filter_daily_frame_to_candidates(daily_df, candidate_symbols)
    # Spyder debug breakpoint 1:
    # Inspect `daily_df`, `prefilter_metrics_df`, `candidate_symbols`,
    # and `candidate_daily_df` here.
    #breakpoint()
    feature_df = build_slope_feature_frame(candidate_daily_df, as_of_date=AS_OF_DATE)
    candidate_feature_view_df = build_inspection_view(
        candidate_daily_df,
        feature_df,
        as_of_date=AS_OF_DATE,
    )
    # Spyder debug breakpoint 2:
    # Inspect `feature_df` and `candidate_feature_view_df` here.
    breakpoint()

    print("marketdata request")
    print(f"  base_url={BASE_URL}")
    print(f"  endpoint={EXPORT_MERGED_ENDPOINT}")
    print(f"  market={MARKET}")
    print(f"  asset_class={ASSET_CLASS}")
    print(f"  symbol_mode={SYMBOL_MODE}")
    print(f"  date_from={date_from}")
    print(f"  date_to={date_to}")
    print()
    print("marketdata response")
    print(f"  status={meta.get('status')}")
    print(f"  cache_hit={meta.get('cache_hit')}")
    print(f"  merged_rows={meta.get('merged_rows')}")
    print(f"  merged_parquet_path={meta.get('merged_parquet_path')}")
    print()
    print("dataframe")
    print(f"  raw_rows={len(raw_df)}")
    print(f"  normalized_rows={len(daily_df)}")
    print(f"  candidate_count={len(candidate_symbols)}")
    print(f"  candidate_daily_rows={len(candidate_daily_df)}")
    print(f"  feature_rows={len(feature_df)}")
    print(f"  columns={list(daily_df.columns)}")
    print(daily_df.head(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
