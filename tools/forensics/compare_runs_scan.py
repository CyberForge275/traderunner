#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

from compare_runs_day import _parse_ts, _signal_day_ny, _choose_key

REQUIRED_DBG = [
    "dbg_trigger_ts",
    "dbg_inside_ts",
    "dbg_mother_ts",
    "dbg_breakout_level",
    "dbg_mother_high",
    "dbg_mother_low",
    "dbg_mother_range",
    "dbg_valid_from_ts_utc",
    "dbg_valid_to_ts_utc",
    "dbg_order_expired",
    "dbg_order_expire_reason",
    "dbg_effective_valid_from_policy",
]


def _load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _dbg_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("dbg_")]


def _sig_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("sig_")]


def _coverage(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    for c in cols:
        if c not in df.columns:
            rows.append({"column": c, "non_null_pct": 0.0, "exists": False})
        else:
            non_null_pct = df[c].notna().mean() * 100 if len(df) else 0.0
            rows.append({"column": c, "non_null_pct": non_null_pct, "exists": True})
    return pd.DataFrame(rows)


def _day_metrics(g: pd.DataFrame, p: pd.DataFrame, day) -> dict:
    g_day = g[g["day_ny"] == day]
    p_day = p[p["day_ny"] == day]
    key_cols, key_ts = _choose_key(g_day, p_day)

    g_key = g_day[key_cols].copy()
    p_key = p_day[key_cols].copy()
    common = g_key.merge(p_key, on=key_cols, how="inner")
    g_only = g_key.merge(p_key, on=key_cols, how="left", indicator=True)
    g_only = g_only[g_only["_merge"] == "left_only"][key_cols]
    p_only = p_key.merge(g_key, on=key_cols, how="left", indicator=True)
    p_only = p_only[p_only["_merge"] == "left_only"][key_cols]

    g2 = g_day.rename(columns={"template_id": "template_id_g"})
    p2 = p_day.rename(columns={"template_id": "template_id_p"})
    cmp_df = g2.merge(p2, on=key_cols, how="inner", suffixes=("_g", "_p"))

    entry_sl_tp_diff_count = 0
    if not cmp_df.empty:
        for col in ["entry_price","stop_price","take_profit_price"]:
            cg = f"{col}_g"
            cp = f"{col}_p"
            if cg in cmp_df.columns and cp in cmp_df.columns:
                diff = (cmp_df[cp] - cmp_df[cg]).abs() > 1e-6
                entry_sl_tp_diff_count += diff.sum()
        entry_sl_tp_diff_count = int(entry_sl_tp_diff_count)

    return {
        "day_ny": day,
        "intents_g": len(g_day),
        "intents_p": len(p_day),
        "common": len(common),
        "only_golden": len(g_only),
        "only_parity": len(p_only),
        "entry_sl_tp_diff_count": entry_sl_tp_diff_count,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", required=True)
    ap.add_argument("--parity", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--tz", default="America/New_York")
    args = ap.parse_args()

    golden = Path(args.golden)
    parity = Path(args.parity)

    g = _load_csv(golden / "events_intent.csv")
    p = _load_csv(parity / "events_intent.csv")

    ts_cols = ["signal_ts","dbg_trigger_ts"]
    g = _parse_ts(g, ts_cols)
    p = _parse_ts(p, ts_cols)

    g = g[g["symbol"] == args.symbol].copy()
    p = p[p["symbol"] == args.symbol].copy()

    g["day_ny"] = _signal_day_ny(g)
    p["day_ny"] = _signal_day_ny(p)

    days = sorted(set(g["day_ny"]).intersection(set(p["day_ny"])))

    rows = []
    first_divergence = None
    first_rule = None
    for day in days:
        metrics = _day_metrics(g, p, day)
        rows.append(metrics)
        # rule checks
        if metrics["intents_g"] != metrics["intents_p"]:
            first_divergence = day
            first_rule = 1
            break
        if metrics["common"] != metrics["intents_g"] or metrics["only_golden"] or metrics["only_parity"]:
            first_divergence = day
            first_rule = 2
            break
        if metrics["entry_sl_tp_diff_count"] > 0:
            first_divergence = day
            first_rule = 3
            break

    df_days = pd.DataFrame(rows)
    out_days = Path("docs/audits/first_divergence_golden_vs_parity_days.csv")
    out_md = Path("docs/audits/first_divergence_golden_vs_parity.md")

    df_days.to_csv(out_days, index=False)

    report = []
    report.append("# First Divergence — Golden vs Parity\n\n")
    report.append(f"Golden: `{golden}`\n")
    report.append(f"Parity: `{parity}`\n")
    report.append(f"Symbol: `{args.symbol}`\n\n")

    report.append(f"First divergence day: {first_divergence}\n")
    report.append(f"Rule triggered: {first_rule}\n\n")

    report.append("## Day Metrics (head)\n")
    report.append(df_days.head(20).to_markdown(index=False))
    report.append("\n\n")

    out_md.write_text("\n".join(report))

    # DBG parity readiness
    dbg_md = Path("docs/audits/dbg_parity_readiness_golden_vs_parity.md")
    dbg_csv = Path("docs/audits/dbg_parity_readiness_golden_vs_parity.csv")

    g_dbg = _dbg_cols(g)
    p_dbg = _dbg_cols(p)
    g_sig = _sig_cols(g)
    p_sig = _sig_cols(p)

    cov_g = _coverage(g, g_dbg)
    cov_p = _coverage(p, p_dbg)

    missing_required = [c for c in REQUIRED_DBG if c not in p.columns]

    inv_rows = []
    for c in sorted(set(g_dbg + p_dbg)):
        inv_rows.append({
            "column": c,
            "golden_exists": c in g.columns,
            "parity_exists": c in p.columns,
            "golden_non_null_pct": cov_g[cov_g["column"] == c]["non_null_pct"].iloc[0] if c in g.columns else 0.0,
            "parity_non_null_pct": cov_p[cov_p["column"] == c]["non_null_pct"].iloc[0] if c in p.columns else 0.0,
        })

    inv_df = pd.DataFrame(inv_rows)
    inv_df.to_csv(dbg_csv, index=False)

    dbg_report = []
    dbg_report.append("# DBG Parity Readiness — Golden vs Parity\n\n")
    dbg_report.append(f"Golden dbg_*: {sorted(g_dbg)}\n\n")
    dbg_report.append(f"Parity dbg_*: {sorted(p_dbg)}\n\n")
    dbg_report.append(f"Golden sig_*: {sorted(g_sig)}\n\n")
    dbg_report.append(f"Parity sig_*: {sorted(p_sig)}\n\n")
    dbg_report.append("## Required dbg_* missing in Parity\n")
    dbg_report.append("(" + ", ".join(missing_required) + ")\n\n")
    dbg_report.append("## Coverage (non-null %)\n")
    dbg_report.append(inv_df.to_markdown(index=False))

    dbg_md.write_text("\n".join(dbg_report))

    print("WROTE", out_md)
    print("WROTE", out_days)
    print("WROTE", dbg_md)
    print("WROTE", dbg_csv)


if __name__ == "__main__":
    main()
