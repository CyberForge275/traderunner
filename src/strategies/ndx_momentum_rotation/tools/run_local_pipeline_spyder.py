"""Spyder helper: run a local NDX Momentum backtest via axiom_bt.pipeline.run_pipeline.

This script executes the same core orchestration stage used by UI backtests
and then exposes artifact DataFrames in the Spyder console namespace.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd
from IPython.display import display

REPO_ROOT = Path(__file__).resolve().parents[4]
for p in (str(REPO_ROOT / "src"), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from axiom_bt.pipeline.config_resolver import load_base_config, resolve_config
from axiom_bt.pipeline.paths import get_backtest_run_dir
from axiom_bt.pipeline.runner import run_pipeline
from strategies.config.managers.ndx_momentum_rotation_manager import (
    NdxMomentumRotationConfigManager,
)

RUN_DIR: Path | None = None
RUN_RESULT: dict | None = None
SIGNALS_DF: pd.DataFrame | None = None
INTENTS_DF: pd.DataFrame | None = None
FILLS_DF: pd.DataFrame | None = None
TRADES_DF: pd.DataFrame | None = None
BARS_SNAPSHOT_DF: pd.DataFrame | None = None
TOP5_SCORES_DF: pd.DataFrame | None = None


def _load_costs_from_base(base_config_path: Path) -> tuple[float, float]:
    base_cfg = load_base_config(base_config_path)
    resolved = resolve_config(base=base_cfg, overrides=None, defaults={})
    costs = resolved.resolved.get("costs", {})
    if "commission_bps" not in costs or "slippage_bps" not in costs:
        raise ValueError(
            "base config missing costs.commission_bps/slippage_bps "
            f"(path={base_config_path})"
        )
    return float(costs["commission_bps"]), float(costs["slippage_bps"])


def _load_daily_universe_frame(parquet_path: Path) -> pd.DataFrame:
    if not parquet_path.exists():
        raise FileNotFoundError(f"daily universe parquet not found: {parquet_path}")

    df = pd.read_parquet(parquet_path)

    # Normalize common provider variants (e.g. Date/Open/High/Low/Close/Volume).
    lower_cols = {c.lower(): c for c in df.columns}
    rename_map: dict[str, str] = {}
    for src, dst in (
        ("date", "timestamp"),
        ("datetime", "timestamp"),
        ("ticker", "symbol"),
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("close", "close"),
        ("volume", "volume"),
    ):
        if src in lower_cols:
            rename_map[lower_cols[src]] = dst
    if rename_map:
        df = df.rename(columns=rename_map)

    # Some EOD exports store symbol in MultiIndex level 0.
    if "symbol" not in df.columns and isinstance(df.index, pd.MultiIndex):
        first_level = df.index.get_level_values(0)
        if first_level.dtype == object:
            df = df.copy()
            df["symbol"] = first_level.astype(str)

    required = ["symbol", "timestamp", "open", "high", "low", "close", "volume"]
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(
            f"daily parquet missing required columns: {', '.join(missing)} "
            f"(path={parquet_path})"
        )

    out = df[required].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    out = out.dropna(subset=["timestamp"]).sort_values(["symbol", "timestamp"])
    return out.reset_index(drop=True)


def _select_top5_roc20(
    daily_df: pd.DataFrame,
    *,
    as_of_date: dt.date,
    min_close: float = 8.0,
    min_avg_volume: float = 500_000.0,
) -> pd.DataFrame:
    as_of_ts = pd.Timestamp(as_of_date).tz_localize("UTC")
    df = daily_df[daily_df["timestamp"] <= as_of_ts].copy()
    if df.empty:
        raise ValueError(f"no daily rows available up to {as_of_date.isoformat()}")

    df = df.sort_values(["symbol", "timestamp"])
    df["roc20"] = (
        df.groupby("symbol", sort=False)["close"].transform(lambda s: (s / s.shift(20)) - 1.0)
    )
    df["avg_volume_20"] = (
        df.groupby("symbol", sort=False)["volume"].transform(lambda s: s.rolling(20).mean())
    )

    latest = (
        df.sort_values("timestamp")
        .groupby("symbol", as_index=False, sort=False)
        .tail(1)
        .reset_index(drop=True)
    )
    filt = latest[
        (latest["close"] >= min_close)
        & (latest["avg_volume_20"] >= min_avg_volume)
        & latest["roc20"].notna()
    ].copy()
    if filt.empty:
        raise ValueError("no symbols passed ROC20 liquidity filter")

    ranked = filt.sort_values(["roc20", "symbol"], ascending=[False, True]).reset_index(drop=True)
    top5 = ranked.head(5).copy()
    if len(top5) < 2:
        raise ValueError("need at least 2 symbols for cross-sectional run")
    return top5[["symbol", "timestamp", "close", "avg_volume_20", "roc20"]]


def _build_snapshot_for_symbols(
    daily_df: pd.DataFrame,
    *,
    symbols: list[str],
    start_date: dt.date,
    end_date: dt.date,
) -> pd.DataFrame:
    start_ts = pd.Timestamp(start_date).tz_localize("UTC")
    end_ts = pd.Timestamp(end_date).tz_localize("UTC")
    out = daily_df[
        daily_df["symbol"].isin(symbols)
        & (daily_df["timestamp"] >= start_ts)
        & (daily_df["timestamp"] <= end_ts)
    ].copy()
    if out.empty:
        raise ValueError("no bars available for selected top5/date window")
    return out.sort_values(["timestamp", "symbol"]).reset_index(drop=True)


def _assemble_strategy_params(
    *,
    core: dict,
    tunable: dict,
    strategy_version: str,
    requested_end: str,
    lookback_days: int,
    commission_bps: float,
    slippage_bps: float,
    symbols: list[str],
) -> dict:
    return {
        **core,
        **tunable,
        "strategy_version": strategy_version,
        "symbol": "NDX100_BUNDLE",
        "symbols": symbols,
        "timeframe": "D1",
        "requested_end": requested_end,
        "lookback_days": lookback_days,
        "fees_bps": commission_bps,
        "slippage_bps": slippage_bps,
        "backtesting": {
            "compound_sizing": True,
            "compound_equity_basis": "cash_only",
        },
    }


def main() -> int:
    strategy_id = "ndx_momentum_rotation"
    strategy_version = "1.0.0"

    end_date = dt.date.today() - dt.timedelta(days=1)
    lookback_days = 365
    start_date = end_date - dt.timedelta(days=lookback_days)
    requested_end = end_date.isoformat()
    run_id = dt.datetime.now().strftime("spyder_%y%m%d_%H%M%S_ndx_rotation")

    base_config_path = REPO_ROOT / "configs" / "runs" / "backtest_pipeline_defaults.yaml"
    commission_bps, slippage_bps = _load_costs_from_base(base_config_path)

    manager = NdxMomentumRotationConfigManager()
    version_node = manager.get(strategy_version)
    core = dict(version_node.get("core", {}))
    tunable = dict(version_node.get("tunable", {}))

    daily_parquet = Path("/var/lib/trading/marketdata/reference/eodhd_daily/stocks_data.parquet")
    daily_df = _load_daily_universe_frame(daily_parquet)
    top5 = _select_top5_roc20(daily_df, as_of_date=end_date)
    symbols = top5["symbol"].astype(str).tolist()
    snapshot_df = _build_snapshot_for_symbols(
        daily_df,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
    )

    strategy_params = _assemble_strategy_params(
        core=core,
        tunable=tunable,
        strategy_version=strategy_version,
        requested_end=requested_end,
        lookback_days=lookback_days,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        symbols=symbols,
    )
    backtesting = strategy_params["backtesting"]
    compound_enabled = bool(backtesting.get("compound_sizing", False))
    compound_equity_basis = str(backtesting.get("compound_equity_basis", "cash_only"))

    run_dir = get_backtest_run_dir(run_id)
    bars_path = run_dir / "bars_snapshot.parquet"
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_df.to_parquet(bars_path, index=False)

    print(
        "Running pipeline:"
        f" run_id={run_id} strategy={strategy_id} version={strategy_version}"
        f" symbols={','.join(symbols)} timeframe=D1 end={requested_end} lookback_days={lookback_days}"
        f" fees_bps={commission_bps} slippage_bps={slippage_bps}"
    )

    run_pipeline(
        run_id=run_id,
        out_dir=run_dir,
        bars_path=bars_path,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        strategy_params=strategy_params,
        strategy_meta={
            "core": core,
            "tunable": tunable,
            "required_warmup_bars": version_node.get("required_warmup_bars", 0),
        },
        compound_enabled=compound_enabled,
        compound_equity_basis=compound_equity_basis,
        initial_cash=10_000.0,
        fees_bps=commission_bps,
        slippage_bps=slippage_bps,
        base_config_path=base_config_path if base_config_path.exists() else None,
    )

    global RUN_DIR, RUN_RESULT, SIGNALS_DF, INTENTS_DF, FILLS_DF, TRADES_DF, BARS_SNAPSHOT_DF, TOP5_SCORES_DF
    RUN_DIR = run_dir
    BARS_SNAPSHOT_DF = snapshot_df
    TOP5_SCORES_DF = top5

    result_path = run_dir / "run_result.json"
    RUN_RESULT = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}

    signals_path = run_dir / "signals_frame.csv"
    intents_path = run_dir / "events_intent.csv"
    fills_path = run_dir / "fills.csv"
    trades_path = run_dir / "trades.csv"
    SIGNALS_DF = pd.read_csv(signals_path) if signals_path.exists() else pd.DataFrame()
    INTENTS_DF = pd.read_csv(intents_path) if intents_path.exists() else pd.DataFrame()
    FILLS_DF = pd.read_csv(fills_path) if fills_path.exists() else pd.DataFrame()
    TRADES_DF = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()

    print(f"\nRun dir: {run_dir}")
    print(f"Run result: {RUN_RESULT}")
    print(
        f"Rows -> bars={len(BARS_SNAPSHOT_DF)} signals={len(SIGNALS_DF)} intents={len(INTENTS_DF)} "
        f"fills={len(FILLS_DF)} trades={len(TRADES_DF)}"
    )

    print("\n--- TOP5 ROC20 ---")
    print(TOP5_SCORES_DF.to_string(index=False))

    if not SIGNALS_DF.empty:
        print("\n--- SIGNALS (head 10) ---")
        print(SIGNALS_DF.head(10).to_string(index=False))

    print(
        "\nSpyder variables: RUN_DIR, RUN_RESULT, BARS_SNAPSHOT_DF, TOP5_SCORES_DF, "
        "SIGNALS_DF, INTENTS_DF, FILLS_DF, TRADES_DF"
    )
    display(SIGNALS_DF.head(20))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
