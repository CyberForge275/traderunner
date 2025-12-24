"""
Dashboard adapter for the Streamlit pipeline.

This module provides a clean interface to execute backtests using the existing
Streamlit pipeline without importing Streamlit itself.

ENHANCED: Now tracks Strategy Lifecycle metadata (strategy_version, strategy_run)
for compliance with FACTORY_LABS_AND_STRATEGY_LIFECYCLE.md.
"""

import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime

# Add necessary paths
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
APPS_DIR = ROOT / "apps"
STREAMLIT_DIR = APPS_DIR / "streamlit"

# Ensure paths are available for imports
for path in [str(SRC), str(APPS_DIR), str(STREAMLIT_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)


class DashboardPipelineAdapter:
    """
    Adapts the Streamlit pipeline for use in the Dash dashboard.
    
    This adapter:
    - Handles import path setup
    - Removes Streamlit dependencies  
    - Provides progress callbacks for UI updates
    - Returns structured results
    """
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize the adapter.
        
        Args:
            progress_callback: Optional function to call with progress updates
        """
        self.progress_callback = progress_callback or (lambda msg: None)
    
    def execute_backtest(
        self,
        run_name: str,
        strategy: str,
        symbols: List[str],
        timeframe: str,
        start_date: Optional[str],
        end_date: Optional[str],
        config_params: Optional[Dict] = None
    ) -> Dict:
        """
        Execute a backtest using the existing pipeline.
        
        ENHANCED: Now tracks Strategy Lifecycle metadata (Phase 1 integration).
        
        Args:
            run_name: Unique name for this run
            strategy: Strategy name (e.g., 'inside_bar', 'rudometkin')
            symbols: List of stock symbols
            timeframe: Timeframe (e.g., 'M5', 'M15')
            start_date: Start date in ISO format (YYYY-MM-DD)
            end_date: End date in ISO format (YYYY-MM-DD)
            config_params: Optional configuration parameters
            
        Returns:
            Dictionary with:
                - status: 'completed' or 'failed'
                - run_name: Final run name (may differ from input)
                - error: Error message if failed
                - traceback: Full traceback if failed
                - strategy_version_id: ID of strategy version (if metadata succeeded)
                - strategy_run_id: ID of strategy run (if metadata succeeded)
        """
        strategy_version_id = None
        strategy_run_id = None
        
        try:
            self.progress_callback("Importing pipeline modules...")
            
            # Import after path setup
            from apps.streamlit.pipeline import execute_pipeline
            from apps.streamlit.state import PipelineConfig, FetchConfig, STRATEGY_REGISTRY
            
            # Import Strategy Lifecycle metadata repository
            from trading_dashboard.repositories.strategy_metadata import (
                get_repository,
                LifecycleStage,
                LabStage,
            )
            
            self.progress_callback("Loading strategy configuration...")
            
            # Get strategy metadata from Streamlit's STRATEGY_REGISTRY
            strategy_obj = STRATEGY_REGISTRY.get(strategy)
            if not strategy_obj:
                available = list(STRATEGY_REGISTRY.keys())
                raise ValueError(f"Unknown strategy: {strategy}. Available: {available}")
            
            self.progress_callback("Configuring data fetch...")
            
            # Build fetch config
            fetch = FetchConfig(
                symbols=symbols,
                timeframe=timeframe,
                start=start_date,
                end=end_date,
                use_sample=False,
                force_refresh=False,
                data_dir=ROOT / "artifacts" / f"data_{timeframe.lower()}",
                data_dir_m1=ROOT / "artifacts" / "data_m1",
            )
            
            # Build pipeline config - CRITICAL: Merge user params with strategy defaults
            # The strategy.default_payload contains essential fields like mode, engine, costs
            base_config = dict(strategy_obj.default_payload)
            
            # Set orders_source_csv to the correct path:
            # Stage 2 (trade.cli_export_orders) generates current_orders.csv
            # The runner (Stage 3) needs this to perform the backtest simulation
            base_config["orders_source_csv"] = str(ROOT / "artifacts" / "orders" / "current_orders.csv")
            
            # Ensure data paths are set (also done in execute_pipeline but safer here)
            base_config.setdefault("data", {})
            base_config["data"]["path"] = str(ROOT / "artifacts" / f"data_{timeframe.lower()}")
            base_config["data"]["path_m1"] = str(ROOT / "artifacts" / "data_m1")
            
            # Merge user overrides if provided
            if config_params:
                for key, value in config_params.items():
                    if key == "data" and isinstance(value, dict):
                        base_config["data"].update(value)
                    else:
                        base_config[key] = value
            
            pipeline = PipelineConfig(
                run_name=run_name,
                fetch=fetch,
                symbols=symbols,
                strategy=strategy_obj,
                config_path=None,
                config_payload=base_config  # Now includes mode, engine, costs, etc.
            )
            
            # ===== PHASE 1: Strategy Lifecycle Metadata Integration =====
            # Create/resolve strategy_version and strategy_run for tracking
            try:
                self.progress_callback("Registering strategy version...")
                repo = get_repository()
                
                # Resolve strategy version (Phase 1: simple impl_version=1, profile_version=1)
                strategy_version_id = self._resolve_or_create_strategy_version(
                    repo=repo,
                    strategy_name=strategy,
                    config=base_config,
                    symbols=symbols,
                )
                
                # Create strategy_run entry (before execution)
                strategy_run_id = repo.create_strategy_run(
                    strategy_version_id=strategy_version_id,
                    lab_stage=LabStage.BACKTEST,
                    run_type="batch_backtest",
                    environment="dev",  # TODO: detect from settings
                    external_run_id=run_name,
                )
                
                self.progress_callback(f"Metadata tracking: version_id={strategy_version_id}, run_id={strategy_run_id}")
                
            except Exception as meta_err:
                # Don't fail backtest if metadata fails - just log
                print(f"⚠️  Strategy metadata tracking failed: {meta_err}")
                self.progress_callback(f"Warning: Metadata tracking failed ({type(meta_err).__name__})")
            
            self.progress_callback("Executing backtest pipeline...")
            
            # Execute pipeline - this runs all 4 stages
            effective_run_name = execute_pipeline(pipeline)
            
            # ===== Update strategy_run with results =====
            if strategy_run_id:
                try:
                    metrics = self._extract_backtest_metrics(effective_run_name)
                    repo.update_strategy_run_status(
                        run_id=strategy_run_id,
                        status="completed",
                        metrics_json=metrics,
                    )
                except Exception as meta_err:
                    print(f"⚠️  Failed to update strategy_run metrics: {meta_err}")
            
            return {
                "status": "completed",
                "run_name": effective_run_name,
                "ended_at": datetime.now().isoformat(),
                "strategy_version_id": strategy_version_id,
                "strategy_run_id": strategy_run_id,
            }
            
        except Exception as e:
            import traceback
            
            # Update strategy_run status if we created one
            if strategy_run_id:
                try:
                    from trading_dashboard.repositories.strategy_metadata import get_repository
                    repo = get_repository()
                    repo.update_strategy_run_status(
                        run_id=strategy_run_id,
                        status="failed",
                        error_message=f"{type(e).__name__}: {str(e)}",
                    )
                except Exception:
                    pass  # Don't fail on metadata update failure
            
            return {
                "status": "failed",
                "error": f"{type(e).__name__}: {str(e)}",
                "traceback": traceback.format_exc(),
                "ended_at": datetime.now().isoformat(),
                "strategy_version_id": strategy_version_id,
                "strategy_run_id": strategy_run_id,
            }
    
    def _resolve_or_create_strategy_version(
        self,
        repo,
        strategy_name: str,
        config: Dict,
        symbols: List[str],
    ) -> int:
        """
        Resolve or create a strategy_version record.
        
        Phase 1 implementation:
        - impl_version = 1 (hardcoded for now)
        - profile_version = 1 (hardcoded)
        - code_ref_value = Git commit hash (if available) or "unknown"
        
        Args:
            repo: StrategyMetadataRepository instance
            strategy_name: Strategy name (e.g., 'inside_bar')
            config: Strategy configuration dictionary
            symbols: List of symbols being backtested
            
        Returns:
            strategy_version_id
        """
        # Import lifecycle enums
        from trading_dashboard.repositories.strategy_metadata import LifecycleStage
        
        # Phase 1: Simple versioning (TODO: enhance in Phase 2)
        strategy_key = strategy_name  # Could map: inside_bar → insidebar_intraday
        impl_version = 1
        profile_key = "default"
        profile_version = 1
        
        # Try to find existing version
        existing = repo.find_strategy_version(
            strategy_key=strategy_key,
            impl_version=impl_version,
            profile_key=profile_key,
            profile_version=profile_version,
        )
        
        if existing:
            return existing.id
        
        # Create new version
        code_ref_value = self._get_git_commit_hash() or "unknown"
        
        # Extract relevant config for storage (avoid storing huge blobs)
        config_json = {
            "strategy_config": config.get("strategy_config", {}),
            "initial_cash": config.get("initial_cash"),
            "engine": config.get("engine"),
            "mode": config.get("mode"),
        }
        
        version_id = repo.create_strategy_version(
            strategy_key=strategy_key,
            impl_version=impl_version,
            label=f"{strategy_name} v{impl_version}.00 (auto-created)",
            code_ref_value=code_ref_value,
            config_json=config_json,
            profile_key=profile_key,
            profile_version=profile_version,
            lifecycle_stage=LifecycleStage.DRAFT_EXPLORE,  # Start as draft
            universe_key=",".join(sorted(symbols)) if len(symbols) <= 10 else f"{len(symbols)}_symbols",
        )
        
        return version_id
    
    def _get_git_commit_hash(self) -> Optional[str]:
        """
        Get current Git commit hash.
        
        Returns:
            Commit hash (short 8 chars) or None if not in Git repo
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short=8", "HEAD"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    def _extract_backtest_metrics(self, run_name: str) -> Dict:
        """
        Extract backtest metrics from results directory.
        
        Args:
            run_name: Backtest run name (directory name)
            
        Returns:
            Dictionary with metrics
        """
        try:
            run_dir = ROOT / "artifacts" / "backtests" / run_name
            
            # Try to load run_log.json for basic metrics
            run_log_path = run_dir / "run_log.json"
            if run_log_path.exists():
                with open(run_log_path) as f:
                    run_log = json.load(f)
                
                return {
                    "run_name": run_name,
                    "status": run_log.get("status"),
                    "symbols": run_log.get("symbols", []),
                    "timeframe": run_log.get("timeframe"),
                    "strategy": run_log.get("strategy"),
                    # TODO: Extract actual backtest results (trades, P&L, etc.)
                    # from results.csv or summary.json when available
                }
        except Exception as e:
            print(f"⚠️  Failed to extract metrics: {e}")
        
        return {"run_name": run_name}


def create_adapter(progress_callback: Optional[Callable[[str], None]] = None) -> DashboardPipelineAdapter:
    """
    Factory function to create a pipeline adapter.
    
    Args:
        progress_callback: Optional function to call with progress updates
        
    Returns:
        Configured DashboardPipelineAdapter instance
    """
    return DashboardPipelineAdapter(progress_callback)
