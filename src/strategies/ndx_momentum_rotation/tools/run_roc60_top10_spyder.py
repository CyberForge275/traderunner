"""Spyder helper: resolve NDX members, compute ROC60, rank Top10."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from IPython.display import display

REPO_ROOT = Path(__file__).resolve().parents[4]
for p in (str(REPO_ROOT / "src"), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from axiom_bt.daily import DailyStore
from strategies.ndx_momentum_rotation.ranking import select_top_n
from strategies.ndx_momentum_rotation.scoring import build_roc_scores
from strategies.ndx_momentum_rotation.universe import load_universe_snapshot

AS_OF_DATE = "2026-03-25"
UNIVERSE = "NDX"
SURVIVORSHIP_MODE = "current_members"
BASE_URL = "http://127.0.0.1:8090"
DAILY_BARS_PATH = REPO_ROOT / "data" / "universe" / "stocks_data.parquet"
TZ = "America/New_York"
LOOKBACK_BARS = 60
TOP_N = 10

UNIVERSE_SNAPSHOT = None
VALID_SYMBOLS_DF: pd.DataFrame | None = None
ROC_SCORES_DF: pd.DataFrame | None = None
TOP10_DF: pd.DataFrame | None = None


def _load_daily_frame(path: Path, tz: str) -> pd.DataFrame:
    store = DailyStore(default_tz=tz)
    return store.load_universe(universe_path=path, tz=tz)


def main() -> int:
    global UNIVERSE_SNAPSHOT, VALID_SYMBOLS_DF, ROC_SCORES_DF, TOP10_DF

    print(
        "Running ROC60 ranking:"
        f" as_of_date={AS_OF_DATE}"
        f" universe={UNIVERSE}"
        f" survivorship_mode={SURVIVORSHIP_MODE}"
        f" base_url={BASE_URL}"
        f" daily_bars_path={DAILY_BARS_PATH}"
        f" lookback_bars={LOOKBACK_BARS}"
        f" top_n={TOP_N}"
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

    daily_df = _load_daily_frame(DAILY_BARS_PATH, TZ)
    daily_df = daily_df[daily_df["symbol"].isin(snap.members)].copy()
    ROC_SCORES_DF = build_roc_scores(
        daily_df,
        as_of_date=AS_OF_DATE,
        lookback_bars=LOOKBACK_BARS,
    )
    TOP10_DF = select_top_n(ROC_SCORES_DF, n=TOP_N, score_column=f"roc{LOOKBACK_BARS}")

    print("\n--- SNAPSHOT ---")
    print(f"member_count={len(snap.members)} source={snap.source}")
    print(f"scored_symbols={len(ROC_SCORES_DF)}")
    print(f"top_count={len(TOP10_DF)}")

    if not TOP10_DF.empty:
        print("\n--- TOP10 ROC60 ---")
        print(TOP10_DF[["rank", "symbol", f"roc{LOOKBACK_BARS}", "close", "bars_available"]].to_string(index=False))
    else:
        print("\nNo symbols produced a ROC60 score.")

    print("\nSpyder variables: UNIVERSE_SNAPSHOT, VALID_SYMBOLS_DF, ROC_SCORES_DF, TOP10_DF")
    display(TOP10_DF)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
