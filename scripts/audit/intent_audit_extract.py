#!/usr/bin/env python3
import csv
from pathlib import Path
import pandas as pd

RUNS = [
    "260202_090827__HOOD_IB_maxLossPCT001_300d",
    "260202_090625_HOOD_IB_maxLossPct0_300d",
    "260203_221225_HOOD_IB_allign2golden_300d",
]
ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts" / "backtests"
OUT_DIR = ROOT / "docs" / "audits"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FORBIDDEN_PREFIXES = {"fill_", "realized_", "pnl", "slippage", "fee", "fees"}
FORBIDDEN_EXACT = {
    "trigger_ts",
    "entry_ts",
    "exit_ts",
    "exit_reason",
    "fill_price",
    "entry_fill_price",
    "exit_fill_price",
    "realized_pnl",
    "pnl",
}

schema_rows = []

for run in RUNS:
    run_dir = ART / run
    events_path = run_dir / "events_intent.csv"
    fills_path = run_dir / "fills.csv"
    trades_path = run_dir / "trades.csv"
    if not events_path.exists():
        print(f"WARN missing events_intent.csv for {run}")
        continue
    events = pd.read_csv(events_path)
    fills = pd.read_csv(fills_path) if fills_path.exists() else pd.DataFrame()
    trades = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()

    events_cols = list(events.columns)
    fills_cols = list(fills.columns)
    trades_cols = list(trades.columns)

    all_cols = sorted(set(events_cols + fills_cols + trades_cols))
    for col in all_cols:
        present = []
        if col in events_cols:
            present.append("events_intent")
        if col in fills_cols:
            present.append("fills")
        if col in trades_cols:
            present.append("trades")
        present_str = ",".join(present)

        forbidden = False
        if col in FORBIDDEN_EXACT:
            forbidden = True
        elif any(col.startswith(pfx) for pfx in FORBIDDEN_PREFIXES):
            forbidden = True
        elif col.startswith("dbg_exit") or col.startswith("dbg_trigger"):
            forbidden = True
        elif col.startswith("dbg_valid_to"):
            forbidden = True

        schema_rows.append({
            "run_id": run,
            "column_name": col,
            "present_in": present_str,
            "forbidden_at_intent_time": "yes" if forbidden else "no/unknown",
        })

    # Lookahead scan: any forbidden columns present in events_intent with non-null values
    forbidden_cols = [c for c in events_cols if (
        c in FORBIDDEN_EXACT
        or any(c.startswith(pfx) for pfx in FORBIDDEN_PREFIXES)
        or c.startswith("dbg_exit")
        or c.startswith("dbg_trigger")
        or c.startswith("dbg_valid_to")
    )]
    scan_lines = []
    for c in forbidden_cols:
        series = events[c]
        non_null = series.notna().sum()
        if non_null:
            sample = series.dropna().head(3).tolist()
            scan_lines.append(f"- {c}: non_null={non_null} sample={sample}")
    out_md = OUT_DIR / f"lookahead_scan_{run}.md"
    out_md.write_text("\n".join([f"# Lookahead scan for {run}", "", *scan_lines]) + "\n", encoding="utf-8")

# Write schema inventory CSV
csv_path = OUT_DIR / "intent_schema_inventory.csv"
with csv_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["run_id","column_name","present_in","forbidden_at_intent_time"])
    writer.writeheader()
    writer.writerows(schema_rows)

print(f"Wrote {csv_path}")
