"""
Full Backtest Runner - Programmatic API (SSOT for production backtests).

EXTRACTED from axiom_bt/runner.py CLI logic to provide programmatic entry point.
Replaces minimal_backtest_with_gates() for production use.

ARCHITECTURE:
- Reuses existing ReplayEngine simulation
- Returns RunResult (not exit code)
- Enforces execution_mode="full_backtest"
- Writes artifacts_index.json for discovery
- Postcondition gate: equity must exist
"""

import logging
from pathlib import Path
from typing import Dict, Optional, List
import json
import pandas as pd

# Import existing components
from core.settings import DEFAULT_INITIAL_CASH
from axiom_bt.fs import ensure_layout
from axiom_bt.metrics import compose_metrics
from axiom_bt.report import save_drawdown_png, save_equity_png
from axiom_bt.engines import replay_engine

# New pipeline components
from backtest.services.run_status import RunResult, RunStatus, FailureReason
from backtest.services.data_coverage import check_coverage, CoverageStatus
from backtest.services.postcondition_gates import check_equity_postcondition
from backtest.services.artifacts_index import write_artifacts_index
from backtest.services.artifacts_manager import ArtifactsManager
from backtest.services.step_tracker import StepTracker

logger = logging.getLogger(__name__)


def run_backtest_full(
    run_id: str,
    symbol: str,
    timeframe: str,
    requested_end: str,
    lookback_days: int,
    strategy_key: str,
    strategy_params: dict,
    artifacts_root: Path,
    market_tz: str = "America/New_York",
    initial_cash: float = 100000.0,
    costs: Optional[dict] = None,
    orders_source_csv: Optional[Path | str] = None,
    debug_trace: bool = False,
) -> RunResult:
    """
    Full backtest runner - SSOT for production backtests.
    
    Phases:
    1. Coverage Gate (precondition)
    2. Signal Detection → orders.csv generation
    3. Trade Simulation (ReplayEngine)
    4. Equity/orders/trades persistence
    5. Artifacts index generation
    6. Postcondition gate (verify equity exists)
    
    Args:
        run_id: Unique run identifier
        symbol: Stock symbol
        timeframe: M1/M5/M15
        requested_end: End date ISO format
        lookback_days: Lookback in calendar days
        strategy_key: Strategy identifier (e.g., "inside_bar")
        strategy_params: Strategy parameters dict
        artifacts_root: Artifacts directory (e.g., Path("artifacts/backtests"))
        market_tz: Market timezone (default: "America/New_York")
        initial_cash: Initial equity (default: 100000.0)
        costs: Trading costs dict {"fees_bps": 0.0, "slippage_bps": 0.0}
    
    Returns:
        RunResult with status SUCCESS/FAILED_PRECONDITION/FAILED_POSTCONDITION/ERROR
    """
    try:
        # Determine effective debug flag (run-level flag takes precedence
        # but we continue to honour a legacy "debug_trace" entry in
        # strategy_params as a fallback for backwards compatibility).
        param_debug = bool(strategy_params.get("debug_trace", False)) if isinstance(strategy_params, dict) else False
        if param_debug and not debug_trace:
            logger.warning("strategy_params.debug_trace is deprecated; use run-level debug_trace")
        effective_debug = bool(debug_trace or param_debug)

        # Diagnostics payloads (always-on); populated once signal
        # generation data is available and then persisted to
        # diagnostics.json and run_steps.
        data_sanity_payload: Optional[Dict[str, object]] = None
        warmup_payload: Optional[Dict[str, object]] = None
        diagnostics_written = False

        # Optional pre-built orders path (e.g. from dashboard adapter).
        orders_csv_path: Optional[Path] = (
            Path(orders_source_csv) if orders_source_csv is not None else None
        )
        # Initialize artifacts manager
        manager = ArtifactsManager(artifacts_root=artifacts_root)
        
        # Phase 0: Create run directory
        ctx = manager.create_run_dir(run_id)
        run_dir = Path(ctx.run_dir)
        logger.info(f"[{run_id}] Run directory created: {run_dir}")

        # Debug directory for per-run diagnostics (created lazily via
        # helpers, but when effective_debug is enabled we proactively
        # create it so callers can rely on its presence).
        if effective_debug:
            debug_dir = run_dir / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize step tracker
        tracker = StepTracker(run_dir)
        tracker._emit_event(1, "create_run_dir", "completed")
        
        # Phase 0.5: Write run_meta.json via ArtifactsManager so that the
        # manifest writer is initialized and run_manifest.json is produced.
        with tracker.step("write_run_meta"):
            manager.write_run_meta(
                strategy=strategy_key,
                symbols=[symbol],
                timeframe=timeframe,
                params={"execution_mode": "full_backtest", **strategy_params},
                requested_end=requested_end,
                lookback_days=lookback_days,
                commit_hash=None,
                market_tz=market_tz,
                impl_version="1.0.0",
                profile_version="default",
            )
            logger.info(f"[{run_id}] run_meta.json written via ArtifactsManager (execution_mode=full_backtest)")
        
        # Phase 0.7: Ensure Intraday Data (NEW - before coverage gate)
        with tracker.step("ensure_intraday_data") as step:
            logger.info(f"[{run_id}] Ensuring intraday data availability...")
            
            from axiom_bt.intraday import IntradayStore, IntradaySpec, Timeframe
            from datetime import timedelta
            
            # Calculate exact same range as coverage gate
            end_ts = pd.Timestamp(requested_end, tz=market_tz)
            start_ts = (end_ts - pd.Timedelta(days=int(lookback_days))).normalize()
            
            # Convert timeframe string to enum
            tf_enum = Timeframe[timeframe.upper()] if isinstance(timeframe, str) else timeframe
            
            # Create spec
            spec = IntradaySpec(
                symbols=[symbol],
                start=start_ts.date().isoformat(),
                end=end_ts.date().isoformat(),
                timeframe=tf_enum,
                tz=market_tz,
            )
            
            # Call ensure with auto_fill_gaps
            store = IntradayStore(default_tz=market_tz)
            actions = store.ensure(spec, force=False, auto_fill_gaps=True)
            
            logger.info(f"[{run_id}] ensure() actions: {actions}")
            step.add_detail("actions", str(actions))
            step.add_detail("date_range", f"{spec.start} to {spec.end}")
        
        # Phase 1: Coverage Gate
        with tracker.step("coverage_gate") as step:
            logger.info(f"[{run_id}] Running coverage gate...")
            requested_end_ts = pd.Timestamp(requested_end, tz=market_tz)
            
            coverage_result = check_coverage(
                symbol=symbol,
                timeframe=timeframe,
                requested_end=requested_end_ts,
                lookback_days=lookback_days,
                auto_fetch=False
            )
            
            step.add_detail("status", coverage_result.status.value if hasattr(coverage_result.status, 'value') else str(coverage_result.status))
        
        # Write coverage check result
        manager.write_coverage_check_result(coverage_result)
        
        # Check coverage status
        if coverage_result.status == CoverageStatus.GAP_DETECTED:
            logger.warning(f"[{run_id}] Coverage gap detected: {coverage_result.gap}")
            
            tracker.skip_step("signal_detection", "coverage_gate_failed")
            tracker.skip_step("trade_simulation", "coverage_gate_failed")
            tracker.skip_step("write_artifacts", "coverage_gate_failed")
            
            run_result = RunResult(
                run_id=run_id,
                status=RunStatus.FAILED_PRECONDITION,
                reason=FailureReason.DATA_COVERAGE_GAP,
                details=coverage_result.to_dict()
            )
            
            with tracker.step("write_run_result"):
                manager.write_run_result(run_result)
            
            return run_result
        
        logger.info(f"[{run_id}] Coverage sufficient")
        
        # Phase 2: Signal Detection → Orders Generation
        signals_debug_df: Optional[pd.DataFrame] = None
        orders_debug_df: Optional[pd.DataFrame] = None

        with tracker.step("signal_detection") as step:
            logger.info(f"[{run_id}] Preparing orders for trade simulation...")

            # Load intraday data once per run for diagnostics and optional
            # in-process signal generation. This is executed regardless of
            # whether an external orders_source_csv is provided so that
            # diagnostics.json is always available.
            windowed: Optional[pd.DataFrame] = None
            ohlcv: Optional[pd.DataFrame] = None
            try:
                from axiom_bt.intraday import IntradayStore, Timeframe

                store = IntradayStore(default_tz=market_tz)
                tf_enum = Timeframe(timeframe.upper())
                ohlcv = store.load(symbol, timeframe=tf_enum, tz=market_tz)

                end_ts = pd.Timestamp(requested_end, tz=market_tz)
                start_ts = end_ts - pd.Timedelta(days=lookback_days)
                windowed = ohlcv.loc[start_ts:end_ts]
                # Preserve canonical column mapping metadata across the
                # slicing operation for consistent diagnostics.
                windowed.attrs.update(getattr(ohlcv, "attrs", {}))

                data_sanity_payload = _write_data_sanity_report(
                    df=windowed,
                    symbol=symbol,
                    timeframe=timeframe,
                    market_tz=market_tz,
                    strategy_params=strategy_params,
                    run_dir=run_dir,
                    write_debug=effective_debug,
                )
                warmup_payload = _write_warmup_requirements_report(
                    df=ohlcv,
                    symbol=symbol,
                    timeframe=timeframe,
                    requested_end=requested_end,
                    lookback_days=lookback_days,
                    strategy_params=strategy_params,
                    run_dir=run_dir,
                    write_debug=effective_debug,
                )

                if data_sanity_payload is not None and warmup_payload is not None:
                    _write_diagnostics_file(
                        run_dir=run_dir,
                        run_id=run_id,
                        symbol=symbol,
                        strategy_key=strategy_key,
                        timeframe=timeframe,
                        market_tz=market_tz,
                        requested_end=requested_end,
                        lookback_days=lookback_days,
                        data_sanity=data_sanity_payload,
                        warmup=warmup_payload,
                    )
                    diagnostics_written = True

                    with tracker.step("data_sanity") as sanity_step:
                        idx_info = data_sanity_payload.get("index", {})
                        nan_stats = data_sanity_payload.get("nan_stats", {})
                        tf_info = data_sanity_payload.get("timeframe_integrity", {})
                        close_nan = (nan_stats.get("close", {}) or {}).get("pct")

                        sanity_step.add_detail("rows", data_sanity_payload.get("rows"))
                        sanity_step.add_detail("tz", idx_info.get("tz"))
                        sanity_step.add_detail("unique", idx_info.get("unique"))
                        sanity_step.add_detail("monotonic", idx_info.get("monotonic_increasing"))
                        sanity_step.add_detail("nan_pct_close", close_nan)
                        sanity_step.add_detail("expected_step_s", tf_info.get("expected_step_seconds"))
                        sanity_step.add_detail("mode_step_s", tf_info.get("mode_step_seconds"))
                        sanity_step.add_detail("off_step_count", tf_info.get("off_step_count"))

                    with tracker.step("warmup_check") as warm_step:
                        bar_checks = warmup_payload.get("bar_checks", {})
                        warm_step.add_detail("required_warmup_bars", bar_checks.get("required_warmup_bars"))
                        warm_step.add_detail(
                            "available_bars_before_start",
                            bar_checks.get("available_bars_before_start"),
                        )
                        warm_step.add_detail("warmup_ok_bars", bar_checks.get("warmup_ok_bars"))

            except Exception as diag_err:  # pragma: no cover - defensive
                step.add_detail("diagnostics_error", str(diag_err))
                windowed = None
                ohlcv = None

            # If an external orders CSV was provided (e.g. from dashboard
            # adapter using trade.orders_builder), copy it into the run
            # directory as orders.csv so that the replay engine can use it
            # and artifacts remain self-contained.
            if orders_csv_path is not None:
                source_csv = orders_csv_path
                dest_csv = run_dir / "orders.csv"
                try:
                    if source_csv.exists():
                        if source_csv != dest_csv:
                            dest_csv.write_bytes(source_csv.read_bytes())
                        orders_csv_path = dest_csv
                        try:
                            preview = pd.read_csv(dest_csv)
                            step.add_detail("signals_count", int(len(preview)))
                        except Exception as read_err:  # pragma: no cover - defensive
                            step.add_detail("signals_count", "unknown")
                            step.add_detail("orders_read_error", str(read_err))
                    else:
                        logger.warning(f"[{run_id}] Provided orders_source_csv does not exist: {source_csv}")
                        orders_csv_path = dest_csv
                        step.add_detail("signals_count", 0)
                        step.add_detail("note", "orders_source_csv missing; will fall back to flat equity")
                except Exception as copy_err:  # pragma: no cover - defensive
                    logger.error(f"[{run_id}] Failed to prepare orders.csv: {copy_err}")
                    orders_csv_path = run_dir / "orders.csv"
                    step.add_detail("signals_count", 0)
                    step.add_detail("orders_copy_error", str(copy_err))
            else:
                # No external orders file; run strategy-specific signal
                # detection and build orders in-process using the canonical
                # trade.orders_builder wrapper.
                try:
                    from strategies.inside_bar.strategy import InsideBarStrategy
                    from trade.orders_builder import build_orders_for_backtest

                    if windowed is None:
                        raise ValueError("windowed data unavailable for signal generation")

                    strategy_impl = InsideBarStrategy()
                    ib_config = strategy_params.get("strategy_config", strategy_params)
                    input_frame = windowed.reset_index().rename(columns={"timestamp": "timestamp"})

                    # Optional tracer capturing per-candle decisions from
                    # the real strategy pipeline. This keeps debug traces
                    # perfectly aligned with production behaviour.
                    ib_trace_events: List[Dict[str, object]] = []

                    def _ib_tracer(event: Dict[str, object]) -> None:
                        ib_trace_events.append(event)

                    tracer_cb = _ib_tracer if effective_debug and strategy_key == "inside_bar" else None

                    signals = strategy_impl.generate_signals(
                        input_frame,
                        symbol,
                        ib_config,
                        tracer=tracer_cb,
                    )

                    # Persist InsideBar trace based on the exact
                    # strategy decisions taken above.
                    if effective_debug and strategy_key == "inside_bar":
                        _write_inside_bar_debug_trace(
                            events=ib_trace_events,
                            symbol=symbol,
                            timeframe=timeframe,
                            run_dir=run_dir,
                        )

                    # Convert Signal objects to the DataFrame format expected
                    # by build_orders_for_backtest (timestamp/Symbol + entry/SL/TP).
                    rows: List[Dict[str, object]] = []
                    for sig in signals:
                        long_entry = short_entry = sl_long = sl_short = tp_long = tp_short = None
                        side: Optional[str] = None

                        if sig.signal_type == "LONG":
                            long_entry = sig.entry_price
                            sl_long = sig.stop_loss
                            tp_long = sig.take_profit
                            side = "BUY"
                        elif sig.signal_type == "SHORT":
                            short_entry = sig.entry_price
                            sl_short = sig.stop_loss
                            tp_short = sig.take_profit
                            side = "SELL"

                        if long_entry is None and short_entry is None:
                            continue

                        # Normalise timestamp for debug purposes.
                        try:
                            ts_iso = pd.to_datetime(sig.timestamp).isoformat()
                        except Exception:
                            ts_iso = str(sig.timestamp)

                        signal_id = f"{sig.symbol}|{ts_iso}|{side or 'NA'}"

                        rows.append(
                            {
                                "timestamp": ts_iso,
                                "Symbol": sig.symbol,
                                "long_entry": long_entry,
                                "short_entry": short_entry,
                                "sl_long": sl_long,
                                "sl_short": sl_short,
                                "tp_long": tp_long,
                                "tp_short": tp_short,
                                "side": side,
                                "signal_ts": ts_iso,
                                "signal_id": signal_id,
                            }
                        )

                    signals_df = pd.DataFrame(rows)
                    orders_df = build_orders_for_backtest(
                        signals=signals_df,
                        strategy_params=strategy_params,
                        market_tz=market_tz,
                    )

                    orders_csv_local = run_dir / "orders.csv"
                    orders_df.to_csv(orders_csv_local, index=False)
                    orders_csv_path = orders_csv_local

                    # Capture for orders debug if enabled
                    signals_debug_df = signals_df.copy() if not signals_df.empty else signals_df
                    orders_debug_df = orders_df.copy() if not orders_df.empty else orders_df

                    step.add_detail("signals_count", int(len(signals_df)))
                    step.add_detail("orders_count", int(len(orders_df)))
                except Exception as build_err:  # pragma: no cover - defensive
                    logger.error(f"[{run_id}] Signal detection/orders build failed: {build_err}", exc_info=True)
                    orders_csv_path = run_dir / "orders.csv"
                    step.add_detail("signals_count", 0)
                    step.add_detail("orders_build_error", str(build_err))

        # Orders debug (signal→order mapping) is written after the
        # signal_detection step so that it can see both the signal
        # frame and the resulting orders. This is purely diagnostic
        # and does not affect trading behaviour.
        if effective_debug:
            _write_orders_debug(
                signals_df=signals_debug_df,
                orders_df=orders_debug_df,
                run_dir=run_dir,
                strategy_key=strategy_key,
                strategy_params=strategy_params,
            )
        
        # Phase 3: Trade Simulation (ReplayEngine)
        with tracker.step("trade_simulation") as step:
            logger.info(f"[{run_id}] Running trade simulation...")
            
            # Prepare data paths
            data_path = Path(f"artifacts/data_{timeframe.lower()}/{symbol}.parquet")
            data_path_m1 = Path(f"artifacts/data_m1/{symbol}.parquet")
            
            # Prepare costs
            if costs is None:
                costs_dict = {"fees_bps": 0.0, "slippage_bps": 0.0}
            else:
                costs_dict = costs
            
            # Determine which orders CSV to use for simulation.
            orders_csv = orders_csv_path or (run_dir / "orders.csv")

            # CRITICAL CHECK: If no orders exist, simulation will return empty
            # equity. This is VALID (0 trades scenario) – postcondition logic
            # is responsible for enforcing the equity invariant.
            if not orders_csv.exists():
                logger.warning(f"[{run_id}] No orders.csv - will generate flat equity curve")
                # Create empty orders for clean simulation
                empty_orders = pd.DataFrame(
                    columns=[
                        "valid_from",
                        "valid_to",
                        "symbol",
                        "side",
                        "order_type",
                        "price",
                        "stop_loss",
                        "take_profit",
                    ]
                )
                empty_orders.to_csv(orders_csv, index=False)
            
            # Run simulation
            try:
                sim_result = replay_engine.simulate_insidebar_from_orders(
                    orders_csv=orders_csv,
                    data_path=data_path,
                    data_path_m1=data_path_m1 if data_path_m1.exists() else None,
                    tz=market_tz,
                    costs=costs_dict,
                    initial_cash=initial_cash,
                    requested_end=requested_end,
                )
            except Exception as e:
                logger.error(f"[{run_id}] Simulation failed: {e}", exc_info=True)
                return RunResult(
                    run_id=run_id,
                    status=RunStatus.ERROR,
                    error_id=_generate_error_id(),
                    details={"simulation_error": str(e)}
                )
            
            # Extract results
            equity = sim_result.get("equity", pd.DataFrame())
            filled_orders = sim_result.get("filled_orders", pd.DataFrame())
            trades = sim_result.get("trades", pd.DataFrame())
            metrics = sim_result.get("metrics", {})
            orders = sim_result.get("orders", pd.DataFrame())

            # 0-orders / empty-equity safeguard:
            # If the simulation returns no equity rows (valid case when there
            # are no executable orders), synthesize a flat equity curve so
            # that downstream invariants (equity_curve.csv existence and
            # non-empty content) continue to hold.
            if not isinstance(equity, pd.DataFrame) or equity.empty or "equity" not in equity.columns or "ts" not in equity.columns:
                ts = pd.Timestamp(requested_end, tz=market_tz)
                equity = pd.DataFrame(
                    [
                        {
                            "ts": ts.isoformat(),
                            "equity": float(initial_cash),
                        }
                    ]
                )
            
            step.add_detail("equity_rows", len(equity))
            step.add_detail("fills_count", len(filled_orders))
            step.add_detail("trades_count", len(trades))
        
        # Phase 4: Write Artifacts
        with tracker.step("write_artifacts"):
            logger.info(f"[{run_id}] Writing artifacts...")
            
            # Write equity (required)
            if not equity.empty and "equity" in equity.columns:
                equity_values = pd.to_numeric(equity["equity"], errors="coerce")
                running_max = equity_values.cummax()
                equity["drawdown_pct"] = ((equity_values / running_max) - 1.0) * 100.0
                equity.to_csv(run_dir / "equity_curve.csv", index=False)
                logger.info(f"[{run_id}] Wrote equity_curve.csv ({len(equity)} rows)")
            
            # Write orders
            if not orders.empty:
                orders.to_csv(run_dir / "orders.csv", index=False)
                logger.info(f"[{run_id}] Wrote orders.csv ({len(orders)} rows)")
            
            # Write filled_orders
            if not filled_orders.empty:
                filled_orders.to_csv(run_dir / "filled_orders.csv", index=False)
                logger.info(f"[{run_id}] Wrote filled_orders.csv ({len(filled_orders)} rows)")
            
            # Write trades
            if not trades.empty:
                trades.to_csv(run_dir / "trades.csv", index=False)
                logger.info(f"[{run_id}] Wrote trades.csv ({len(trades)} rows)")
            
            # Write metrics
            if metrics:
                (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
                logger.info(f"[{run_id}] Wrote metrics.json")
            
            # Generate PNGs (optional, don't fail if errors)
            try:
                if not equity.empty:
                    save_equity_png(equity, run_dir / "equity_curve.png")
                    save_drawdown_png(equity, run_dir / "drawdown_curve.png")
                    logger.info(f"[{run_id}] Generated chart PNGs")
            except Exception as e:
                logger.warning(f"[{run_id}] Could not generate chart images: {e}")
        
        # Phase 5: Artifacts Index
        with tracker.step("write_artifacts_index"):
            write_artifacts_index(run_dir)
        
        # Phase 6: Postcondition Gate (verify equity exists)
        with tracker.step("equity_postcondition") as step:
            postcondition = check_equity_postcondition(run_dir, "full_backtest")
            
            step.add_detail("status", postcondition.status)
            step.add_detail("equity_exists", postcondition.equity_file_exists)
            step.add_detail("equity_rows", postcondition.equity_rows)
            
            if postcondition.status == "fail":
                logger.error(f"[{run_id}] Postcondition FAILED: {postcondition.error_message}")
                
                run_result = RunResult(
                    run_id=run_id,
                    status=RunStatus.FAILED_POSTCONDITION,
                    reason=FailureReason.EQUITY_POSTCONDITION_FAILED,
                    details={
                        "postcondition": "equity_verification",
                        "error": postcondition.error_message,
                        "equity_file_exists": postcondition.equity_file_exists
                    }
                )
                
                with tracker.step("write_run_result"):
                    manager.write_run_result(run_result)
                
                return run_result
        
        # Success!
        run_result = RunResult(
            run_id=run_id,
            status=RunStatus.SUCCESS,
            details={
                "equity_rows": postcondition.equity_rows,
                "trades_count": len(trades),
                "coverage": coverage_result.to_dict()
            }
        )
        
        with tracker.step("write_run_result"):
            manager.write_run_result(run_result)
            logger.info(f"[{run_id}] Full backtest completed successfully")
        
        return run_result
    
    except Exception as e:
        # Unhandled exception
        logger.error(f"[{run_id}] Pipeline exception: {e}", exc_info=True)
        
        error_id = _generate_error_id()
        
        run_result = RunResult(
            run_id=run_id,
            status=RunStatus.ERROR,
            error_id=error_id,
            details={
                "exception": str(e),
                "exception_type": type(e).__name__
            }
        )
        
        # Try to write result
        try:
            manager.write_run_result(run_result)
            manager.write_error_stacktrace(e, error_id)
        except Exception:  # pragma: no cover - defensive
            pass

        return run_result

    finally:
        # Ensure diagnostics.json is persisted even if later phases fail,
        # provided the payloads were already computed.
        if (
            not diagnostics_written
            and data_sanity_payload is not None
            and warmup_payload is not None
        ):
            try:
                _write_diagnostics_file(
                    run_dir=run_dir,
                    run_id=run_id,
                    symbol=symbol,
                    strategy_key=strategy_key,
                    timeframe=timeframe,
                    market_tz=market_tz,
                    requested_end=requested_end,
                    lookback_days=lookback_days,
                    data_sanity=data_sanity_payload,
                    warmup=warmup_payload,
                )
            except Exception:  # pragma: no cover - defensive
                pass


def _generate_error_id() -> str:
    """Generate unique error ID for correlation."""
    import secrets
    return secrets.token_hex(6).upper()


def _debug_dir_for(run_dir: Path) -> Path:
    """Return the per-run debug directory, creating it if needed."""

    debug_dir = run_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    return debug_dir


def _write_data_sanity_report(
    df: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    market_tz: str,
    strategy_params: dict,
    run_dir: Path,
    write_debug: bool = False,
) -> Dict[str, object]:
    """Build basic OHLCV sanity diagnostics for the data used in signal-gen.

    The returned payload is used both for always-on diagnostics
    (diagnostics.json) and, when debug is enabled, for detailed debug
    artifacts under ``run_dir/debug``. It has no effect on strategy
    behaviour.
    """
    report: Dict[str, object] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "rows": int(len(df)),
        "market_tz": market_tz,
    }

    # Index properties
    idx_info: Dict[str, object] = {}
    index = df.index
    from pandas import DatetimeIndex

    if isinstance(index, DatetimeIndex):
        idx_info["type"] = "DatetimeIndex"
        idx_info["tz_aware"] = index.tz is not None
        idx_info["tz"] = str(index.tz) if index.tz is not None else None
        idx_info["monotonic_increasing"] = bool(index.is_monotonic_increasing)
        idx_info["unique"] = bool(index.is_unique)
        if len(index) > 0:
            idx_info["start"] = index.min().isoformat()
            idx_info["end"] = index.max().isoformat()
    else:
        idx_info["type"] = type(index).__name__
        idx_info["tz_aware"] = False
        idx_info["monotonic_increasing"] = False
        idx_info["unique"] = False

    report["index"] = idx_info

    # Column presence and basic NaN stats
    required_cols = ["open", "high", "low", "close", "volume"]
    present = [c for c in required_cols if c in df.columns]
    missing = [c for c in required_cols if c not in df.columns]
    report["ohlcv_columns"] = {"present": present, "missing": missing}

    # Capture how this canonical OHLCV view was constructed from the
    # raw source frame. IntradayStore._normalize_ohlcv_frame attaches
    # these attributes; if they are absent we fall back to reporting
    # only the visible columns.
    raw_columns = df.attrs.get("ohlcv_raw_columns") or list(df.columns)
    canonical_columns = df.attrs.get("ohlcv_canonical_columns") or present
    column_mapping = df.attrs.get("ohlcv_column_mapping") or {
        name: name for name in canonical_columns
    }
    report["raw_columns"] = list(raw_columns)
    report["canonical_columns"] = list(canonical_columns)
    report["column_mapping"] = column_mapping

    nan_stats: Dict[str, Dict[str, object]] = {}
    for col in ["open", "high", "low", "close"]:
        if col in df.columns and len(df) > 0:
            nulls = int(df[col].isna().sum())
            pct = float(nulls) / float(len(df)) * 100.0
            nan_stats[col] = {"count": nulls, "pct": pct}
        else:
            nan_stats[col] = {"count": None, "pct": None}
    report["nan_stats"] = nan_stats

    # Timeframe integrity (approximate bar spacing)
    tf_map = {"M1": 60, "M5": 300, "M15": 900}
    expected_step = tf_map.get(timeframe.upper())
    tf_info: Dict[str, object] = {"expected_step_seconds": expected_step}
    if isinstance(index, DatetimeIndex) and len(index) > 1 and expected_step:
        deltas = index.to_series().diff().dropna().dt.total_seconds()
        if not deltas.empty:
            # Mode of step sizes
            vc = deltas.value_counts()
            mode_step = float(vc.idxmax())
            off_step = int((deltas != expected_step).sum())
            tf_info["mode_step_seconds"] = mode_step
            tf_info["off_step_count"] = off_step
            tf_info["samples"] = int(len(deltas))
    report["timeframe_integrity"] = tf_info

    # Duplicate index diagnostics
    dup_info: Dict[str, object] = {"index_duplicates": 0, "duplicate_timestamps": []}
    if isinstance(index, DatetimeIndex) and len(index) > 0:
        dup_mask = index.duplicated(keep="first")
        dup_count = int(dup_mask.sum())
        dup_info["index_duplicates"] = dup_count
        if dup_count > 0:
            dup_info["duplicate_timestamps"] = [ts.isoformat() for ts in index[dup_mask][:10]]
    report["duplicates"] = dup_info

    # Session filter summary (if present in params)
    sess_info: Dict[str, object] = {"active": False}
    session_filter = strategy_params.get("session_filter")
    if session_filter is not None and isinstance(index, DatetimeIndex):
        try:
            from strategies.inside_bar.config import SessionFilter

            if isinstance(session_filter, SessionFilter):
                sess_info["active"] = True
                in_session = 0
                for ts in index:
                    if session_filter.is_in_session(ts):
                        in_session += 1
                sess_info["in_session_rows"] = int(in_session)
                sess_info["out_of_session_rows"] = int(len(index) - in_session)
                sess_info["windows"] = session_filter.to_strings()
        except Exception:  # pragma: no cover - defensive
            sess_info["active"] = False
    report["session_filter"] = sess_info

    if write_debug:
        debug_dir = _debug_dir_for(run_dir)
        out_path = debug_dir / "data_sanity.json"
        out_path.write_text(json.dumps(report, indent=2, default=str))

    return report


