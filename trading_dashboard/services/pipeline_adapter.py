"""
Dashboard adapter for the Streamlit pipeline.

This module provides a clean interface to execute backtests using the existing
Streamlit pipeline without importing Streamlit itself.
"""

import sys
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
        """
        try:
            self.progress_callback("Importing pipeline modules...")
            
            # Import after path setup
            from apps.streamlit.pipeline import execute_pipeline
            from apps.streamlit.state import PipelineConfig, FetchConfig, STRATEGY_REGISTRY
            
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
            
            self.progress_callback("Executing backtest pipeline...")
            
            # Execute pipeline - this runs all 4 stages
            effective_run_name = execute_pipeline(pipeline)
            
            return {
                "status": "completed",
                "run_name": effective_run_name,
                "ended_at": datetime.now().isoformat(),
            }
            
        except Exception as e:
            import traceback
            return {
                "status": "failed",
                "error": f"{type(e).__name__}: {str(e)}",
                "traceback": traceback.format_exc(),
                "ended_at": datetime.now().isoformat(),
            }


def create_adapter(progress_callback: Optional[Callable[[str], None]] = None) -> DashboardPipelineAdapter:
    """
    Factory function to create a pipeline adapter.
    
    Args:
        progress_callback: Optional function to call with progress updates
        
    Returns:
        Configured DashboardPipelineAdapter instance
    """
    return DashboardPipelineAdapter(progress_callback)
