"""Pipeline orchestrator (CLI/headless)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from .data_prep import load_bars_snapshot
from .data_fetcher import ensure_and_snapshot_bars, DataFetcherError
from .warmup_calc import warmup_days_from_bars, WarmupError
from .signal_frame_factory import build_signal_frame
from .signals import generate_intent
from .fill_model import generate_fills
from axiom_bt.contracts.signal_frame_contract_v1 import compute_schema_fingerprint
from .execution import execute
from .metrics import compute_and_write_metrics
from .artifacts import write_artifacts

logger = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    """Raised when the pipeline fails."""


def run_pipeline(
    *,
    run_id: str,
    out_dir: Path,
    bars_path: Path,
    strategy_id: str,
    strategy_version: str,
    strategy_params: Dict,
    strategy_meta: Dict,
    compound_enabled: bool,
    compound_equity_basis: str,
    initial_cash: float,
    fees_bps: float,
    slippage_bps: float,
) -> None:
    """End-to-end pipeline orchestrator (headless/CLI).

    Steps:
    1) Validate compound basis and time range inputs.
    2) Build effective config from SSOT (market_tz/session_mode/timeframe_minutes).
    3) Compute warmup (candles→days) and ensure/snapshot bars if missing.
    4) Generate intent → fills → execute (sizing, trades, equity/ledger).
    5) Compute metrics and write artifacts/manifest hashes.
    """
    if compound_equity_basis != "cash_only":
        raise PipelineError("unsupported compound_equity_basis (only cash_only allowed)")
    core = strategy_meta.get("core", {}) if strategy_meta else {}

    requested_end = strategy_params.get("requested_end")
    lookback_days = strategy_params.get("lookback_days")
    if not requested_end or lookback_days is None:
        raise PipelineError("missing requested_end or lookback_days (provide via CLI)")

    timeframe_str = strategy_params.get("timeframe")
    tf_minutes = core.get("timeframe_minutes")
    if tf_minutes is None:
        raise PipelineError("timeframe_minutes missing in strategy core (SSOT)")
    if timeframe_str and tf_minutes != int(tf_minutes):
        tf_minutes = int(tf_minutes)
    if timeframe_str:
        expected_tf = f"M{tf_minutes}" if tf_minutes < 60 else ("H1" if tf_minutes == 60 else None)
        if expected_tf and timeframe_str.upper() != expected_tf:
            raise PipelineError(
                f"timeframe mismatch: CLI {timeframe_str} vs SSOT timeframe_minutes {tf_minutes}"
            )

    market_tz = core.get("session_timezone") or core.get("market_tz")
    if not market_tz:
        raise PipelineError("session_timezone missing in strategy SSOT; add to configs/strategies/<strategy>.yaml")

    session_mode = core.get("session_mode")
    if not session_mode:
        raise PipelineError("session_mode missing in strategy SSOT; add to configs/strategies/<strategy>.yaml")

    # 3) Compute warmup (candles→days) and ensure/snapshot bars if missing.
    # [Analysis Layer]: Calculate the exact number of calendar days needed to satisfy the strategy's warmup requirement, respecting the session mode.
    required_warmup_bars = int(strategy_meta.get("required_warmup_bars", 0))
    try:
        warmup_days = warmup_days_from_bars(required_warmup_bars, int(tf_minutes), session_mode)
    except WarmupError as exc:
        raise PipelineError(str(exc)) from exc

    logger.info(
        "actions: pipeline_effective_config_built strategy_id=%s version=%s market_tz=%s session_mode=%s tf=%s warmup_bars=%s warmup_days=%s",
        strategy_id,
        strategy_version,
        market_tz,
        session_mode,
        timeframe_str,
        required_warmup_bars,
        warmup_days,
    )

    # Bars snapshot: use existing if present, else ensure & snapshot via IntradayStore
    # [Data Layer]: Check if a pre-cached bars file exists; if not, initiate a 'just-in-time' fetch and snapshot process through the DataFetcher.
    snapshot_path = bars_path
    if not snapshot_path.exists():
        logger.info(
            "actions: pipeline_bars_input_missing path=%s", snapshot_path
        )
        try:
            # [Framework Logic]: Orchestrate data fetching, resampling (e.g. M1->M5), and session filtering into a stable, per-run artifact.
            snap_info = ensure_and_snapshot_bars(
                run_dir=out_dir,
                symbol=strategy_params.get("symbol", "UNKNOWN"),
                timeframe=strategy_params.get("timeframe", "M5"),
                requested_end=requested_end,
                lookback_days=int(lookback_days),
                market_tz=market_tz,
                session_mode=session_mode,
                warmup_days=warmup_days,
            )
            snapshot_path = Path(snap_info["exec_path"])
            bars_hash = snap_info["bars_hash"]
            logger.info(
                "actions: bars_snapshot_created symbol=%s timeframe=%s exec_path=%s bars_hash=%s",
                strategy_params.get("symbol", "UNKNOWN"),
                strategy_params.get("timeframe", "M5"),
                snapshot_path,
                bars_hash,
            )
        except DataFetcherError as exc:
            raise PipelineError(f"failed to ensure bars: {exc}") from exc
    # [Data Layer]: Load the validated and snapshotted bars into memory; this marks the 'frozen' state of input data for this specific run.
    bars, bars_hash = load_bars_snapshot(snapshot_path)

    # 4) Generate intent → fills → execute (sizing, trades, equity/ledger).
    # [Strategy Boundary]: Delegate indicator calculation and signal generation to the decoupled strategy plugin via the abstract registry (SoC).
    signals_frame, schema = build_signal_frame(
        bars=bars,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        strategy_params=strategy_params,
    )

    # [Contract Layer]: Validate the strategy-generated signal frame against its versioned schema contract to ensure data integrity before execution.
    schema_fp = compute_schema_fingerprint(schema)
    logger.info(
        "actions: signal_frame_validated strategy_id=%s version=%s schema_hash=%s cols=%d",
        strategy_id,
        strategy_version,
        schema_fp["schema_hash"],
        schema_fp["column_count"],
    )

    # [Framework Layer]: Transform the strategy-specific SignalFrame into a normalized, generic intent stream (events_intent) understood by the execution engine.
    intent_art = generate_intent(signals_frame, strategy_id, strategy_version, {**strategy_params, "symbol": strategy_params.get("symbol")})
    
    # [Engine Layer]: Market Simulation: Match the intent stream against historical bars to generate discrete execution fills (STOP/LIMIT/MARKET).
    fills_art = generate_fills(
        intent_art.events_intent,
        bars,
        order_validity_policy=strategy_params.get("order_validity_policy"),
        session_timezone=strategy_params.get("session_timezone"),
        session_filter=strategy_params.get("session_filter"),
    )
    
    # [Engine Layer]: Portfolio Management: Apply position sizing, risk rules, and derive actual trades, equity curve, and the portfolio ledger.
    # Execution: apply sizing (respecting compound_enabled) and derive trades/equity/ledger
    exec_art = execute(
        fills_art.fills,
        intent_art.events_intent,
        bars,
        initial_cash=initial_cash,
        compound_enabled=compound_enabled,
        order_validity_policy=strategy_params.get("order_validity_policy"),
        session_timezone=strategy_params.get("session_timezone"),
        session_filter=strategy_params.get("session_filter"),
    )

    # 5) Compute metrics and write artifacts/manifest hashes.
    # [Reporting Layer]: Calculate standardized performance metrics and risk ratios from the finalized trade history and equity curve.
    metrics = compute_and_write_metrics(exec_art.trades, exec_art.equity_curve, initial_cash, out_dir / "metrics.json")

    manifest_fields = {
        "run_id": run_id,
        "params": {
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "strategy_params": strategy_params,
            "strategy_meta": strategy_meta,
            "compound_enabled": compound_enabled,
            "compound_equity_basis": compound_equity_basis,
            "initial_cash": initial_cash,
            "fees_bps": fees_bps,
            "slippage_bps": slippage_bps,
        },
        "hashes": {
            "bars_hash": bars_hash,
            "intent_hash": intent_art.intent_hash,
            "fills_hash": fills_art.fills_hash,
        },
        "signal_schema": schema_fp,
        "artifacts_index": [
            "events_intent.csv",
            "fills.csv",
            "trades.csv",
            "metrics.json",
            "equity_curve.csv",
            "portfolio_ledger.csv",
        ],
    }

    result_fields = {
        "run_id": run_id,
        "status": "success",
        "details": {
            "trades": len(exec_art.trades),
            "fills": len(fills_art.fills),
        },
    }

    # [Persistence Layer]: Commit all generated data products and the comprehensive run manifest to disk for auditability and dashboard visualization.
    write_artifacts(
        out_dir,
        signals_frame=intent_art.signals_frame,
        events_intent=intent_art.events_intent,
        fills=fills_art.fills,
        trades=exec_art.trades,
        equity_curve=exec_art.equity_curve,
        ledger=exec_art.portfolio_ledger,
        manifest_fields=manifest_fields,
        result_fields=result_fields,
        metrics=metrics,
    )

    logger.info(
        "actions: pipeline_completed run_id=%s intent_hash=%s fills_hash=%s bars_hash=%s",
        run_id,
        intent_art.intent_hash,
        fills_art.fills_hash,
        bars_hash,
    )
