"""Spyder-friendly helper to inspect one impulse setup in isolation.

This stays independent from the existing sweet-spot runtime path:
- same marketdata-stream contract
- same daily normalization expectations
- no changes to current scan/backtest logic
"""

from __future__ import annotations

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

from strategies.perlentaucher_daily_scan.daily_pipeline import normalize_daily_ohlcv_frame
from strategies.perlentaucher_daily_scan.impulse_inspection import inspect_impulse_setup


USE_MARKETDATA_API = True
BASE_URL = "http://127.0.0.1:8090"
EXPORT_MERGED_ENDPOINT = "/daily/v2/export_merged"
RAW_DATA_PATH = Path("/var/lib/trading/marketdata/mysql_daily/exports/stock_list_2025-03-01_2025-09-30.parquet")

SYMBOL = "AXTI"
BREAKOUT_DATE = "2025-08-20"
VALID_FROM = "2025-03-01"
VALID_TO = "2025-09-30"

PRE_WINDOW = 30
CONFIRM_OFFSET = 1
TRIM_TOP_N = 1
TRIM_BOTTOM_N = 1

MIN_PRICE_LR_TRIMMED = -1.0
MIN_VOL_LR_TRIMMED = -1_000_000.0
MIN_PRICE_RATIO_PREV_TO_BREAKOUT = 1.10
MIN_VOLUME_RATIO_PREV_TO_BREAKOUT = 3.0
MIN_PRICE_RATIO_PREV_TO_CONFIRM = 1.05
MIN_VOLUME_RATIO_PREV_TO_CONFIRM = 1.20


def fetch_daily_stock_data(*, base_url: str, symbol: str, valid_from: str, valid_to: str) -> tuple[pd.DataFrame, dict]:
    url = f"{base_url.rstrip('/')}{EXPORT_MERGED_ENDPOINT}"
    payload = {
        "universe": "US",
        "asset_class": "stock",
        "symbol_mode": "LIST",
        "symbols": [symbol],
        "valid_from": valid_from,
        "valid_to": valid_to,
    }
    response = requests.post(url, json=payload, timeout=300)
    response.raise_for_status()
    meta = response.json()
    merged_path = Path(meta["merged_parquet_path"])
    if not merged_path.exists():
        raise FileNotFoundError(f"marketdata export parquet not found: {merged_path}")
    return pd.read_parquet(merged_path), meta


def main() -> int:
    if USE_MARKETDATA_API:
        raw_df, meta = fetch_daily_stock_data(
            base_url=BASE_URL,
            symbol=SYMBOL,
            valid_from=VALID_FROM,
            valid_to=VALID_TO,
        )
    else:
        raw_df = pd.read_parquet(RAW_DATA_PATH)
        meta = {"merged_parquet_path": str(RAW_DATA_PATH), "status": "local"}

    daily_df = normalize_daily_ohlcv_frame(raw_df)
    inspection = inspect_impulse_setup(
        daily_df,
        symbol=SYMBOL,
        breakout_date=BREAKOUT_DATE,
        pre_window=PRE_WINDOW,
        confirm_offset=CONFIRM_OFFSET,
        trim_top_n=TRIM_TOP_N,
        trim_bottom_n=TRIM_BOTTOM_N,
        min_price_lr_trimmed=MIN_PRICE_LR_TRIMMED,
        min_vol_lr_trimmed=MIN_VOL_LR_TRIMMED,
        min_price_ratio_prev_to_breakout=MIN_PRICE_RATIO_PREV_TO_BREAKOUT,
        min_volume_ratio_prev_to_breakout=MIN_VOLUME_RATIO_PREV_TO_BREAKOUT,
        min_price_ratio_prev_to_confirm=MIN_PRICE_RATIO_PREV_TO_CONFIRM,
        min_volume_ratio_prev_to_confirm=MIN_VOLUME_RATIO_PREV_TO_CONFIRM,
    )

    INSPECTION_RESULT = inspection  # noqa: F841 - Spyder inspection hook
    INSPECTION_DF = pd.DataFrame([inspection])  # noqa: F841 - Spyder inspection hook
    RAW_DF = raw_df  # noqa: F841 - Spyder inspection hook
    DAILY_DF = daily_df  # noqa: F841 - Spyder inspection hook
    META = meta  # noqa: F841 - Spyder inspection hook

    print("impulse inspection")
    print(f"  symbol={SYMBOL}")
    print(f"  breakout_date={BREAKOUT_DATE}")
    print(f"  source={meta.get('merged_parquet_path')}")
    print(INSPECTION_DF.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
