"""Spyder helper: build placeholder D1 signal frame for perlentaucher_daily_scan.

This is intentionally signal-frame only. No DB providers, no sweet-spot matching,
no intents beyond the empty skeleton contract.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
for p in (str(REPO_ROOT / "src"), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from axiom_bt.daily import DailyStore
from axiom_bt.pipeline.signal_frame_factory import build_signal_frame
import strategies.config.managers  # noqa: F401 - trigger manager self-registration
from strategies.config.registry import config_manager_registry
from strategies.perlentaucher_daily_scan.prefilter import (
    build_volume_prefilter_metrics,
    select_volume_prefilter_candidates,
)


AS_OF_DATE = (dt.date.today() - dt.timedelta(days=1)).isoformat()
UNIVERSE_PATH = REPO_ROOT / "data" / "universe" / "stocks_data.parquet"
SESSION_TIMEZONE = "America/New_York"
STRATEGY_ID = "perlentaucher_daily_scan"
STRATEGY_VERSION = "1.0.0"

SIGNALS_DF: pd.DataFrame | None = None
SIGNAL_SCHEMA = None
BARS_ASOF_DF: pd.DataFrame | None = None
PREFILTER_METRICS_DF: pd.DataFrame | None = None
PREFILTER_CANDIDATES_DF: pd.DataFrame | None = None


def _load_core_params() -> dict:
    manager = config_manager_registry.get_manager(STRATEGY_ID)
    if manager is None:
        raise RuntimeError(f"no config manager registered for {STRATEGY_ID}")
    version_node = manager.get(STRATEGY_VERSION)
    return dict(version_node["core"])


def _load_daily_universe_frame(universe_path: Path) -> pd.DataFrame:
    store = DailyStore(default_tz=SESSION_TIMEZONE)
    return store.load_universe(universe_path=universe_path, tz=SESSION_TIMEZONE)


def _filter_asof_bars(daily_df: pd.DataFrame, as_of_date: str) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of_date).date()
    session_dates = daily_df["timestamp"].dt.tz_convert(SESSION_TIMEZONE).dt.date
    out = daily_df.loc[session_dates == as_of].copy()
    return out.sort_values(["symbol", "timestamp"]).reset_index(drop=True)


def main() -> int:
    daily_df = _load_daily_universe_frame(UNIVERSE_PATH)
    bars_asof = _filter_asof_bars(daily_df, AS_OF_DATE)
    if bars_asof.empty:
        raise ValueError(f"no daily bars available for as_of_date={AS_OF_DATE}")

    params = _load_core_params()
    signals_df, schema = build_signal_frame(
        bars_asof,
        STRATEGY_ID,
        STRATEGY_VERSION,
        params,
    )

    metrics_df = build_volume_prefilter_metrics(
        daily_df,
        as_of_date=AS_OF_DATE,
        session_timezone=SESSION_TIMEZONE,
    )
    candidates_df = select_volume_prefilter_candidates(metrics_df)

    global SIGNALS_DF, SIGNAL_SCHEMA, BARS_ASOF_DF, PREFILTER_METRICS_DF, PREFILTER_CANDIDATES_DF
    SIGNALS_DF = signals_df
    SIGNAL_SCHEMA = schema
    BARS_ASOF_DF = bars_asof
    PREFILTER_METRICS_DF = metrics_df
    PREFILTER_CANDIDATES_DF = candidates_df

    print(
        f"Built placeholder signal frame for {STRATEGY_ID} "
        f"as_of_date={AS_OF_DATE} rows={len(signals_df)} "
        f"prefilter_candidates={len(candidates_df)}"
    )
    if not candidates_df.empty:
        print(candidates_df.head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
