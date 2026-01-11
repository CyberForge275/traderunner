"""Callback for dynamic backtest configuration from SSOT registry."""

import logging
from dash import Input, Output, State, html, dcc, ALL, MATCH, no_update
from dash.exceptions import PreventUpdate
from trading_dashboard.config_store.strategy_config_store import StrategyConfigStore
from src.strategies.config.registry import config_manager_registry
from trading_dashboard.strategy_configs.registry import get_registry

logger = logging.getLogger(__name__)


def register_ssot_backtest_config_callback(app):
    """Register callbacks for dynamic SSOT-driven backtest configuration."""

    @app.callback(
        Output("backtests-new-strategy", "options"),
        Input("backtests-new-strategy", "id"),
    )
    def populate_backtest_strategy_dropdown(_):
        """P5.1: Populate strategy dropdown from registry."""
        strategies = config_manager_registry.list_strategies()
        if not strategies:
            logger.warning("actions: ui_backtest_strategies_loaded count=0 msg='No strategies registered'")
            return []
        
        logger.info(f"actions: ui_backtest_strategies_loaded count={len(strategies)}")
        return [{"label": sid.replace("_", " ").title(), "value": sid} for sid in sorted(strategies)]

    @app.callback(
        [
            Output("backtests-new-version", "options"),
            Output("backtests-new-version", "value")
        ],
        Input("backtests-new-strategy", "value"),
        prevent_initial_call=False
    )
    def update_backtest_version_dropdown(strategy_id):
        """P5.2: Update version dropdown based on selected strategy."""
        if not strategy_id:
            return [], None
        
        try:
            manager = config_manager_registry.get_manager(strategy_id)
            if not manager:
                logger.error(f"actions: ui_backtest_versions_failed strategy_id={strategy_id} msg='Unregistered strategy'")
                return [], None
            
            config = manager.load()
            versions = list(config.get("versions", {}).keys())
            sorted_versions = sorted(versions, reverse=True)
            
            options = [{"label": v, "value": v} for v in sorted_versions]
            default_value = sorted_versions[0] if sorted_versions else None
            
            return options, default_value
            
        except Exception as e:
            logger.error(f"actions: ui_backtest_versions_failed strategy_id={strategy_id} exc={type(e).__name__} msg='{str(e)}'")
            return [], None

    @app.callback(
        [
            Output("strategy-config-container", "children"),
            Output("bt-config-store", "data"),
        ],
        [
            Input("backtests-new-strategy", "value"),
            Input("backtests-new-version", "value"),
        ],
        prevent_initial_call=True
    )
    def render_backtest_params(strategy_id, version):
        """P5.3: Render parameter fields dynamically and store snapshot."""
        if not strategy_id:
            return [], None
        
        # 1. Try SSOT Manager Registry first (Dynamic Rendering)
        manager = config_manager_registry.get_manager(strategy_id)
        if manager:
            if not version:
                return [html.Div("Select version to load parameters", style={"color": "#888"})], None
                
            try:
                # Fetch defaults and specs from SSOT
                defaults = StrategyConfigStore.get_defaults(strategy_id, version)
                
                # Combination into layout
                layout = [
                    html.Div([
                        html.Span("ℹ️ ", style={"fontSize": "1.2em", "marginRight": "8px"}),
                        html.Span("Parameters are managed in the SSOT Config Viewer below.", style={"color": "#888", "fontSize": "0.9em"})
                    ], style={
                        "padding": "12px",
                        "backgroundColor": "rgba(255,255,255,0.03)",
                        "borderRadius": "4px",
                        "border": "1px solid rgba(255,255,255,0.1)",
                        "marginBottom": "15px"
                    })
                ]
                
                # Summary log
                core_count = len(defaults.get("core", {}))
                tunable_count = len(defaults.get("tunable", {}))
                logger.info(
                    f"actions: ui_field_specs_loaded strategy_id={strategy_id} version={version} "
                    f"core_fields={core_count} tunable_fields={tunable_count}"
                )
                
                # Prepare snapshot for store
                snapshot = {
                    "strategy_id": strategy_id,
                    "version": version,
                    "required_warmup_bars": defaults.get("required_warmup_bars", 0),
                    "core": defaults.get("core", {}),
                    "tunable": defaults.get("tunable", {}),
                    "strategy_finalized": defaults.get("strategy_finalized", False)
                }
                
                return layout, snapshot
                
            except Exception as e:
                logger.error(f"actions: ui_backtest_params_failed strategy_id={strategy_id} version={version} exc={type(e).__name__} msg='{str(e)}'")
                return [html.Div(f"Error loading parameters: {str(e)}", style={"color": "red"})], None

        # 2. Fallback to Legacy Plugin Registry
        legacy_registry = get_registry()
        if legacy_registry.has_custom_config(strategy_id):
            logger.info(f"actions: ui_backtest_params_legacy strategy_id={strategy_id}")
            return legacy_registry.render_config_for_strategy(strategy_id), None
            
        return [html.Div(f"No configuration found for {strategy_id}", style={"color": "#888"})], None
