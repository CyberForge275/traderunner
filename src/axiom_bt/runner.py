from __future__ import annotations

import argparse
import inspect
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from core.settings import DEFAULT_INITIAL_CASH

from axiom_bt.fs import ensure_layout, new_run_dir
from axiom_bt.metrics import compose_metrics
from axiom_bt.report import save_drawdown_png, save_equity_png


def load_yaml(path: str | Path):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _as_path(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    return Path(path).expanduser()


def _derive_m1_dir(data_path: Path) -> Path | None:
    name = data_path.name.lower()
    if "m5" in name:
        candidate = data_path.with_name(data_path.name.replace("m5", "m1"))
        if candidate.exists():
            return candidate
    if "m15" in name:
        candidate = data_path.with_name(data_path.name.replace("m15", "m1"))
        if candidate.exists():
            return candidate
    sibling = data_path.parent / "data_m1"
    if sibling.exists():
        return sibling
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run backtests from YAML config")
    parser.add_argument("--config", required=True, help="Path to run-config YAML")
    parser.add_argument("--name", default=None, help="Optional run name override")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"[ERROR] config not found: {cfg_path}", file=sys.stderr)
        return 2

    cfg = load_yaml(cfg_path)
    engine = cfg.get("engine", "replay")
    mode = cfg.get("mode", "")

    if engine != "replay":
        print(f"[ERROR] unsupported engine: {engine}", file=sys.stderr)
        return 2
    if mode != "insidebar_intraday":
        print(f"[ERROR] unsupported mode for replay: {mode}", file=sys.stderr)
        return 2

    orders_csv_cfg = cfg.get("orders_source_csv")
    data_cfg = cfg.get("data", {}) or {}
    data_path_cfg = data_cfg.get("path")
    data_path_m1_cfg = data_cfg.get("path_m1")
    tz_value = data_cfg.get("tz", "UTC")

    costs_cfg = cfg.get("costs", {}) or {}
    fees_bps = float(costs_cfg.get("fees_bps", 0.0))
    slippage_bps = float(costs_cfg.get("slippage_bps", 0.0))

    initial_cash = float(cfg.get("initial_cash", DEFAULT_INITIAL_CASH))

    orders_csv = _as_path(orders_csv_cfg)
    data_path = _as_path(data_path_cfg)
    data_path_m1 = _as_path(data_path_m1_cfg)

    if orders_csv is None or data_path is None:
        print("[ERROR] orders_source_csv and data.path are required in config", file=sys.stderr)
        return 2
    if not orders_csv.exists():
        print(f"[ERROR] orders_source_csv not found: {orders_csv}", file=sys.stderr)
        return 2
    if not data_path.exists():
        print(f"[ERROR] data.path not found: {data_path}", file=sys.stderr)
        return 2

    if data_path_m1 is None:
        data_path_m1 = _derive_m1_dir(data_path)

    if data_path_m1 is not None and not data_path_m1.exists():
        data_path_m1 = _derive_m1_dir(data_path)

    from axiom_bt.engines import replay_engine

    simulate_fn = replay_engine.simulate_insidebar_from_orders
    signature = inspect.signature(simulate_fn)
    accepted = set(signature.parameters.keys())

    if hasattr(replay_engine, "Costs"):
        try:
            costs_obj = replay_engine.Costs(fees_bps=fees_bps, slippage_bps=slippage_bps)
        except TypeError:
            costs_obj = replay_engine.Costs(fees_bps, slippage_bps)
    else:
        costs_obj = {"fees_bps": fees_bps, "slippage_bps": slippage_bps}

    kwargs = {}
    if "orders_csv" in accepted:
        kwargs["orders_csv"] = orders_csv
    else:
        print(f"[ERROR] Engine missing 'orders_csv' param. Has: {sorted(accepted)}", file=sys.stderr)
        return 2

    if "data_path" in accepted:
        kwargs["data_path"] = data_path
    else:
        print(f"[ERROR] Engine missing 'data_path' param. Has: {sorted(accepted)}", file=sys.stderr)
        return 2

    if "data_path_m1" in accepted:
        kwargs["data_path_m1"] = data_path_m1

    if "tz" in accepted:
        kwargs["tz"] = tz_value

    if "costs" in accepted:
        kwargs["costs"] = costs_obj

    if "initial_cash" in accepted:
        kwargs["initial_cash"] = initial_cash

    result = simulate_fn(**kwargs)

    ensure_layout()
    run_name = args.name or cfg.get("name", "run")
    run_dir = new_run_dir(run_name)

    manifest = {
        "run_id": run_dir.name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "engine": engine,
        "mode": mode,
        "config": cfg,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    filled = result.get("filled_orders", pd.DataFrame())
    trades = result.get("trades", pd.DataFrame())
    equity = result.get("equity", pd.DataFrame())
    metrics = result.get("metrics", {})

    if isinstance(filled, pd.DataFrame):
        filled.to_csv(run_dir / "filled_orders.csv", index=False)
    if isinstance(trades, pd.DataFrame):
        trades.to_csv(run_dir / "trades.csv", index=False)
    if isinstance(equity, pd.DataFrame):
        equity.to_csv(run_dir / "equity_curve.csv", index=False)
    if "orders" in result and isinstance(result["orders"], pd.DataFrame):
        result["orders"].to_csv(run_dir / "orders.csv", index=False)

    if isinstance(trades, pd.DataFrame) and isinstance(equity, pd.DataFrame):
        metrics = compose_metrics(trades, equity, initial_cash)
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    if isinstance(equity, pd.DataFrame) and not equity.empty:
        save_equity_png(equity, run_dir / "equity_curve.png")
        save_drawdown_png(equity, run_dir / "drawdown_curve.png")

    if isinstance(result, dict):
        result["run_dir"] = str(run_dir)

    print(f"[OK] Backtest artifacts → {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
