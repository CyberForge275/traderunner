"""Spyder helper: run the local_loader_cli smoke test for last 30 days.

Usage in Spyder:
- Open this file
- Press Run
"""

from __future__ import annotations

import datetime as dt
import sys
import importlib
from pathlib import Path

import pandas as pd
from IPython.display import display

REPO_ROOT = Path(__file__).resolve().parents[4]
# Remove competing workspace repo source paths that can shadow traderunner modules.
sys.path = [p for p in sys.path if "marketdata-monorepo/src" not in str(p)]
for p in (str(REPO_ROOT / "src"), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Spyder kernels may already have `trade` loaded from another repo path
# (e.g. marketdata-monorepo). Purge cached modules so imports resolve from
# traderunner/src according to the path order above.
for mod in ("trade.session_windows", "trade"):
    if mod in sys.modules:
        del sys.modules[mod]
importlib.invalidate_caches()

from strategies.harami_break.pattern_detection import enrich_inside_pattern_frame
from strategies.harami_break.session_logic import apply_signal_validity
from strategies.harami_break.local_loader_cli import (
    build_ensure_request,
    load_local_dataframe,
    normalize_date_window,
)
from strategies.config.managers.harami_break_manager import HaramiBreakConfigManager
from core.settings.runtime_config import get_marketdata_data_root, get_runtime_config
from axiom_bt.pipeline.marketdata_stream_client import MarketdataStreamClient

LOADED_DF: pd.DataFrame | None = None
ENRICHED_DF: pd.DataFrame | None = None


def main() -> int:
    

    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=30)
    strategy_version = "1.0.0"
    symbol = "HOOD"
    manager = HaramiBreakConfigManager()
    core = manager.get(strategy_version)["core"]
    runtime_cfg = get_runtime_config()
    data_root = get_marketdata_data_root()
    client = MarketdataStreamClient(
        base_url=runtime_cfg.services.marketdata_stream_url,
        enabled=True,
    )
    start_date, end_date = normalize_date_window(start_date=start_date, end_date=end_date)
    req = build_ensure_request(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        core=core,
        data_root=data_root,
    )
    print(
        "Running direct loader:"
        f" symbol={symbol} tf_m{req.timeframe_minutes} range={start_date}..{end_date}"
        f" mode={req.session_mode} tz={req.session_timezone}"
    )
    ensure_resp = client.ensure_bars(req)
    if ensure_resp.get("status") not in {"ok", "backfilled"}:
        raise RuntimeError(f"ensure_bars failed: {ensure_resp}")

    global LOADED_DF, ENRICHED_DF
    ENRICHED_DF = None
    df = load_local_dataframe(
        symbol=symbol,
        timeframe_minutes=req.timeframe_minutes,
        data_root=Path(req.data_root),
    )
    start_ts = pd.Timestamp(start_date.isoformat(), tz="UTC")
    end_ts = pd.Timestamp(end_date.isoformat(), tz="UTC") + pd.Timedelta(days=1)
    df = df[(df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)].copy()
    LOADED_DF = df.copy()
    enriched = enrich_inside_pattern_frame(
        df,
        definition_mode=str(core["inside_bar_definition_mode"]),
        strict=bool(core["strict_mode"]),
        session_windows=list(core.get("session_windows", [])),
        session_timezone=str(core["session_timezone"]),
    )
    enriched = apply_signal_validity(
        enriched,
        timeframe_minutes=int(core["timeframe_minutes"]),
        session_windows=list(core["session_windows"]),
        session_timezone=str(core["session_timezone"]),
        order_validity_policy=str(core["order_validity_policy"]),
        order_validity_minutes=int(core["order_validity_minutes"]),
        order_validity_bars=int(core["order_validity_bars"]),
    )
    if "is_inside_bar" in enriched.columns:
        enriched["long_trigger_price"] = enriched["mother_bar_high"].where(enriched["is_inside_bar"])
        enriched["short_trigger_price"] = enriched["mother_bar_low"].where(enriched["is_inside_bar"])
    ENRICHED_DF = enriched.copy()

    print(
        f"loaded symbol={symbol} tf_m{req.timeframe_minutes} rows={len(df)} "
        f"range={start_date}..{end_date}"
    )
    print(f"ensure_status={ensure_resp.get('status')} gaps_after={ensure_resp.get('gaps_after')}")

    # Console-friendly formatting for Spyder
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 180)
    pd.set_option("display.max_rows", 30)

    print("\n--- DATAFRAME INFO ---")
    print(df.info())
    print("\n--- AVAILABLE COLUMNS ---")
    print(", ".join(df.columns.tolist()))
    print("\n--- HEAD (20) ---")
    print(df.head(20).to_string(index=False))
    print("\n--- TAIL (20) ---")
    print(df.tail(20).to_string(index=False))
    print("\n--- NUMERIC SUMMARY ---")
    print(df.describe(include=["number"]).to_string())

    out_path = Path("/tmp/harami_loader_hood_m5_last30d.csv")
    df.to_csv(out_path, index=False)
    print(f"\nCSV export: {out_path}")

    print("\n--- DISPLAY TABLE (Spyder/IPython) ---")
    display(df)
    print("\nDataFrame variable available as: LOADED_DF")
    if ENRICHED_DF is not None:
        print("\n--- ENRICHED COLUMNS ---")
        print(", ".join(ENRICHED_DF.columns.tolist()))
        print("\n--- ENRICHED HEAD (20) ---")
        print(ENRICHED_DF.head(20).to_string(index=False))
        print("\nDataFrame variable available as: ENRICHED_DF")

    print("\nSpyder smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