def _write_warmup_requirements_report(
    df: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    requested_end: str,
    lookback_days: int,
    strategy_params: dict,
    run_dir: Path,
    write_debug: bool = False,
) -> Dict[str, object]:
    """Build a warmup requirements report for indicator lookback needs."""

    from math import ceil

    atr_period = int(strategy_params.get("atr_period", 14))
    # Future extensions could include EMA/other lookbacks here.
    required_warmup_bars = max(atr_period, 1)

    tf_minutes = {"M1": 1, "M5": 5, "M15": 15}.get(timeframe.upper(), 5)
    bars_per_day = int(6.5 * 60 / tf_minutes) if tf_minutes > 0 else 1
    warmup_days = max(1, ceil(required_warmup_bars / max(bars_per_day, 1)))

    index = df.index
    from pandas import DatetimeIndex

    tz = None
    earliest_ts = None
    latest_ts = None
    if isinstance(index, DatetimeIndex) and len(index) > 0:
        tz = index.tz
        earliest_ts = index.min()
        latest_ts = index.max()

    if tz is None:
        tz = "America/New_York"

    req_end = pd.Timestamp(requested_end, tz=tz)
    requested_start = req_end - pd.Timedelta(days=lookback_days)
    required_start = req_end - pd.Timedelta(days=lookback_days + warmup_days)

    # Bar-based warmup check: count how many bars exist strictly before
    # the requested backtest window.
    available_bars_before_start = 0
    if isinstance(index, DatetimeIndex) and len(index) > 0:
        available_bars_before_start = int((index < requested_start).sum())

    warmup_ok_bars = available_bars_before_start >= required_warmup_bars

    payload: Dict[str, object] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "config": {
            "atr_period": atr_period,
        },
        "required_warmup_bars": required_warmup_bars,
        "bars_per_day_estimate": bars_per_day,
        "warmup_days_estimate": warmup_days,
        "requested_range": {
            "start": requested_start.isoformat(),
            "end": req_end.isoformat(),
            "lookback_days": lookback_days,
        },
        "required_range_with_warmup": {
            "start": required_start.isoformat(),
            "end": req_end.isoformat(),
            "warmup_days": warmup_days,
            "required_warmup_bars": required_warmup_bars,
        },
        "data": {
            "earliest_data": earliest_ts.isoformat() if isinstance(earliest_ts, pd.Timestamp) else None,
            "latest_data": latest_ts.isoformat() if isinstance(latest_ts, pd.Timestamp) else None,
        },
        "bar_checks": {
            "required_warmup_bars": required_warmup_bars,
            "available_bars_before_start": available_bars_before_start,
            "warmup_ok_bars": warmup_ok_bars,
        },
        # Backwards-compatible flag; mirrors the bar-based verdict.
        "warmup_ok": warmup_ok_bars,
    }
    if write_debug:
        debug_dir = _debug_dir_for(run_dir)
        (debug_dir / "warmup_requirements.json").write_text(
            json.dumps(payload, indent=2, default=str)
        )
    return payload


