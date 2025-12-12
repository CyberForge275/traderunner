"""
Rudometkin MOC Strategy Profile
================================

Metadata profile for Rudometkin Market-on-Close strategy.
"""

from strategies.metadata.schema import (
    StrategyMetadata,
    StrategyCapabilities,
    DataRequirements,
    DeploymentInfo,
    DeploymentStatus,
    DeploymentEnvironment,
)


RUDOMETKIN_MOC_PROFILE = StrategyMetadata(
    # Identity
    strategy_id="rudometkin_moc_mode",
    canonical_name="rudometkin_moc",
    display_name="Rudometkin Market-on-Close",
    version="1.0.0",
    description="Mean reversion strategy trading at market close using universe file",
    
    # Capabilities
    capabilities=StrategyCapabilities(
        supports_live_trading=False,  # Not yet migrated to live
        supports_backtest=True,
        supports_pre_papertrade=True,
        requires_two_stage_pipeline=True,  # Uses two-stage fetch → run pipeline
        generates_long_signals=True,
        generates_short_signals=True,  # Long/short strategy
        generates_exit_signals=True,
        supports_market_orders=True,
        supports_limit_orders=False,
        supports_stop_orders=True,
        supports_position_sizing=True,
        supports_portfolio_mode=True,  # Trades multiple symbols
    ),
    
    # Data Requirements
    data_requirements=DataRequirements(
        required_timeframes=["M5"],  # Still uses M5 data
        requires_intraday=True,
        requires_daily=False,
        requires_universe=True,  # CRITICAL: Needs universe file
        min_history_days=30,
        requires_market_data_db=True,
        requires_signals_db=False,
    ),
    
    # Configuration
    config_class_path="strategies.rudometkin_moc.config.RudometkinConfig",
    default_parameters={
        "universe_path": "data/universe/rudometkin.parquet",
        # Add other Rudometkin-specific params here
    },
    parameter_schema={
        "type": "object",
        "properties": {
            "universe_path": {"type": "string"},
        },
        "required": ["universe_path"],
    },
    
    # Runtime Paths
    signal_module_path="signals.cli_rudometkin_moc",
    core_module_path="strategies.rudometkin_moc.core",
    
    # Dependencies
    required_indicators=[],  # Add specific indicators if needed
    
    # Deployment
    deployment_info=DeploymentInfo(
        deployed_environments=[
            DeploymentEnvironment.EXPLORE_LAB,
        ],
        deployment_status=DeploymentStatus.DEVELOPMENT,
        deployed_since=None,
        deployed_by=None,
        git_tag=None,
        deployment_notes=(
            "Strategy exists but not yet fully migrated to unified architecture. "
            "Backtest works, live trading not yet implemented."
        ),
    ),
    
    # Metadata
    created_by="migration_from_streamlit_state",
    documentation_url=None,
)
