#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REQUIRED_ARTIFACTS = [
    "run_manifest.json",
    "run_result.json",
    "trades.csv",
    "events_intent.csv",
    "signals_frame.csv",
    "equity_curve.csv",
]


def _now_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def _to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def _flatten(prefix: str, data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in sorted(data.items()):
        full = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            out.update(_flatten(full, value))
        else:
            out[full] = value
    return out


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    path: Path


def discover_runs(artifacts_root: Path, run_glob: str, include_failed: bool) -> list[RunPaths]:
    runs: list[RunPaths] = []
    for path in sorted(artifacts_root.glob(run_glob)):
        if not path.is_dir():
            continue
        rr = path / "run_result.json"
        if not include_failed:
            if not rr.exists():
                continue
            try:
                status = str(json.loads(rr.read_text(encoding="utf-8")).get("status", "")).lower()
                if status != "success":
                    continue
            except Exception:
                continue
        runs.append(RunPaths(run_id=path.name, path=path))
    return runs


def build_inventory(runs: list[RunPaths]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for run in runs:
        row: dict[str, Any] = {"run_id": run.run_id, "run_dir": str(run.path)}
        manifest = run.path / "run_manifest.json"
        result = run.path / "run_result.json"
        params: dict[str, Any] = {}
        status = "UNKNOWN"
        details: Any = None
        if result.exists():
            try:
                rj = json.loads(result.read_text(encoding="utf-8"))
                status = str(rj.get("status", "UNKNOWN"))
                details = rj.get("details")
            except Exception as exc:
                status = f"BAD_RUN_RESULT:{type(exc).__name__}"
        row["status"] = status
        row["details"] = json.dumps(details, ensure_ascii=True) if details is not None else ""

        if manifest.exists():
            try:
                mj = json.loads(manifest.read_text(encoding="utf-8"))
                params = mj.get("params", {}).get("strategy_params", {}) or {}
                row["strategy_id"] = mj.get("params", {}).get("strategy_id")
                row["strategy_version"] = mj.get("params", {}).get("strategy_version")
            except Exception:
                params = {}

        row["symbol"] = params.get("symbol")
        row["timeframe"] = params.get("timeframe")
        row["requested_end"] = params.get("requested_end")
        row["lookback_days"] = params.get("lookback_days")
        row["session_windows"] = json.dumps(params.get("session_windows", []), ensure_ascii=True)
        row["strict_mode"] = params.get("strict_mode")
        row["min_mother_body_fraction"] = params.get("min_mother_body_fraction")
        row["max_mother_body_fraction"] = params.get("max_mother_body_fraction")
        row["regime_filter"] = json.dumps(params.get("regime_filter", {}), ensure_ascii=True)

        missing = [name for name in REQUIRED_ARTIFACTS if not (run.path / name).exists()]
        row["missing_artifacts"] = ",".join(missing)
        for name in REQUIRED_ARTIFACTS:
            row[f"has_{name.replace('.', '_')}"] = int((run.path / name).exists())
        rows.append(row)

    return pd.DataFrame(rows).sort_values("run_id").reset_index(drop=True)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def compute_trade_frame(run: RunPaths) -> tuple[pd.DataFrame, pd.DataFrame]:
    trades = _load_csv(run.path / "trades.csv")
    intents = _load_csv(run.path / "events_intent.csv")
    signals = _load_csv(run.path / "signals_frame.csv")

    if trades.empty:
        return pd.DataFrame(), pd.DataFrame()

    trades = trades.copy()
    trades["run_id"] = run.run_id
    trades["entry_ts"] = _to_utc(trades["entry_ts"])
    trades["exit_ts"] = _to_utc(trades["exit_ts"])
    trades = trades.sort_values(["entry_ts", "template_id"], kind="mergesort").reset_index(drop=True)
    trades["hold_min"] = (trades["exit_ts"] - trades["entry_ts"]).dt.total_seconds() / 60.0
    trades["win"] = trades["net_pnl"] > 0

    if not intents.empty and {"template_id", "signal_ts", "stop_price"}.issubset(intents.columns):
        intents_small = intents[
            [c for c in ["template_id", "signal_ts", "stop_price", "take_profit_price"] if c in intents.columns]
        ].copy()
        intents_small["signal_ts"] = _to_utc(intents_small["signal_ts"])
        trades = trades.merge(intents_small, on="template_id", how="left")
        if "stop_price" in trades.columns:
            trades["risk_per_share"] = (pd.to_numeric(trades["entry_price"], errors="coerce") - pd.to_numeric(trades["stop_price"], errors="coerce")).abs()
            trades["r_multiple"] = trades["net_pnl"] / trades["risk_per_share"].replace(0.0, np.nan)
    else:
        trades["risk_per_share"] = np.nan
        trades["r_multiple"] = np.nan

    if not signals.empty and "timestamp" in signals.columns:
        sig_keep = [c for c in ["timestamp", "adx_14", "mother_body_fraction", "mother_body_ok", "high", "low", "close"] if c in signals.columns]
        sig = signals[sig_keep].copy()
        sig["timestamp"] = _to_utc(sig["timestamp"])
        if "signal_ts" in trades.columns:
            trades = trades.merge(sig, left_on="signal_ts", right_on="timestamp", how="left")

        if {"timestamp", "high", "low"}.issubset(signals.columns):
            bars = signals[["timestamp", "high", "low"]].copy()
            bars["timestamp"] = _to_utc(bars["timestamp"])
            bars = bars.sort_values("timestamp").reset_index(drop=True)
            mfe, mae = [], []
            for _, t in trades.iterrows():
                s = t["entry_ts"]
                e = t["exit_ts"]
                if pd.isna(s) or pd.isna(e):
                    mfe.append(np.nan)
                    mae.append(np.nan)
                    continue
                seg = bars[(bars["timestamp"] >= s) & (bars["timestamp"] <= e)]
                if seg.empty:
                    mfe.append(np.nan)
                    mae.append(np.nan)
                    continue
                entry = float(t["entry_price"])
                if str(t["side"]).upper() == "BUY":
                    mfe_val = float(seg["high"].max() - entry)
                    mae_val = float(entry - seg["low"].min())
                else:
                    mfe_val = float(entry - seg["low"].min())
                    mae_val = float(seg["high"].max() - entry)
                mfe.append(max(mfe_val, 0.0))
                mae.append(max(mae_val, 0.0))
            trades["mfe"] = mfe
            trades["mae"] = mae
        else:
            trades["mfe"] = np.nan
            trades["mae"] = np.nan

    ny = trades["entry_ts"].dt.tz_convert("America/New_York")
    trades["weekday"] = ny.dt.day_name()
    trades["entry_hour"] = ny.dt.hour
    m = ny.dt.hour * 60 + ny.dt.minute
    trades["session_bucket"] = np.select(
        [(m >= 570) & (m < 660), (m >= 660) & (m < 840), (m >= 840) & (m < 930)],
        ["09:30-11:00", "11:00-14:00", "14:00-15:30"],
        default="other",
    )

    return trades, signals


def summarize_run(run_id: str, trades: pd.DataFrame, equity: pd.DataFrame) -> dict[str, Any]:
    gp = trades.loc[trades["net_pnl"] > 0, "net_pnl"].sum()
    gl = -trades.loc[trades["net_pnl"] < 0, "net_pnl"].sum()
    pf = gp / gl if gl > 0 else np.nan
    expectancy = trades["net_pnl"].mean() if not trades.empty else np.nan
    avg_r = trades["r_multiple"].mean(skipna=True)
    med_r = trades["r_multiple"].median(skipna=True)

    eq = equity.copy()
    eq["ts"] = _to_utc(eq["ts"])
    eq = eq.dropna(subset=["ts", "equity"]).sort_values("ts")
    cagr = np.nan
    sharpe = np.nan
    sortino = np.nan
    calmar = np.nan
    max_dd = np.nan
    exposure = np.nan
    if not eq.empty:
        start_eq = float(eq["equity"].iloc[0])
        end_eq = float(eq["equity"].iloc[-1])
        days = max((eq["ts"].iloc[-1] - eq["ts"].iloc[0]).total_seconds() / 86400.0, 1.0)
        years = days / 365.25
        cagr = (end_eq / start_eq) ** (1.0 / years) - 1.0 if start_eq > 0 else np.nan
        rets = eq["equity"].pct_change().dropna()
        if not rets.empty and rets.std(ddof=0) > 0:
            sharpe = np.sqrt(252) * rets.mean() / rets.std(ddof=0)
            neg = rets[rets < 0]
            if not neg.empty and neg.std(ddof=0) > 0:
                sortino = np.sqrt(252) * rets.mean() / neg.std(ddof=0)
        roll_max = eq["equity"].cummax()
        dd = eq["equity"] / roll_max - 1.0
        max_dd = float(dd.min())
        if max_dd < 0 and pd.notna(cagr):
            calmar = cagr / abs(max_dd)
        if "hold_min" in trades.columns:
            exposure = float(trades["hold_min"].sum() / (days * 24 * 60))

    return {
        "run_id": run_id,
        "symbol": str(trades["symbol"].iloc[0]) if "symbol" in trades.columns and not trades.empty else None,
        "trades": int(len(trades)),
        "net_pnl": float(trades["net_pnl"].sum()),
        "winrate": float((trades["net_pnl"] > 0).mean()),
        "profit_factor": float(pf) if pd.notna(pf) else np.nan,
        "expectancy_usd": float(expectancy) if pd.notna(expectancy) else np.nan,
        "expectancy_r": float(avg_r) if pd.notna(avg_r) else np.nan,
        "median_r": float(med_r) if pd.notna(med_r) else np.nan,
        "avg_hold_min": float(trades["hold_min"].mean()) if not trades.empty else np.nan,
        "turnover_qty": float(trades["qty"].abs().sum()) if "qty" in trades.columns else np.nan,
        "mfe_median": float(trades["mfe"].median(skipna=True)) if "mfe" in trades.columns else np.nan,
        "mfe_p90": float(trades["mfe"].quantile(0.9)) if "mfe" in trades.columns else np.nan,
        "mae_median": float(trades["mae"].median(skipna=True)) if "mae" in trades.columns else np.nan,
        "mae_p90": float(trades["mae"].quantile(0.9)) if "mae" in trades.columns else np.nan,
        "sl_pct": float((trades["reason"] == "stop_loss").mean()) if "reason" in trades.columns else np.nan,
        "tp_pct": float((trades["reason"] == "take_profit").mean()) if "reason" in trades.columns else np.nan,
        "session_end_pct": float((trades["reason"] == "session_end").mean()) if "reason" in trades.columns else np.nan,
        "cagr": float(cagr) if pd.notna(cagr) else np.nan,
        "sharpe": float(sharpe) if pd.notna(sharpe) else np.nan,
        "sortino": float(sortino) if pd.notna(sortino) else np.nan,
        "max_dd": float(max_dd) if pd.notna(max_dd) else np.nan,
        "calmar": float(calmar) if pd.notna(calmar) else np.nan,
        "exposure_ratio": float(exposure) if pd.notna(exposure) else np.nan,
    }


def attribution(trades: pd.DataFrame, by: str) -> pd.DataFrame:
    return (
        trades.groupby(by, dropna=False)
        .agg(
            trades=("net_pnl", "size"),
            winrate=("win", "mean"),
            net_pnl=("net_pnl", "sum"),
            expectancy=("net_pnl", "mean"),
            avg_r=("r_multiple", "mean"),
            pf=("net_pnl", lambda x: x[x > 0].sum() / abs(x[x < 0].sum()) if (x < 0).any() else np.nan),
        )
        .reset_index()
        .sort_values("net_pnl", ascending=False)
    )


def rolling_metrics(trades: pd.DataFrame, freq: str) -> pd.DataFrame:
    t = trades.dropna(subset=["entry_ts"]).copy().sort_values("entry_ts")
    t["bucket"] = t["entry_ts"].dt.to_period(freq).astype(str)
    out = (
        t.groupby("bucket")
        .agg(
            trades=("net_pnl", "size"),
            net_pnl=("net_pnl", "sum"),
            winrate=("win", "mean"),
            expectancy=("net_pnl", "mean"),
            pf=("net_pnl", lambda x: x[x > 0].sum() / abs(x[x < 0].sum()) if (x < 0).any() else np.nan),
        )
        .reset_index()
        .sort_values("bucket")
    )
    return out


def sanity_checks(trades: pd.DataFrame) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []
    checks.append({"check": "duplicate_template_id_within_run", "count": int(trades.duplicated(["run_id", "template_id"]).sum())})
    checks.append({"check": "template_id_reused_across_runs", "count": int(trades.duplicated(["template_id"]).sum())})
    checks.append({"check": "entry_after_exit", "count": int((trades["entry_ts"] > trades["exit_ts"]).sum())})
    checks.append({"check": "non_positive_prices", "count": int(((trades["entry_price"] <= 0) | (trades["exit_price"] <= 0)).sum())})
    if "signal_ts" in trades.columns:
        checks.append({"check": "signal_after_entry", "count": int((trades["signal_ts"] > trades["entry_ts"]).sum())})
    return pd.DataFrame(checks)


def draw_plots(out_dir: Path, run_summaries: pd.DataFrame, equity_map: dict[str, pd.DataFrame], rolling: pd.DataFrame, attr_symbol: pd.DataFrame) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(12, 5))
    for run_id, eq in equity_map.items():
        if eq.empty:
            continue
        e = eq.copy()
        e["ts"] = _to_utc(e["ts"])
        e = e.dropna(subset=["ts", "equity"]).sort_values("ts")
        plt.plot(e["ts"], e["equity"], label=run_id, linewidth=1)
    plt.title("Equity Curves")
    plt.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(out_dir / "equity_curves.png", dpi=140)
    plt.close()

    plt.figure(figsize=(10, 4))
    top = attr_symbol.head(15)
    plt.bar(top.iloc[:, 0].astype(str), top["net_pnl"])
    plt.xticks(rotation=45, ha="right")
    plt.title("Net PnL by Symbol")
    plt.tight_layout()
    plt.savefig(out_dir / "attribution_symbol.png", dpi=140)
    plt.close()

    if not rolling.empty:
        plt.figure(figsize=(10, 4))
        plt.plot(rolling["bucket"], rolling["expectancy"], marker="o")
        plt.xticks(rotation=45, ha="right")
        plt.title("Rolling Expectancy")
        plt.tight_layout()
        plt.savefig(out_dir / "rolling_expectancy.png", dpi=140)
        plt.close()

    if "max_dd" in run_summaries.columns:
        plt.figure(figsize=(8, 4))
        plt.bar(run_summaries["run_id"], run_summaries["max_dd"])
        plt.xticks(rotation=60, ha="right", fontsize=7)
        plt.title("Max Drawdown by Run")
        plt.tight_layout()
        plt.savefig(out_dir / "drawdown_by_run.png", dpi=140)
        plt.close()


def write_report(
    report_path: Path,
    inventory: pd.DataFrame,
    summary: pd.DataFrame,
    sanity: pd.DataFrame,
    kpi_aggregate: dict[str, Any],
    r_quantiles: pd.Series,
    hold_quantiles: pd.Series,
    attr_symbol: pd.DataFrame,
    attr_weekday: pd.DataFrame,
    attr_session: pd.DataFrame,
    attr_vol: pd.DataFrame,
    attr_regime: pd.DataFrame,
    rolling_1m: pd.DataFrame,
    split_70_30: pd.DataFrame,
    param_delta_cols: list[str],
    concentration: dict[str, Any],
    fix_list: list[str],
    run_group: str,
    analysis_dir: Path,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# Backtest Audit {datetime.now(UTC).strftime('%Y-%m-%d')} ({run_group})")
    lines.append("")
    lines.append("## Executive Summary")
    if summary.empty:
        lines.append("- No successful runs with required artifacts were available.")
    else:
        total_net = summary["net_pnl"].sum()
        avg_pf = summary["profit_factor"].mean()
        lines.extend(
            [
                f"- Runs analyzed: **{len(summary)}** (successful + required artifacts present).",
                f"- Aggregate net PnL: **{total_net:.2f}**.",
                f"- Mean profit factor across runs: **{avg_pf:.3f}**.",
                f"- Positive net runs: **{int((summary['net_pnl'] > 0).sum())}/{len(summary)}**.",
                "- Edge status: **weak/fragile** if performance is concentrated by symbol/time bucket.",
                f"- Top symbol concentration share: **{concentration.get('top_symbol_share', np.nan):.2%}** of total net.",
                f"- Top 10% trades concentration share: **{concentration.get('top_10pct_trade_share', np.nan):.2%}**.",
                "- Main risk flags: coverage incompleteness, symbol concentration, regime dependence.",
                "- Slippage/fees are included if present in `trades.csv` cost columns.",
                "- Determinism note: all joins sorted by timestamp/template_id, no random sampling used.",
            ]
        )
    lines.append("")
    lines.append("## A) Run Inventory")
    lines.append(inventory.to_markdown(index=False))
    lines.append("")
    lines.append("## B) KPI Board")
    lines.append("### Per Run")
    kpi_cols = [
        "run_id",
        "symbol",
        "trades",
        "net_pnl",
        "profit_factor",
        "winrate",
        "expectancy_usd",
        "expectancy_r",
        "avg_hold_min",
        "max_dd",
        "sharpe",
    ]
    lines.append(summary[kpi_cols].to_markdown(index=False))
    lines.append("")
    lines.append("### Aggregate")
    lines.append(json.dumps(kpi_aggregate, indent=2))
    lines.append("")
    lines.append("## C) Distributions")
    lines.append("### R-Multiple Quantiles")
    lines.append(r_quantiles.to_frame("r_multiple").to_markdown())
    lines.append("")
    lines.append("### Hold Time Quantiles (minutes)")
    lines.append(hold_quantiles.to_frame("hold_min").to_markdown())
    lines.append("")
    lines.append("## D) Attribution / Edge Localisation")
    lines.append("### Symbol")
    lines.append(attr_symbol.head(15).to_markdown(index=False))
    lines.append("")
    lines.append("### Weekday")
    lines.append(attr_weekday.to_markdown(index=False))
    lines.append("")
    lines.append("### Session Bucket")
    lines.append(attr_session.to_markdown(index=False))
    lines.append("")
    lines.append("### Volatility Bucket (ADX proxy)")
    lines.append(attr_vol.to_markdown(index=False))
    lines.append("")
    lines.append("### Regime Bucket")
    lines.append(attr_regime.to_markdown(index=False))
    lines.append("")
    lines.append("## E) Robustness / Drift")
    lines.append("### Rolling 1M (head)")
    lines.append(rolling_1m.head(12).to_markdown(index=False))
    lines.append("")
    lines.append("### Temporal Split 70/30")
    lines.append(split_70_30.to_markdown(index=False))
    lines.append("")
    lines.append("### Concentration")
    lines.append(json.dumps(concentration, indent=2))
    lines.append("")
    lines.append("## F) Sensitivity / Ablation")
    if param_delta_cols:
        lines.append(f"- Detected varying parameter keys across runs: {', '.join(param_delta_cols)}")
    else:
        lines.append("- No strategy-parameter variance detected in analyzed run set (mostly symbol/time-window differences).")
    lines.append("- Full join export: `sensitivity_run_vs_params.csv`.")
    lines.append("")
    lines.append("## G) Forensic Sanity Checks")
    lines.append(sanity.to_markdown(index=False))
    lines.append("")
    lines.append("## Output Artifacts")
    lines.append(f"- Analysis directory: `{analysis_dir}`")
    lines.append("- Core exports: `summary_runs.csv`, `attribution_*.csv`, `rolling_metrics_*.csv`, `sanity_checks.csv`.")
    lines.append("- Plots: `equity_curves.png`, `drawdown_by_run.png`, `rolling_expectancy.png`, `attribution_symbol.png`.")
    lines.append("")
    lines.append("## Run Inventory")
    lines.append("_See section A above._")
    lines.append("")
    lines.append("## Fix List / Data Issues")
    for item in fix_list:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Experiment Specs (next 8)")
    lines.extend(
        [
            "- Hypothesis: Morning window has higher expectancy; change: keep `09:30-11:00` only; gate: +PF with >=150 trades.",
            "- Hypothesis: Afternoon BUY harms edge; change: disable BUY in `14:00-15:30`; gate: net pnl and maxDD improvement.",
            "- Hypothesis: Mother body sweet spot drives edge; change: tighten to `0.72-0.78`; gate: expectancy improvement.",
            "- Hypothesis: ADX mid-high performs better; change: require `adx_14 >= 20`; gate: winrate and PF increase.",
            "- Hypothesis: High ADX + high mother body is noisy; change: cap body at 0.80 when ADX>=30.",
            "- Hypothesis: Stop-loss cluster near session end; change: reduce validity window in afternoon only.",
            "- Hypothesis: Symbol concentration risk; change: cap per-symbol weight in batch selection.",
            "- Hypothesis: Coverage quality bias; change: exclude symbols with recurrent incomplete-day warnings in prefilter.",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Forensic multi-run backtest analyzer")
    parser.add_argument("--artifacts-root", default="/var/lib/trading/artifacts/backtests")
    parser.add_argument("--run-glob", default="260302_*_HB*")
    parser.add_argument("--include-failed", action="store_true")
    parser.add_argument("--run-group", default="harami_hb")
    parser.add_argument("--output-root", default="artifacts/analysis")
    parser.add_argument("--report-path", default="")
    args = parser.parse_args()

    artifacts_root = Path(args.artifacts_root)
    timestamp = _now_tag()
    out_dir = Path(args.output_root) / f"{timestamp}_{args.run_group}"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report_path) if args.report_path else Path("reports") / f"backtest_audit_{datetime.now(UTC).strftime('%Y%m%d')}.md"

    runs = discover_runs(artifacts_root, args.run_glob, include_failed=args.include_failed)
    inventory = build_inventory(runs)
    inventory.to_csv(out_dir / "run_inventory.csv", index=False)

    summaries: list[dict[str, Any]] = []
    all_trades: list[pd.DataFrame] = []
    equity_map: dict[str, pd.DataFrame] = {}
    missing_artifacts_rows: list[dict[str, str]] = []
    param_rows: list[dict[str, Any]] = []

    for run in runs:
        missing = [a for a in REQUIRED_ARTIFACTS if not (run.path / a).exists()]
        if missing:
            missing_artifacts_rows.append({"run_id": run.run_id, "missing": ",".join(missing)})
            continue

        trades, _signals = compute_trade_frame(run)
        equity = _load_csv(run.path / "equity_curve.csv")
        if trades.empty or equity.empty:
            missing_artifacts_rows.append({"run_id": run.run_id, "missing": "empty_trades_or_equity"})
            continue

        summaries.append(summarize_run(run.run_id, trades, equity))
        all_trades.append(trades)
        equity_map[run.run_id] = equity

        manifest = run.path / "run_manifest.json"
        if manifest.exists():
            mj = json.loads(manifest.read_text(encoding="utf-8"))
            p = mj.get("params", {}).get("strategy_params", {}) or {}
            flat = _flatten("", p)
            flat["run_id"] = run.run_id
            param_rows.append(flat)

    summary_df = pd.DataFrame(summaries).sort_values("net_pnl", ascending=False)
    summary_df.to_csv(out_dir / "summary_runs.csv", index=False)

    missing_df = pd.DataFrame(missing_artifacts_rows)
    if not missing_df.empty and "run_id" in missing_df.columns:
        missing_df = missing_df.sort_values("run_id")
    missing_df.to_csv(out_dir / "missing_artifacts.csv", index=False)

    if summary_df.empty:
        sanity = pd.DataFrame([{"check": "no_data", "count": 1}])
        write_report(
            report_path=report_path,
            inventory=inventory,
            summary=summary_df,
            sanity=sanity,
            concentration={},
            fix_list=["No valid runs available for analysis."],
            run_group=args.run_group,
        )
        return 0

    trades_df = pd.concat(all_trades, ignore_index=True).sort_values(["entry_ts", "template_id"], kind="mergesort")
    sanity = sanity_checks(trades_df)
    sanity.to_csv(out_dir / "sanity_checks.csv", index=False)

    # Attribution outputs
    attr_symbol = attribution(trades_df, "symbol")
    attr_weekday = attribution(trades_df, "weekday")
    attr_session = attribution(trades_df, "session_bucket")
    attr_symbol.to_csv(out_dir / "attribution_symbol.csv", index=False)
    attr_weekday.to_csv(out_dir / "attribution_weekday.csv", index=False)
    attr_session.to_csv(out_dir / "attribution_session_bucket.csv", index=False)
    trades_df["adx_bucket"] = pd.cut(trades_df["adx_14"], bins=[-np.inf, 20, 25, 30, np.inf], labels=["<20", "20-25", "25-30", ">=30"])
    attr_vol = attribution(trades_df, "adx_bucket")
    attr_vol.to_csv(out_dir / "attribution_volatility_adx.csv", index=False)
    trades_df["regime_bucket"] = np.where(trades_df["adx_14"] >= 25, "trend", "range_or_transition")
    attr_regime = attribution(trades_df, "regime_bucket")
    attr_regime.to_csv(out_dir / "attribution_regime.csv", index=False)

    # Distributions
    q = trades_df["r_multiple"].quantile([0.1, 0.25, 0.5, 0.75, 0.9])
    hold_q = trades_df["hold_min"].quantile([0.1, 0.25, 0.5, 0.75, 0.9])
    q.rename("r_multiple").to_csv(out_dir / "distribution_r_multiple_quantiles.csv")
    hold_q.rename("hold_min").to_csv(out_dir / "distribution_hold_min_quantiles.csv")
    trades_df[["template_id", "mfe", "mae", "net_pnl"]].to_csv(out_dir / "distribution_mfe_mae.csv", index=False)

    # Rolling robustness
    rolling_1m = rolling_metrics(trades_df, "M")
    rolling_3m = rolling_metrics(trades_df, "Q")
    rolling_1m.to_csv(out_dir / "rolling_metrics_1m.csv", index=False)
    rolling_3m.to_csv(out_dir / "rolling_metrics_3m.csv", index=False)

    # Temporal split (70/30)
    trades_sorted = trades_df.dropna(subset=["entry_ts"]).sort_values("entry_ts")
    cut = int(len(trades_sorted) * 0.7)
    is_df = trades_sorted.iloc[:cut]
    oos_df = trades_sorted.iloc[cut:]
    split_rows = []
    for tag, df in [("in_sample", is_df), ("out_of_sample", oos_df)]:
        gp = df.loc[df["net_pnl"] > 0, "net_pnl"].sum()
        gl = -df.loc[df["net_pnl"] < 0, "net_pnl"].sum()
        split_rows.append(
            {
                "split": tag,
                "trades": len(df),
                "net_pnl": df["net_pnl"].sum(),
                "winrate": (df["net_pnl"] > 0).mean(),
                "expectancy": df["net_pnl"].mean(),
                "pf": gp / gl if gl > 0 else np.nan,
            }
        )
    split_df = pd.DataFrame(split_rows)
    split_df.to_csv(out_dir / "robustness_temporal_split_70_30.csv", index=False)

    # Concentration
    top_trade_n = max(1, int(len(trades_df) * 0.10))
    abs_total = trades_df["net_pnl"].abs().sum()
    top_trade_share = (
        trades_df["net_pnl"].abs().sort_values(ascending=False).head(top_trade_n).sum() / abs_total
        if abs_total > 0
        else np.nan
    )
    by_symbol = trades_df.groupby("symbol")["net_pnl"].sum().abs().sort_values(ascending=False)
    top_symbol_share = by_symbol.iloc[0] / by_symbol.sum() if (not by_symbol.empty and by_symbol.sum() > 0) else np.nan
    concentration = {"top_10pct_trade_share": float(top_trade_share), "top_symbol_share": float(top_symbol_share)}
    pd.DataFrame([concentration]).to_csv(out_dir / "concentration_checks.csv", index=False)

    # Parameter sensitivity (run-level)
    if param_rows:
        params_df = pd.DataFrame(param_rows).sort_values("run_id")
        params_df.to_csv(out_dir / "config_params_flat.csv", index=False)
        sens = summary_df.merge(params_df, on="run_id", how="left")
        sens.to_csv(out_dir / "sensitivity_run_vs_params.csv", index=False)
        varying = []
        for c in params_df.columns:
            if c == "run_id":
                continue
            series_norm = params_df[c].map(
                lambda v: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
            )
            if series_norm.nunique(dropna=False) > 1:
                varying.append(c)
        param_delta_cols = varying
    else:
        param_delta_cols = []

    # Plot outputs
    draw_plots(
        out_dir=out_dir,
        run_summaries=summary_df,
        equity_map=equity_map,
        rolling=rolling_1m,
        attr_symbol=attr_symbol,
    )

    # Run inventory table for report should include only useful columns
    inv_cols = [
        "run_id",
        "status",
        "symbol",
        "timeframe",
        "lookback_days",
        "requested_end",
        "missing_artifacts",
    ]
    inv_report = inventory[inv_cols].copy() if set(inv_cols).issubset(inventory.columns) else inventory.copy()
    fix_list = []
    if not missing_df.empty:
        fix_list.append(f"Runs with missing/empty artifacts: {len(missing_df)} (see missing_artifacts.csv).")
    if int(sanity.loc[sanity["check"] == "signal_after_entry", "count"].sum()) > 0:
        fix_list.append("Detected signal_after_entry violations; review signal/fill ordering.")
    if int(sanity.loc[sanity["check"] == "duplicate_template_id_within_run", "count"].sum()) > 0:
        fix_list.append("Duplicate template_id found within single run.")
    if int(sanity.loc[sanity["check"] == "entry_after_exit", "count"].sum()) > 0:
        fix_list.append("Trades with entry_ts > exit_ts detected.")
    if not fix_list:
        fix_list.append("No structural trade-ordering issues detected in analyzed runs.")

    gp = trades_df.loc[trades_df["net_pnl"] > 0, "net_pnl"].sum()
    gl = -trades_df.loc[trades_df["net_pnl"] < 0, "net_pnl"].sum()
    kpi_aggregate = {
        "trades": int(len(trades_df)),
        "symbols": int(trades_df["symbol"].nunique()) if "symbol" in trades_df.columns else None,
        "net_pnl": float(trades_df["net_pnl"].sum()),
        "winrate": float(trades_df["win"].mean()),
        "expectancy_usd": float(trades_df["net_pnl"].mean()),
        "expectancy_r": float(trades_df["r_multiple"].mean(skipna=True)),
        "profit_factor": float(gp / gl) if gl > 0 else None,
        "avg_hold_min": float(trades_df["hold_min"].mean()),
        "mfe_median": float(trades_df["mfe"].median(skipna=True)),
        "mae_median": float(trades_df["mae"].median(skipna=True)),
    }

    write_report(
        report_path=report_path,
        inventory=inv_report,
        summary=summary_df,
        sanity=sanity,
        kpi_aggregate=kpi_aggregate,
        r_quantiles=q,
        hold_quantiles=hold_q,
        attr_symbol=attr_symbol,
        attr_weekday=attr_weekday,
        attr_session=attr_session,
        attr_vol=attr_vol,
        attr_regime=attr_regime,
        rolling_1m=rolling_1m,
        split_70_30=split_df,
        param_delta_cols=param_delta_cols,
        concentration=concentration,
        fix_list=fix_list,
        run_group=args.run_group,
        analysis_dir=out_dir,
    )

    print(f"analysis_dir={out_dir}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
