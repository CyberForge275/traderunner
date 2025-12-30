#!/usr/bin/env python3
"""Fetch M5 intraday data for RK strategy candidates from EODHD."""

import requests
import pandas as pd
import time
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Configuration
API_TOKEN = "619162ef9b88b1.49903202"
BASE_URL = "https://eodhd.com/api/intraday"
OUTPUT_DIR = Path("artifacts/data_m5")
INTERVAL = "5m"

# Candidate symbols from previous RK analysis (Nov 19-21, 2025)
# Combined unique list of LONG and SHORT candidates
CANDIDATES = sorted(list(set([
    # LONG candidates
    'GLTO', 'MOVE', 'BKKT', 'QURE', 'BTDR', 'NEGG', 'QBTS', 'IREN', 'RGTI',
    'LTBR', 'NTLA', 'BE', 'CSIQ', 'CIFR',
    # SHORT candidates
    'NXTT', 'WW', 'SGBX', 'INDP', 'VOR', 'POAI', 'LCID', 'ABVX', 'OXLC',
    'LXP', 'QURE', 'CELC', 'COGT', 'MLYS', 'TERN', 'PACS'
])))

def fetch_intraday_data(symbol: str):
    """Fetch intraday data for a symbol and save to parquet."""

    print(f"⬇️  Fetching {symbol}...", end=" ", flush=True)

    # Construct URL
    # Calculate date range (last 10 days to cover the analysis period)
    # Current time is ~2025-11-26, so this covers back to mid-Nov
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=15)

    url = f"{BASE_URL}/{symbol}.US"
    params = {
        "api_token": API_TOKEN,
        "fmt": "json",
        "interval": INTERVAL,
        "from": int(start_dt.timestamp()),
        "to": int(end_dt.timestamp())
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        if not data:
            print("❌ No data returned")
            return

        # Manual DataFrame construction to avoid "duplicate keys" error
        # and ensure we extract exactly what we need
        parsed_data = {
            "timestamp": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": []
        }

        for row in data:
            # Handle different time keys
            # EODHD usually sends 'datetime' for formatted string or 'timestamp' for unix
            # We prefer 'datetime' string if available, else convert timestamp
            ts = row.get("datetime")
            if not ts and "timestamp" in row:
                ts = datetime.fromtimestamp(row["timestamp"])

            parsed_data["timestamp"].append(ts)
            parsed_data["open"].append(row.get("open"))
            parsed_data["high"].append(row.get("high"))
            parsed_data["low"].append(row.get("low"))
            parsed_data["close"].append(row.get("close"))
            parsed_data["volume"].append(row.get("volume"))

        df = pd.DataFrame(parsed_data)

        # Ensure timestamp is datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Ensure numeric columns
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col])

        # Save to parquet
        output_file = OUTPUT_DIR / f"{symbol}.parquet"
        df.to_parquet(output_file)

        print(f"✅ Saved {len(df)} rows to {output_file}")

    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"🚀 Fetching M5 data for {len(CANDIDATES)} symbols")
    print(f"📂 Output directory: {OUTPUT_DIR}")
    print("-" * 60)

    for symbol in CANDIDATES:
        fetch_intraday_data(symbol)
        # Be nice to the API
        time.sleep(1)

    print("-" * 60)
    print("✨ Fetch complete!")

if __name__ == "__main__":
    main()
