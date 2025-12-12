"""
InsideBar Strategy Profiles
============================

Metadata profiles for InsideBar strategy (v1 and v2).
"""

from strategies.metadata.schema import (
    StrategyMetadata,
    StrategyCapabilities,
    DataRequirements,
    DeploymentInfo,
    DeploymentStatus,
    DeploymentEnvironment,
)
from datetime import datetime


# InsideBar v1 (Original)
INSIDE_BAR_V1_PROFILE = StrategyMetadata(
    # Identity
    strategy_id="insidebar_intraday",
    canonical_name="inside_bar",
    display_name="Inside Bar Intraday",
    version="1.0.0",
    description="Original inside bar pattern strategy with ATR-based breakouts and risk management",
    
    # Capabilities
    capabilities=StrategyCapabilities(
        supports_live_trading=True,
        supports_backtest=True,
        supports_pre_papertrade=True,
        requires_two_stage_pipeline=False,
        generates_long_signals=True,
        generates_short_signals=False,
        generates_exit_signals=True,
        supports_market_orders=True,
        supports_limit_orders=False,
        supports_stop_orders=True,
        supports_position_sizing=True,
        supports_portfolio_mode=False,
    ),
    
    # Data Requirements
    data_requirements=DataRequirements(
        required_timeframes=["M5"],
        requires_intraday=True,
        requires_daily=False,
        requires_universe=False,
        min_history_days=30,  # Need 30 days for ATR calculation
        requires_market_data_db=True,
        requires_signals_db=False,
    ),
    
    # Configuration
    config_class_path="strategies.inside_bar.core.InsideBarConfig",
    default_parameters={
        "atr_period": 14,
        "risk_reward_ratio": 2.0,
        "min_mother_bar_size": 0.5,
        "breakout_confirmation": True,
        "inside_bar_mode": "inclusive",
        "lookback_candles": 50,
        "max_pattern_age_candles": 12,
        "max_deviation_atr": 3.0,
    },
    parameter_schema={
        "type": "object",
        "properties": {
            "atr_period": {"type": "integer", "minimum": 1},
            "risk_reward_ratio": {"type": "number", "minimum": 0},
            "min_mother_bar_size": {"type": "number", "minimum": 0},
            "inside_bar_mode": {"type": "string", "enum": ["inclusive", "strict"]},
        },
        "required": ["atr_period", "risk_reward_ratio"],
    },
    
    # Runtime Paths
    signal_module_path="signals.cli_inside_bar",
    core_module_path="strategies.inside_bar.core",
    
    # Dependencies
    required_indicators=["ATR"],
    
    # Deployment
    deployment_info=DeploymentInfo(
        deployed_environments=[
            DeploymentEnvironment.PRE_PAPERTRADE_LAB,
            DeploymentEnvironment.LIVE_TRADING,
        ],
        deployment_status=DeploymentStatus.PRODUCTION,
        deployed_since=datetime(2025, 12, 7, 11, 30),
        deployed_by="mirko",
        git_tag="insidebar-v1.0.0",
deployment_notes="Original implementation, stable and tested",
    ),
    
    #  Metadata
    created_by="migration_from_streamlit_state",
    documentation_url=None,  # TODO: Add docs link
)


# InsideBar v2 (Unified Implementation)
INSIDE_BAR_V2_PROFILE = StrategyMetadata(
    # Identity
    strategy_id="insidebar_intraday_v2",
    canonical_name="inside_bar",
    display_name="Inside Bar Intraday v2",
    version="2.0.0",
    description="Unified inside bar implementation with 100% parity between backtest and live trading",
    
    # Capabilities
    capabilities=StrategyCapabilities(
        supports_live_trading=True,
        supports_backtest=True,
        supports_pre_papertrade=True,
        requires_two_stage_pipeline=False,
        generates_long_signals=True,
        generates_short_signals=False,
        generates_exit_signals=True,
        supports_market_orders=True,
        supports_limit_orders=False,
        supports_stop_orders=True,
        supports_position_sizing=True,
        supports_portfolio_mode=False,
    ),
    
    # Data Requirements
    data_requirements=DataRequirements(
        required_timeframes=["M5"],
        requires_intraday=True,
        requires_daily=False,
        requires_universe=False,
        min_history_days=30,
        requires_market_data_db=True,
        requires_signals_db=False,
    ),
    
    # Configuration
    config_class_path="strategies.inside_bar.core.InsideBarConfig",
    default_parameters={
        "atr_period": 14,
        "risk_reward_ratio": 2.0,
        "min_mother_bar_size": 0.5,
        "breakout_confirmation": True,
        "inside_bar_mode": "inclusive",
        "lookback_candles": 50,
        "max_pattern_age_candles": 12,
        "max_deviation_atr": 3.0,
    },
    parameter_schema={
        "type": "object",
        "properties": {
            "atr_period": {"type": "integer", "minimum": 1},
            "risk_reward_ratio": {"type": "number", "minimum": 0},
            "min_mother_bar_size": {"type": "number", "minimum": 0},
            "inside_bar_mode": {"type": "string", "enum": ["inclusive", "strict"]},
        },
        "required": ["atr_period", "risk_reward_ratio"],
    },
    
    # Runtime Paths
    signal_module_path="signals.cli_inside_bar",
    core_module_path="strategies.inside_bar.core",
    
    # Dependencies
    required_indicators=["ATR"],
    
    # Deployment
    deployment_info=DeploymentInfo(
        deployed_environments=[
            DeploymentEnvironment.PRE_PAPERTRADE_LAB,
            DeploymentEnvironment.LIVE_TRADING,
        ],
        deployment_status=DeploymentStatus.PRODUCTION,
        deployed_since=datetime(2025, 12, 7, 11, 30),
        deployed_by="mirko",
        git_tag="insidebar-v2.0.0",
        checksum="3d565178f137ebdf",
        deployment_notes=(
            "Unified implementation with 23/23 parity tests passing. "
            "Core logic extracted to shared module. "
            "100% identical signals between backtest and live."
        ),
    ),
    
    # Metadata
    created_by="migration_from_config_versions",
    documentation_url=None,  # TODO: Add docs link
)