def _write_diagnostics_file(
    *,
    run_dir: Path,
    run_id: str,
    symbol: str,
    strategy_key: str,
    timeframe: str,
    market_tz: str,
    requested_end: str,
    lookback_days: int,
    data_sanity: Dict[str, object],
    warmup: Dict[str, object],
) -> None:
    """Write consolidated always-on diagnostics.json for a backtest run."""

    idx = data_sanity.get("index", {})
    nan_stats = data_sanity.get("nan_stats", {})
    tf_info = data_sanity.get("timeframe_integrity", {})
    dup = data_sanity.get("duplicates", {})
    sess = data_sanity.get("session_filter", {})
    ohlcv_cols = data_sanity.get("ohlcv_columns", {})

    raw_columns = data_sanity.get("raw_columns", [])
    canonical_columns = data_sanity.get("canonical_columns", [])
    column_mapping = data_sanity.get("column_mapping", {})
    missing_required = ohlcv_cols.get("missing", [])

    # Flatten NaN stats into the requested structure.
    nan_payload: Dict[str, object] = {}
    for col in ["open", "high", "low", "close"]:
        stats = nan_stats.get(col, {}) or {}
        nan_payload[f"{col}_nan"] = stats.get("count")
        nan_payload[f"{col}_nan_pct"] = stats.get("pct")

    data_sanity_block = {
        "rows": data_sanity.get("rows"),
        "index": {
            "type": idx.get("type"),
            "tz_aware": idx.get("tz_aware"),
            "tz": idx.get("tz"),
            "monotonic_increasing": idx.get("monotonic_increasing"),
            "unique": idx.get("unique"),
            "start": idx.get("start"),
            "end": idx.get("end"),
        },
        "ohlcv": {
            "raw_columns": raw_columns,
            "canonical_columns": canonical_columns,
            "column_mapping": column_mapping,
            "missing_required": missing_required,
        },
        "nan": nan_payload,
        "timeframe_integrity": {
            "expected_step_seconds": tf_info.get("expected_step_seconds"),
            "mode_step_seconds": tf_info.get("mode_step_seconds"),
            "off_step_count": tf_info.get("off_step_count"),
        },
        "duplicates": {
            "duplicate_index_count": dup.get("index_duplicates"),
            "duplicate_index_samples": dup.get("duplicate_timestamps", []),
        },
        "session_filter": {
            "enabled": bool(sess.get("active")),
            "rows_in_session": sess.get("in_session_rows"),
            "rows_out_of_session": sess.get("out_of_session_rows"),
        },
    }

    warm_cfg = warmup.get("config", {})
    warm_req = warmup.get("required_range_with_warmup", {})
    warm_req_range = warmup.get("requested_range", {})
    bar_checks = warmup.get("bar_checks", {})

    warm_block = {
        "atr_period": warm_cfg.get("atr_period"),
        "required_warmup_bars": warmup.get("required_warmup_bars")
        or warm_req.get("required_warmup_bars"),
        "bars_per_day_estimate": warmup.get("bars_per_day_estimate"),
        "warmup_days_estimate": warmup.get("warmup_days_estimate"),
        "requested_range": {
            "start": warm_req_range.get("start"),
            "end": warm_req_range.get("end"),
        },
        "required_range_with_warmup": {
            "start": warm_req.get("start"),
            "end": warm_req.get("end"),
        },
        "bar_checks": {
            "available_bars_before_start": bar_checks.get(
                "available_bars_before_start"
            ),
            "warmup_ok_bars": bar_checks.get("warmup_ok_bars"),
        },
    }

    diagnostics = {
        "run_id": run_id,
        "symbol": symbol,
        "strategy_key": strategy_key,
        "timeframe": timeframe,
        "market_tz": market_tz,
        "requested_end": requested_end,
        "lookback_days": lookback_days,
        "data_sanity": data_sanity_block,
        "warmup": warm_block,
    }

    (run_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, default=str)
    )


