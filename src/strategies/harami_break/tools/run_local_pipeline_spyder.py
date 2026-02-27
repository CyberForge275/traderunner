"""Spyder helper: run a local Harami backtest via axiom_bt.pipeline.run_pipeline.

This script executes the same core orchestration stage used by UI backtests
and then exposes artifact DataFrames in the Spyder console namespace.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
from IPython.display import display

REPO_ROOT = Path(__file__).resolve().parents[4]
# Remove competing workspace repo source paths that can shadow traderunner modules.
sys.path = [p for p in sys.path if "marketdata-monorepo/src" not in str(p)]
for p in (str(REPO_ROOT / "src"), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Spyder kernels may already have `trade` loaded from another repo path.
for mod in ("trade.session_windows", "trade"):
    if mod in sys.modules:
        del sys.modules[mod]

from axiom_bt.pipeline.config_resolver import load_base_config, resolve_config
from axiom_bt.pipeline.paths import get_backtest_run_dir
from axiom_bt.pipeline.runner import run_pipeline
from strategies.config.managers.harami_break_manager import HaramiBreakConfigManager

RUN_DIR: Path | None = None
RUN_RESULT: dict | None = None
SIGNALS_DF: pd.DataFrame | None = None
INTENTS_DF: pd.DataFrame | None = None
FILLS_DF: pd.DataFrame | None = None
TRADES_DF: pd.DataFrame | None = None


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


def main() -> int:
    strategy_id = "harami_break_intraday"
    strategy_version = "1.0.0"
    symbol = "HOOD"
    timeframe = "M5"

    end_date = dt.date.today() - dt.timedelta(days=1)
    lookback_days = 30
    requested_end = end_date.isoformat()
    run_id = dt.datetime.now().strftime("spyder_%y%m%d_%H%M%S_harami_pipeline")

    base_config_path = REPO_ROOT / "configs" / "runs" / "backtest_pipeline_defaults.yaml"
    commission_bps, slippage_bps = _load_costs_from_base(base_config_path)

    manager = HaramiBreakConfigManager()
    version_node = manager.get(strategy_version)
    core = dict(version_node.get("core", {}))
    tunable = dict(version_node.get("tunable", {}))

    strategy_params = {
        **core,
        **tunable,
        "strategy_version": strategy_version,
        "symbol": symbol,
        "timeframe": timeframe,
        "requested_end": requested_end,
        "lookback_days": lookback_days,
        "fees_bps": commission_bps,
        "slippage_bps": slippage_bps,
    }

    run_dir = get_backtest_run_dir(run_id)
    bars_path = run_dir / "bars_snapshot.parquet"

    print(
        "Running pipeline:"
        f" run_id={run_id} strategy={strategy_id} version={strategy_version}"
        f" symbol={symbol} timeframe={timeframe} end={requested_end} lookback_days={lookback_days}"
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
        compound_enabled=False,
        compound_equity_basis="cash_only",
        initial_cash=10_000.0,
        fees_bps=commission_bps,
        slippage_bps=slippage_bps,
        base_config_path=base_config_path if base_config_path.exists() else None,
    )

    global RUN_DIR, RUN_RESULT, SIGNALS_DF, INTENTS_DF, FILLS_DF, TRADES_DF
    RUN_DIR = run_dir
    result_path = run_dir / "run_result.json"
    if result_path.exists():
        import json

        RUN_RESULT = json.loads(result_path.read_text(encoding="utf-8"))
    else:
        RUN_RESULT = {}

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
        f"Rows -> signals={len(SIGNALS_DF)} intents={len(INTENTS_DF)} "
        f"fills={len(FILLS_DF)} trades={len(TRADES_DF)}"
    )

    if not SIGNALS_DF.empty:
        print("\n--- SIGNALS (head 10) ---")
        print(SIGNALS_DF.head(10).to_string(index=False))
    if not INTENTS_DF.empty:
        print("\n--- INTENTS (head 10) ---")
        print(INTENTS_DF.head(10).to_string(index=False))
    if not TRADES_DF.empty:
        print("\n--- TRADES (head 10) ---")
        print(TRADES_DF.head(10).to_string(index=False))

    print("\nSpyder variables: RUN_DIR, RUN_RESULT, SIGNALS_DF, INTENTS_DF, FILLS_DF, TRADES_DF")
    display(SIGNALS_DF.head(20))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
