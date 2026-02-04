#!/usr/bin/env python3
from pathlib import Path
import pandas as pd

RUN = "260202_090827__HOOD_IB_maxLossPCT001_300d"
ROOT = Path(__file__).resolve().parents[2]
EVENTS = ROOT / "artifacts" / "backtests" / RUN / "events_intent.csv"
OUT_CSV = ROOT / "docs" / "audits" / "intent_dependency_map.csv"
OUT_MD = ROOT / "docs" / "audits" / "intent_dependency_map.md"

if not EVENTS.exists():
    raise SystemExit(f"missing {EVENTS}")

df = pd.read_csv(EVENTS)
cols = df.columns.tolist()

rows = []
for col in cols:
    producer = "signals.generate_intent"
    producer_ref = "src/axiom_bt/pipeline/signals.py:63-176"
    source = "signals_frame"
    if col in {"strategy_id","strategy_version","breakout_confirmation"}:
        source = "params"
    if col in {"template_id","signal_ts","symbol","side","entry_price","stop_price","take_profit_price","exit_ts","exit_reason"}:
        source = "signals_frame"
    if col.startswith("sig_"):
        source = "signals_frame"  # copied from sig columns
    if col.startswith("dbg_"):
        source = "signals_frame/params"

    # time of knowledge heuristic
    if col in {"signal_ts","symbol","side","entry_price","stop_price","take_profit_price","template_id"}:
        time = "known_at_signal_close"
    elif col in {"exit_ts","exit_reason","dbg_valid_to_ts_utc","dbg_valid_to_ts_ny","dbg_valid_to_ts","dbg_exit_ts_ny"}:
        time = "scheduled_at_signal_time (future)"
    elif col in {"dbg_valid_from_ts_utc","dbg_valid_from_ts","dbg_valid_from_ts_ny","dbg_effective_valid_from_policy"}:
        time = "known_at_signal_close"
    elif col in {"dbg_trigger_ts"}:
        time = "strategy_defined (often signal_ts)"
    elif col.startswith("sig_"):
        time = "known_at_signal_close"
    elif col.startswith("dbg_"):
        time = "known_at_signal_close"
    else:
        time = "unknown"

    risk = "potential_lookahead" if col in {"exit_ts","exit_reason","dbg_valid_to_ts_utc","dbg_valid_to_ts_ny","dbg_valid_to_ts","dbg_exit_ts_ny","dbg_trigger_ts"} else "low"

    rows.append({
        "column_name": col,
        "producer": producer,
        "producer_ref": producer_ref,
        "source": source,
        "time_of_knowledge": time,
        "lookahead_risk": risk,
    })

out_df = pd.DataFrame(rows)
OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
out_df.to_csv(OUT_CSV, index=False)

# write md
lines = ["# Intent dependency map", "", f"Run: {RUN}", "", "Columns:"]
for row in rows:
    lines.append(
        f"- {row['column_name']}: producer={row['producer']} ({row['producer_ref']}), source={row['source']}, time={row['time_of_knowledge']}, risk={row['lookahead_risk']}"
    )
OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {OUT_CSV} and {OUT_MD}")
