"""
StrategyMetadata Schema Definition
===================================

Enterprise-grade metadata schema for trading strategies.

This is the Single Source of Truth for all strategy definitions.
All systems (Dashboard, Backtest, Live, marketdata-stream) MUST use this schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Type
from enum import Enum

from pydantic import BaseModel, Field, validator


class DeploymentStatus(str, Enum):
    """Strategy deployment lifecycle status."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRE_PAPERTRADE = "pre_papertrade"
    PAPER_TRADING = "paper_trading"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class DeploymentEnvironment(str, Enum):
    """Deployment environment types."""
    EXPLORE_LAB = "explore-lab"
    PRE_PAPERTRADE_LAB = "pre-papertrading-lab"
    PAPER_TRADING_LAB = "paper-trading-lab"
    LIVE_TRADING = "live-trading"


@dataclass
class DataRequirements:
    """Data requirements for a strategy."""
    
    required_timeframes: List[str]  # e.g., ["M5", "M15"]
    requires_intraday: bool = True
    requires_daily: bool = False
    requires_universe: bool = False
    min_history_days: int = 30  # Minimum historical data needed
    
    # Optional specific data sources
    requires_market_data_db: bool = True
    requires_signals_db: bool = False
    
    def validate(self) -> None:
        """Validate data requirements."""
        assert self.required_timeframes, "At least one timeframe required"
        assert self.min_history_days > 0, "Min history must be positive"
        
        # Validate timeframe format
        valid_timeframes = {"M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"}
        for tf in self.required_timeframes:
            assert tf in valid_timeframes, f"Invalid timeframe: {tf}"


@dataclass
class StrategyCapabilities:
    """Strategy capabilities and features."""
    
    supports_live_trading: bool
    supports_backtest: bool
    supports_pre_papertrade: bool
    requires_two_stage_pipeline: bool = False
    
    # Signal generation capabilities
    generates_long_signals: bool = True
    generates_short_signals: bool = False
    generates_exit_signals: bool = True
    
    # Execution capabilities
    supports_market_orders: bool = True
    supports_limit_orders: bool = False
    supports_stop_orders: bool = True
    
    # Risk management
    supports_position_sizing: bool = True
    supports_portfolio_mode: bool = False
    
    def validate(self) -> None:
        """Validate capability consistency."""
        # At least one trading mode must be supported
        assert (
            self.supports_live_trading
            or self.supports_backtest
            or self.supports_pre_papertrade
        ), "Strategy must support at least one trading mode"
        
        # At least one signal type
        assert (
            self.generates_long_signals
            or self.generates_short_signals
        ), "Strategy must generate at least long or short signals"


@dataclass
class DeploymentInfo:
    """Deployment information for a strategy."""
    
    deployed_environments: List[DeploymentEnvironment] = field(default_factory=list)
    deployment_status: DeploymentStatus = DeploymentStatus.DEVELOPMENT
    deployed_since: Optional[datetime] = None
    deployed_by: Optional[str] = None
    
    # Version tracking
    git_tag: Optional[str] = None
    checksum: Optional[str] = None
    
    # Notes
    deployment_notes: Optional[str] = None


@dataclass
class StrategyMetadata:
    """
    Single Source of Truth for Strategy Metadata.
    
    This dataclass defines all metadata for a trading strategy.
    ALL systems must use this schema - no duplicate definitions allowed.
    """
    
    # === Identity (REQUIRED) ===
    strategy_id: str
    canonical_name: str
    display_name: str
    version: str
    description: str
    
    # === Capabilities (REQUIRED) ===
    capabilities: StrategyCapabilities
    data_requirements: DataRequirements
    
    # === Configuration (REQUIRED) ===
    config_class_path: str
    default_parameters: Dict[str, Any]
    signal_module_path: str
    core_module_path: str
    
    # === Dependencies (OPTIONAL with defaults) ===
    parameter_schema: Optional[Dict[str, Any]] = None
    required_indicators: List[str] = field(default_factory=list)
    deployment_info: Optional[DeploymentInfo] = None
    
    # === Metadata (AUTO-POPULATED with defaults) ===
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"
    documentation_url: Optional[str] = None
    
    def __post_init__(self):
        """Validation after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """
        Validate strategy metadata.
        
        Raises:
            ValueError: If validation fails
        """
        # Validate ID format (lowercase, underscores only)
        if not self.strategy_id.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                f"Invalid strategy_id: {self.strategy_id}. "
                "Must contain only letters, numbers, underscores, hyphens."
            )
        
        # Validate canonical name (base name without version)
        if not self.canonical_name.replace("_", "").isalnum():
            raise ValueError(
                f"Invalid canonical_name: {self.canonical_name}"
            )
        
        # Validate version (basic semver check)
        version_parts = self.version.split(".")
        if len(version_parts) != 3:
            raise ValueError(
                f"Invalid version: {self.version}. Must be semver (e.g., '2.0.0')"
            )
        
        try:
            for part in version_parts:
                int(part)  # Must be integers
        except ValueError:
            raise ValueError(
                f"Invalid version: {self.version}. Parts must be integers"
            )
        
        # Validate sub-components
        self.capabilities.validate()
        self.data_requirements.validate()
        
        # Validate paths are not empty
        assert self.config_class_path, "config_class_path required"
        assert self.signal_module_path, "signal_module_path required"
        assert self.core_module_path, "core_module_path required"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strategy_id": self.strategy_id,
            "canonical_name": self.canonical_name,
            "display_name": self.display_name,
            "version": self.version,
            "description": self.description,
            "capabilities": self.capabilities.__dict__,
            "data_requirements": self.data_requirements.__dict__,
            "config_class_path": self.config_class_path,
            "default_parameters": self.default_parameters,
            "parameter_schema": self.parameter_schema,
            "signal_module_path": self.signal_module_path,
            "core_module_path": self.core_module_path,
            "required_indicators": self.required_indicators,
            "deployment_info": (
                self.deployment_info.__dict__ if self.deployment_info else None
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "documentation_url": self.documentation_url,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyMetadata":
        """Create from dictionary."""
        # Convert nested objects
        if "capabilities" in data and isinstance(data["capabilities"], dict):
            data["capabilities"] = StrategyCapabilities(**data["capabilities"])
        
        if "data_requirements" in data and isinstance(data["data_requirements"], dict):
            data["data_requirements"] = DataRequirements(**data["data_requirements"])
        
        if "deployment_info" in data and isinstance(data["deployment_info"], dict):
            data["deployment_info"] = DeploymentInfo(**data["deployment_info"])
        
        # Convert datetime strings
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        
        return cls(**data)
    
    def is_compatible_with_environment(self, env: DeploymentEnvironment) -> bool:
        """Check if strategy is compatible with deployment environment."""
        if env == DeploymentEnvironment.EXPLORE_LAB:
            return True  # All strategies can be explored
        
        if env == DeploymentEnvironment.PRE_PAPERTRADE_LAB:
            return self.capabilities.supports_pre_papertrade
        
        if env == DeploymentEnvironment.PAPER_TRADING_LAB:
            return self.capabilities.supports_backtest  # Paper uses backtest engine
        
        if env == DeploymentEnvironment.LIVE_TRADING:
            return self.capabilities.supports_live_trading
        
        return False
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"StrategyMetadata("
            f"id={self.strategy_id}, "
            f"name={self.display_name}, "
            f"version={self.version})"
        )
