"""Spyder helper: resolve valid NDX members for a date from external member source.

This is a research/debug script for phase-1 step-1 only:
- fetch current members from marketdata-stream
- intersect them with daily bars available on a specific date
- print the valid symbol set for that date

Adjust the constants below before running from Spyder.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from IPython.display import display

REPO_ROOT = Path(__file__).resolve().parents[4]
for p in (str(REPO_ROOT / "src"), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from strategies.ndx_momentum_rotation.universe import load_universe_snapshot

AS_OF_DATE = "2026-03-25"
SURVIVORSHIP_MODE = "current_members"
UNIVERSE = "NDX"
BASE_URL = "http://127.0.0.1:8090"
DAILY_BARS_PATH = REPO_ROOT / "data" / "universe" / "stocks_data.parquet"
TZ = "America/New_York"

UNIVERSE_SNAPSHOT = None
VALID_SYMBOLS_DF: pd.DataFrame | None = None


def main() -> int:
    global UNIVERSE_SNAPSHOT, VALID_SYMBOLS_DF

    print(
        "Resolving NDX universe:"
        f" as_of_date={AS_OF_DATE}"
        f" survivorship_mode={SURVIVORSHIP_MODE}"
        f" universe={UNIVERSE}"
        f" base_url={BASE_URL}"
        f" daily_bars_path={DAILY_BARS_PATH}"
    )

    snap = load_universe_snapshot(
        as_of_date=AS_OF_DATE,
        survivorship_mode=SURVIVORSHIP_MODE,
        daily_bars_path=DAILY_BARS_PATH,
        tz=TZ,
        universe=UNIVERSE,
        base_url=BASE_URL,
    )

    UNIVERSE_SNAPSHOT = snap
    VALID_SYMBOLS_DF = pd.DataFrame({"symbol": snap.members})

    print("\n--- SNAPSHOT ---")
    print(f"source={snap.source}")
    print(f"pit_available={snap.pit_available}")
    print(f"member_count={len(snap.members)}")

    if not VALID_SYMBOLS_DF.empty:
        print("\n--- VALID SYMBOLS (head 20) ---")
        print(VALID_SYMBOLS_DF.head(20).to_string(index=False))
    else:
        print("\nNo valid symbols resolved for this date.")

    print("\nSpyder variables: UNIVERSE_SNAPSHOT, VALID_SYMBOLS_DF")
    display(VALID_SYMBOLS_DF)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
