"""Backtests tab callbacks - filtering and detail view."""

from __future__ import annotations

from datetime import datetime

from dash import Input, Output, State


def register_backtests_callbacks(app):
    """Register callbacks for the Backtests tab."""

    @app.callback(
        Output("version-pattern-hint", "children"),
        Output("version-pattern-hint", "style"),
        Input("backtests-new-version", "value")
    )
    def validate_version_pattern(new_version):
        """Validate new version input pattern."""
        import re
        
        if not new_version or not new_version.strip():
            return (
                "Pattern: v#.## (e.g., v1.01, v2.00)",
                {"fontSize": "0.75em", "color": "#888", "marginBottom": "8px"}
            )
        
        # Pattern: v followed by number, dot, two-digit number
        pattern = r'^v\d+\.\d{2}$'
        if re.match(pattern, new_version.strip()):
            return (
                "✓ Valid version format",
                {"fontSize": "0.75em", "color": "green", "marginBottom": "8px"}
            )
        else:
            return (
                "❌ Invalid format. Use: v#.## (e.g., v1.01, v2.00)",
                {"fontSize": "0.75em", "color": "red", "marginBottom": "8px"}
            )

    @app.callback(
        Output("backtests-detail", "children"),
        Input("backtests-run-dropdown", "value"),
        Input("backtests-refresh-interval", "n_intervals"),
        # prevent_initial_call removed - allow initial render when dropdown has default value
    )
    def update_backtests_detail(run_name, n_intervals):
        import logging
        from pathlib import Path
        logger = logging.getLogger(__name__)
        
        # Comprehensive logging for evidence/debugging
        logger.info(f"🔍 [backtests_detail] CALLBACK TRIGGERED: run_name={run_name}, n_intervals={n_intervals}")
        
        from ..services.backtest_details_service import BacktestDetailsService
        from ..repositories.backtests import (
            get_backtest_log,
            get_backtest_metrics,
            get_backtest_summary,
            get_backtest_equity,
            get_backtest_orders,
            get_rudometkin_candidates,
        )
        from ..layouts.backtests import create_backtest_detail

        if not run_name:
            logger.info(f"🔍 [backtests_detail] No run_name provided, returning placeholder")
            return create_backtest_detail(None, None, None)

        # Resolve run_dir and check existence
        run_dir = Path("artifacts/backtests") / run_name
        run_dir_exists = run_dir.exists()
        logger.info(f"🔍 [backtests_detail] run_dir={run_dir}, exists={run_dir_exists}")

        # Helper: Normalize steps to dicts (Dash UI boundary - only JSON-serializable types)
        def _step_to_dict(s):
            """Convert RunStep (dataclass/pydantic) to plain dict for Dash serialization."""
            from dataclasses import asdict, is_dataclass
            
            if isinstance(s, dict):
                return s
            if is_dataclass(s):
                # Dataclass: convert datetime objects to ISO strings
                d = asdict(s)
                # Convert datetime to string for JSON compatibility
                if 'timestamp' in d and d['timestamp'] is not None:
                    d['timestamp'] = d['timestamp'].isoformat() if hasattr(d['timestamp'], 'isoformat') else str(d['timestamp'])
                # Rename duration_seconds to duration_s for consistency with layout
                if 'duration_seconds' in d:
                    d['duration_s'] = d.pop('duration_seconds')
                return d
            if hasattr(s, "model_dump"):  # pydantic v2
                return s.model_dump()
            if hasattr(s, "dict"):  # pydantic v1
                return s.dict()
            # Fallback: manual extraction
            return {
                "step_index": getattr(s, "step_index", None),
                "step_name": getattr(s, "step_name", ""),
                "status": getattr(s, "status", ""),
                "timestamp": getattr(s, "timestamp", None),
                "details": getattr(s, "details", None),
                "duration_s": getattr(s, "duration_seconds", getattr(s, "duration_s", None)),
            }

        # Try new-pipeline artifacts first
        details_service = BacktestDetailsService()
        details = details_service.load_summary(run_name)
        steps_raw = details_service.load_steps(run_name)
        
        # Normalize steps to dicts (CRITICAL: Dash requires JSON-serializable data)
        steps = [_step_to_dict(s) for s in (steps_raw or [])]
        
        # Log what we found
        logger.info(f"📊 [backtests_detail] Loaded details: status={details.status}, source={details.source}, symbols={details.symbols}")
        logger.info(f"📝 [backtests_detail] Loaded {len(steps)} steps from run_steps.jsonl")
        if steps_raw:
            logger.info(f"🧪 [backtests_detail] step_type_raw={type(steps_raw[0]).__name__}, step_type_normalized={type(steps[0]).__name__}")

        
        # Discover available files
        found_files = []
        if run_dir_exists:
            found_files = [f.name for f in run_dir.iterdir() if f.is_file()]
            logger.info(f"📂 [backtests_detail] Found files in run_dir: {', '.join(found_files[:10])}{'...' if len(found_files) > 10 else ''}")
        
        # If we have new-pipeline artifacts, use them
        if details.source in ["manifest", "meta+result"]:
            logger.info(f"✅ [backtests_detail] Using new-pipeline artifacts for {run_name}")
            # Create summary dict for create_backtest_detail
            summary = {
                "run_name": run_name,
                "status": details.status.lower(),
                "strategy": details.strategy_key,
                "timeframe": details.requested_tf,
                "symbols": details.symbols,
                "started_at": details.started_at,
                "finished_at": details.finished_at,
                "failure_reason": details.failure_reason,
                "steps": steps,  # Pass steps to detail view
            }
            
            # Still try to load legacy artifacts if they exist
            # (equity, orders, etc. - still valuable even for new runs)
            log_df = get_backtest_log(run_name)  # May be empty
            metrics = get_backtest_metrics(run_name)
            equity_df = get_backtest_equity(run_name)
            orders = get_backtest_orders(run_name)
            rk_df = get_rudometkin_candidates(run_name)
            
            # Log artifact counts for evidence
            equity_rows = len(equity_df) if equity_df is not None and not equity_df.empty else 0
            orders_count = len(orders.get("orders", [])) if orders.get("orders") is not None else 0
            logger.info(f"📈 [backtests_detail] Charts/Artifacts: equity_rows={equity_rows}, orders_count={orders_count}, steps_count={len(steps)}")
            
            return create_backtest_detail(
                run_name,
                log_df,
                metrics,
                summary=summary,
                equity_df=equity_df,
                orders_df=orders.get("orders"),
                fills_df=orders.get("fills"),
                trades_df=orders.get("trades"),
                rk_df=rk_df,
            )
        
        # Fall back to pure legacy if no new artifacts
        logger.info(f"⚠️ [backtests_detail] Falling back to legacy artifacts for {run_name}")
        log_df = get_backtest_log(run_name)
        metrics = get_backtest_metrics(run_name)
        summary = get_backtest_summary(run_name)
        equity_df = get_backtest_equity(run_name)
        orders = get_backtest_orders(run_name)
        rk_df = get_rudometkin_candidates(run_name)

        return create_backtest_detail(
            run_name,
            log_df,
            metrics,
            summary=summary,
            equity_df=equity_df,
            orders_df=orders.get("orders"),
            fills_df=orders.get("fills"),
            trades_df=orders.get("trades"),
            rk_df=rk_df,
        )