def _write_inside_bar_debug_trace(
    *,
    events: List[Dict[str, object]],
    symbol: str,
    timeframe: str,
    run_dir: Path,
) -> None:
    """Write InsideBar trace and summary based on real strategy events.

    The ``events`` sequence is produced by instrumentation inside
    :class:`InsideBarCore` and therefore reflects the exact decisions
    taken during signal generation.
    """

    debug_dir = _debug_dir_for(run_dir)

    trace_path = debug_dir / "inside_bar_trace.jsonl"
    with trace_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, default=str) + "\n")

    # Build a compact summary for high-level inspection.
    if not events:
        summary = {
            "symbol": symbol,
            "timeframe": timeframe,
            "rows": 0,
            "inside_bar_candidates": 0,
            "patterns_signaled": 0,
            "signals_emitted": 0,
            "top_reject_reasons": [
                {"reason": "no_inside_bars", "count": 1},
            ],
            "evaluation_window": {"start": None, "end": None},
        }
        (debug_dir / "inside_bar_summary.json").write_text(
            json.dumps(summary, indent=2, default=str)
        )
        return

    # Derive row count from the highest row_index we have seen.
    row_indices = [int(e["row_index"]) for e in events if "row_index" in e]
    rows = (max(row_indices) + 1) if row_indices else len(events)

    inside_candidates = sum(1 for e in events if bool(e.get("is_inside_bar")))

    pattern_ids_with_signals = {
        int(e["breakout_from_pattern_index"])
        for e in events
        if e.get("signal_emitted") and e.get("breakout_from_pattern_index") is not None
    }
    patterns_signaled = len(pattern_ids_with_signals)
    signals_emitted = sum(1 for e in events if e.get("signal_emitted"))

    # Aggregate reject reasons for non-signalling candles.
    reason_counts: Dict[str, int] = {}
    for e in events:
        if e.get("signal_emitted"):
            continue
        reason = e.get("reject_reason")
        if not reason:
            continue
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

    top_reject_reasons = [
        {"reason": r, "count": c}
        for r, c in sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # Preserve the original "no_inside_bars" category for compatibility.
    if inside_candidates == 0:
        top_reject_reasons.insert(0, {"reason": "no_inside_bars", "count": 1})

    summary = {
        "symbol": symbol,
        "timeframe": timeframe,
        "rows": int(rows),
        "inside_bar_candidates": int(inside_candidates),
        "patterns_signaled": int(patterns_signaled),
        "signals_emitted": int(signals_emitted),
        "top_reject_reasons": top_reject_reasons,
        "evaluation_window": {
            "start": events[0].get("timestamp"),
            "end": events[-1].get("timestamp"),
        },
    }

    (debug_dir / "inside_bar_summary.json").write_text(
        json.dumps(summary, indent=2, default=str)
    )


def _write_orders_debug(
    *,
    signals_df: Optional[pd.DataFrame],
    orders_df: Optional[pd.DataFrame],
    run_dir: Path,
    strategy_key: str,
    strategy_params: dict,
) -> None:
    """Write per-signal → order mapping diagnostics.

    This helper is intentionally tolerant: if either DataFrame is
    missing it still writes a small report explaining the situation.
    """

    debug_dir = _debug_dir_for(run_dir)
    debug_path = debug_dir / "orders_debug.jsonl"

    with debug_path.open("w", encoding="utf-8") as f:
        if signals_df is None or signals_df.empty:
            event = {
                "note": "no_signals_frame_available",
                "strategy_key": strategy_key,
                "orders_total": int(len(orders_df)) if orders_df is not None else 0,
            }
            f.write(json.dumps(event) + "\n")
            return

        orders_df = orders_df if orders_df is not None else pd.DataFrame()

        # Normalise order timestamps once for efficient matching.
        if not orders_df.empty:
            ts_source = None
            for col in ("valid_from", "ts", "timestamp"):
                if col in orders_df.columns:
                    ts_source = col
                    break
            if ts_source is not None:
                orders_df = orders_df.copy()
                orders_df["_debug_ts"] = pd.to_datetime(
                    orders_df[ts_source], errors="coerce", utc=True
                )
            else:
                orders_df["_debug_ts"] = pd.NaT

        for _, sig in signals_df.iterrows():
            symbol = sig.get("Symbol") or sig.get("symbol")
            raw_ts = sig.get("signal_ts") or sig.get("timestamp") or sig.get("ts")
            raw_side = sig.get("side")

            # Infer side from entry columns if not explicitly present.
            if not raw_side:
                long_entry = sig.get("long_entry")
                short_entry = sig.get("short_entry")
                if pd.notna(long_entry):
                    raw_side = "BUY"
                elif pd.notna(short_entry):
                    raw_side = "SELL"

            try:
                sig_ts = pd.to_datetime(raw_ts, errors="coerce", utc=True)
                signal_ts_iso = sig_ts.isoformat() if sig_ts is not None else str(raw_ts)
            except Exception:
                sig_ts = pd.NaT
                signal_ts_iso = str(raw_ts)

            signal_id = f"{symbol}|{signal_ts_iso}|{raw_side or 'NA'}"

            matching = pd.DataFrame()
            if (
                not orders_df.empty
                and symbol is not None
                and "symbol" in orders_df.columns
            ):
                sym_mask = (
                    orders_df["symbol"].astype(str).str.upper()
                    == str(symbol).upper()
                )
                mask = sym_mask
                if "side" in orders_df.columns and raw_side:
                    mask = mask & (
                        orders_df["side"].astype(str).str.upper()
                        == str(raw_side).upper()
                    )
                if "_debug_ts" in orders_df.columns and sig_ts is not pd.NaT:
                    mask = mask & (orders_df["_debug_ts"] == sig_ts)

                matching = orders_df[mask]

            event = {
                "signal_id": signal_id,
                "signal_ts": signal_ts_iso,
                "symbol": symbol,
                "side": raw_side,
                "orders_count": int(len(matching)),
                "qty_sum": float(matching["qty"].sum()) if "qty" in matching.columns and not matching.empty else 0.0,
                "strategy_key": strategy_key,
                "sizing_mode": strategy_params.get("sizing", "risk"),
                "risk_pct": float(strategy_params.get("risk_pct", 1.0)),
            }
            f.write(json.dumps(event, default=str) + "\n")
