#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def _load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _parse_ts(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], utc=True, errors="coerce")
    return df


def _dbg_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("dbg_")]


def _sig_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("sig_")]


def _signal_day_ny(df: pd.DataFrame) -> pd.Series:
    if "dbg_signal_ts_ny" in df.columns:
        ts = pd.to_datetime(df["dbg_signal_ts_ny"], utc=True, errors="coerce")
        return ts.dt.tz_convert("America/New_York").dt.date
    ts = pd.to_datetime(df["signal_ts"], utc=True, errors="coerce")
    return ts.dt.tz_convert("America/New_York").dt.date


def _choose_key(df_g: pd.DataFrame, df_p: pd.DataFrame):
    if "dbg_trigger_ts" in df_g.columns and "dbg_trigger_ts" in df_p.columns:
        return ["symbol", "side", "dbg_trigger_ts"], "dbg_trigger_ts"
    return ["symbol", "side", "signal_ts"], "signal_ts"

def _compact_reason_series(series: pd.Series) -> str:
    if series is None or series.empty:
        return ""
    vals = series.dropna().astype(str).unique().tolist()
    return "|".join(sorted(vals))

def _fills_trades_summary(
    fills: pd.DataFrame | None,
    trades: pd.DataFrame | None,
    template_id: str,
):
    fills_count = 0
    fills_reasons = ""
    first_fill_ts = None
    first_fill_price = None
    last_fill_ts = None
    last_fill_price = None
    trade_present = False
    trade_exit_reason = None
    trade_exit_ts = None
    trade_pnl = None
    trade_entry_ts = None
    trade_entry_price = None
    trade_exit_price = None

    if fills is not None and "template_id" in fills.columns:
        f = fills[fills["template_id"] == template_id]
        fills_count = len(f)
        if len(f):
            fills_reasons = _compact_reason_series(f.get("reason"))
            ts = pd.to_datetime(f.get("fill_ts"), utc=True, errors="coerce")
            if not ts.isna().all():
                first_idx = ts.idxmin()
                last_idx = ts.idxmax()
                first_fill_ts = ts.loc[first_idx]
                last_fill_ts = ts.loc[last_idx]
                if "fill_price" in f.columns:
                    first_fill_price = f.loc[first_idx, "fill_price"]
                    last_fill_price = f.loc[last_idx, "fill_price"]

    if trades is not None and "template_id" in trades.columns:
        t = trades[trades["template_id"] == template_id]
        if len(t):
            trade_present = True
            row = t.iloc[0]
            if "reason" in t.columns:
                trade_exit_reason = row.get("reason")
            if "exit_ts" in t.columns:
                trade_exit_ts = pd.to_datetime(row.get("exit_ts"), utc=True, errors="coerce")
            if "pnl" in t.columns:
                trade_pnl = row.get("pnl")
            if "entry_ts" in t.columns:
                trade_entry_ts = pd.to_datetime(row.get("entry_ts"), utc=True, errors="coerce")
            if "entry_price" in t.columns:
                trade_entry_price = row.get("entry_price")
            if "exit_price" in t.columns:
                trade_exit_price = row.get("exit_price")

    return {
        "fills_count": fills_count,
        "fills_reasons": fills_reasons,
        "first_fill_ts": first_fill_ts,
        "first_fill_price": first_fill_price,
        "last_fill_ts": last_fill_ts,
        "last_fill_price": last_fill_price,
        "trade_present": trade_present,
        "trade_exit_reason": trade_exit_reason,
        "trade_exit_ts": trade_exit_ts,
        "trade_pnl": trade_pnl,
        "trade_entry_ts": trade_entry_ts,
        "trade_entry_price": trade_entry_price,
        "trade_exit_price": trade_exit_price,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", required=True)
    ap.add_argument("--parity", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--day-ny", required=True)
    ap.add_argument("--include-fills-trades", action="store_true", default=True)
    ap.add_argument("--output-prefix", default=None)
    args = ap.parse_args()

    golden = Path(args.golden)
    parity = Path(args.parity)
    if args.output_prefix:
        prefix = Path(args.output_prefix)
        out_md = prefix.with_suffix(".md")
        out_csv = prefix.with_name(prefix.name + "_common.csv")
    else:
        out_md = Path("docs/audits/delta_golden_vs_parity_2026-01-22.md")
        out_csv = Path("docs/audits/delta_golden_vs_parity_2026-01-22_common.csv")

    g = _load_csv(golden / "events_intent.csv")
    p = _load_csv(parity / "events_intent.csv")
    fills_g = _load_csv(golden / "fills.csv") if (golden / "fills.csv").exists() else None
    fills_p = _load_csv(parity / "fills.csv") if (parity / "fills.csv").exists() else None
    trades_g = _load_csv(golden / "trades.csv") if (golden / "trades.csv").exists() else None
    trades_p = _load_csv(parity / "trades.csv") if (parity / "trades.csv").exists() else None

    ts_cols = [
        "signal_ts","dbg_trigger_ts","dbg_inside_ts","dbg_mother_ts","exit_ts",
        "dbg_valid_from_ts_utc","dbg_valid_to_ts_utc",
        "dbg_valid_from_ts","dbg_valid_to_ts",
        "dbg_valid_from_ts_ny","dbg_valid_to_ts_ny",
    ]
    g = _parse_ts(g, ts_cols)
    p = _parse_ts(p, ts_cols)

    g_day = _signal_day_ny(g)
    p_day = _signal_day_ny(p)
    day = pd.Timestamp(args.day_ny).date()

    g = g[(g["symbol"] == args.symbol) & (g_day == day)].copy()
    p = p[(p["symbol"] == args.symbol) & (p_day == day)].copy()

    key_cols, key_ts = _choose_key(g, p)

    g_key = g[key_cols].copy()
    p_key = p[key_cols].copy()

    common = g_key.merge(p_key, on=key_cols, how="inner")
    g_only = g_key.merge(p_key, on=key_cols, how="left", indicator=True)
    g_only = g_only[g_only["_merge"] == "left_only"][key_cols]
    p_only = p_key.merge(g_key, on=key_cols, how="left", indicator=True)
    p_only = p_only[p_only["_merge"] == "left_only"][key_cols]

    g2 = g.rename(columns={"template_id": "template_id_g"})
    p2 = p.rename(columns={"template_id": "template_id_p"})
    cmp_df = g2.merge(p2, on=key_cols, how="inner", suffixes=("_g", "_p"))

    def add_delta(df, col):
        cg = f"{col}_g"
        cp = f"{col}_p"
        if cg in df.columns and cp in df.columns:
            df[f"delta_{col}"] = df[cp] - df[cg]
            df[f"diff_{col}"] = (df[f"delta_{col}"].abs() > 1e-6)

    for col in ["entry_price","stop_price","take_profit_price"]:
        add_delta(cmp_df, col)

    cols_out = [
        key_ts,
        "template_id_g","template_id_p",
        "side",
        "entry_price_g","entry_price_p","delta_entry_price","diff_entry_price",
        "stop_price_g","stop_price_p","delta_stop_price","diff_stop_price",
        "take_profit_price_g","take_profit_price_p","delta_take_profit_price","diff_take_profit_price",
    ]
    if args.include_fills_trades:
        extras = [
            "fills_count_g","fills_count_p",
            "fills_reasons_g","fills_reasons_p",
            "trade_present_g","trade_present_p",
            "trade_exit_reason_g","trade_exit_reason_p",
            "trade_exit_ts_g","trade_exit_ts_p",
            "trade_pnl_g","trade_pnl_p",
            "trade_entry_ts_g","trade_entry_ts_p",
            "trade_entry_price_g","trade_entry_price_p",
            "trade_exit_price_g","trade_exit_price_p",
        ]
        cols_out.extend(extras)
    cols_out = [c for c in cols_out if c in cmp_df.columns]
    if args.include_fills_trades and not cmp_df.empty:
        rows = []
        for _, row in cmp_df.iterrows():
            tid_g = row.get("template_id_g")
            tid_p = row.get("template_id_p")
            s_g = _fills_trades_summary(fills_g, trades_g, tid_g) if tid_g else {}
            s_p = _fills_trades_summary(fills_p, trades_p, tid_p) if tid_p else {}
            for k, v in s_g.items():
                row[f"{k}_g"] = v
            for k, v in s_p.items():
                row[f"{k}_p"] = v
            rows.append(row)
        cmp_df = pd.DataFrame(rows)
    cmp_df[cols_out].to_csv(out_csv, index=False)

    report = []
    report.append("# Delta Golden vs Parity — 2026-01-22 (NY)\n\n")
    report.append(f"Golden: `{golden}`\n")
    report.append(f"Parity: `{parity}`\n")
    report.append(f"Symbol: `{args.symbol}`\n")
    report.append(f"Day (NY): `{args.day_ny}`\n\n")

    report.append("## Column Inventory\n")
    report.append(f"Golden dbg_*: {sorted(_dbg_cols(g))}\n\n")
    report.append(f"Parity dbg_*: {sorted(_dbg_cols(p))}\n\n")
    report.append(f"Golden sig_*: {sorted(_sig_cols(g))}\n\n")
    report.append(f"Parity sig_*: {sorted(_sig_cols(p))}\n\n")

    report.append("## Counts\n")
    report.append(f"Golden intents (day): {len(g)}\n")
    report.append(f"Parity intents (day): {len(p)}\n\n")

    report.append("## Matching Summary\n")
    report.append(f"Match key: {key_cols}\n")
    report.append(f"Common: {len(common)}\n")
    report.append(f"Only Golden: {len(g_only)}\n")
    report.append(f"Only Parity: {len(p_only)}\n\n")

    report.append("## COMMON Diffs (Entry/SL/TP)\n")
    report.append(f"CSV: `{out_csv}`\n\n")
    if args.include_fills_trades:
        report.append("## Fills/Trades Cross-Check (COMMON)\n")
        report.append("Columns include fills_count_*, fills_reasons_*, trade_present_*, trade_exit_reason_*.\n\n")

    if not cmp_df.empty:
        diff_mask = (
            cmp_df.get("diff_entry_price", False)
            | cmp_df.get("diff_stop_price", False)
            | cmp_df.get("diff_take_profit_price", False)
        )
        diff_rows = cmp_df[diff_mask].copy()
        if not diff_rows.empty:
            report.append("### Top 10 DIFF rows\n")
            view_cols = cols_out[:]
            report.append(diff_rows[view_cols].head(10).to_markdown(index=False))
            report.append("\n\n")

    report.append("## Only in Golden\n")
    report.append(g_only.head(10).to_markdown(index=False) if len(g_only) else "(none)")
    report.append("\n\n")

    report.append("## Only in Parity\n")
    report.append(p_only.head(10).to_markdown(index=False) if len(p_only) else "(none)")
    report.append("\n\n")

    if not cmp_df.empty:
        diff_rows = cmp_df[(cmp_df.get("diff_entry_price", False)) | (cmp_df.get("diff_stop_price", False)) | (cmp_df.get("diff_take_profit_price", False))]
        if not diff_rows.empty:
            report.append("## DBG Evidence (Top 10 DIFF rows)\n")
            cols = [
                key_ts,
                "dbg_mother_high_g","dbg_mother_high_p",
                "dbg_mother_low_g","dbg_mother_low_p",
                "dbg_mother_range_g","dbg_mother_range_p",
                "dbg_breakout_level_g","dbg_breakout_level_p",
                "dbg_inside_ts_g","dbg_inside_ts_p",
                "dbg_mother_ts_g","dbg_mother_ts_p",
                "dbg_trigger_ts_g","dbg_trigger_ts_p",
                "dbg_valid_from_ts_utc_g","dbg_valid_from_ts_utc_p",
                "dbg_valid_to_ts_utc_g","dbg_valid_to_ts_utc_p",
                "dbg_effective_valid_from_policy_g","dbg_effective_valid_from_policy_p",
                "breakout_confirmation_g","breakout_confirmation_p",
                "risk_distance_filtered_g","risk_distance_filtered_p",
            ]
            cols = [c for c in cols if c in diff_rows.columns]
            report.append(diff_rows[cols].head(10).to_markdown(index=False))
            report.append("\n\n")

    out_md.write_text("\n".join(report))
    print("WROTE", out_md)
    print("WROTE", out_csv)


if __name__ == "__main__":
    main()
