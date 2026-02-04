#!/usr/bin/env python3
from pathlib import Path
import pandas as pd

RUNS = [
    "260202_090827__HOOD_IB_maxLossPCT001_300d",
    "260202_090625_HOOD_IB_maxLossPct0_300d",
    "260203_221225_HOOD_IB_allign2golden_300d",
]
ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts" / "backtests"
OUT = ROOT / "docs" / "audits" / "intent_row_case_studies.md"

lines = ["# Intent row case studies", ""]

for run in RUNS:
    run_dir = ART / run
    events_path = run_dir / "events_intent.csv"
    fills_path = run_dir / "fills.csv"
    trades_path = run_dir / "trades.csv"
    if not events_path.exists():
        lines.append(f"## {run}\n\n- missing events_intent.csv")
        continue
    events = pd.read_csv(events_path)
    fills = pd.read_csv(fills_path) if fills_path.exists() else pd.DataFrame()
    trades = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()

    lines.append(f"## {run}")

    # pick representative rows
    candidates = events.copy()
    # prefer rows with dbg fields
    if "dbg_mother_ts" in candidates.columns:
        candidates = candidates[candidates["dbg_mother_ts"].notna()]
    # prefer rows with exit_reason
    if "exit_reason" in candidates.columns:
        with_exit = candidates[candidates["exit_reason"].notna()]
    else:
        with_exit = candidates.iloc[0:0]

    sample_rows = []
    if not with_exit.empty:
        sample_rows.append(with_exit.iloc[0])
    # row that later became a trade
    if not trades.empty and "template_id" in trades.columns:
        tid = trades.iloc[0]["template_id"]
        match = candidates[candidates.get("template_id") == tid]
        if not match.empty:
            sample_rows.append(match.iloc[0])
    # fill to 5 rows
    for _, row in candidates.head(5).iterrows():
        if len(sample_rows) >= 5:
            break
        sample_rows.append(row)

    if not sample_rows:
        lines.append("- no rows selected\n")
        continue

    for i, row in enumerate(sample_rows, start=1):
        tid = row.get("template_id", "")
        sym = row.get("symbol", "")
        signal_ts = row.get("signal_ts", "")
        lines.append(f"### case {i}: template_id={tid} symbol={sym} signal_ts={signal_ts}")
        # list suspicious fields
        suspicious = []
        for col in ["dbg_trigger_ts","dbg_exit_ts_ny","dbg_valid_to_ts_utc","exit_ts","exit_reason"]:
            if col in row and pd.notna(row[col]):
                suspicious.append(f"{col}={row[col]}")
        if suspicious:
            lines.append("- suspicious fields: " + ", ".join(suspicious))

        # show short dict subset
        subset_cols = [c for c in ["template_id","symbol","signal_ts","side","entry_price","stop_price","take_profit_price","exit_ts","exit_reason"] if c in row]
        subset = {c: row[c] for c in subset_cols}
        lines.append("- intent subset: " + str(subset))

        if not fills.empty and "template_id" in fills.columns:
            frows = fills[fills["template_id"] == tid].head(3)
            if not frows.empty:
                lines.append("- fills: " + frows[[c for c in frows.columns if c in ["fill_ts","fill_price","fill_reason","side","template_id"]]].to_dict(orient="records").__str__())
        if not trades.empty and "template_id" in trades.columns:
            trows = trades[trades["template_id"] == tid].head(1)
            if not trows.empty:
                lines.append("- trade: " + trows[[c for c in trows.columns if c in ["entry_price","exit_price","pnl","exit_reason","template_id"]]].to_dict(orient="records").__str__())
        lines.append("")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {OUT}")
