"""
Unit Tests for StrategyMetadata Schema
======================================

Tests all validation rules, serialization, and edge cases.
"""

import pytest
from datetime import datetime
from src.strategies.metadata.schema import (
    StrategyMetadata,
    StrategyCapabilities,
    DataRequirements,
    DeploymentInfo,
    DeploymentStatus,
    DeploymentEnvironment,
)


class TestDataRequirements:
    """Test DataRequirements validation."""
    
    def test_valid_data_requirements(self):
        """Valid data requirements should pass validation."""
        req = DataRequirements(
            required_timeframes=["M5", "M15"],
            requires_intraday=True,
            min_history_days=30,
        )
        req.validate()  # Should not raise
    
    def test_empty_timeframes_fails(self):
        """Empty timeframes list should fail."""
        req = DataRequirements(
            required_timeframes=[],
            min_history_days=30,
        )
        with pytest.raises(AssertionError, match="At least one timeframe"):
            req.validate()
    
    def test_invalid_timeframe_fails(self):
        """Invalid timeframe should fail."""
        req = DataRequirements(
            required_timeframes=["M5", "INVALID"],
            min_history_days=30,
        )
        with pytest.raises(AssertionError, match="Invalid timeframe"):
            req.validate()
    
    def test_negative_history_fails(self):
        """Negative min_history_days should fail."""
        req = DataRequirements(
            required_timeframes=["M5"],
            min_history_days=0,
        )
        with pytest.raises(AssertionError, match="Min history must be positive"):
            req.validate()


class TestStrategyCapabilities:
    """Test StrategyCapabilities validation."""
    
    def test_valid_capabilities(self):
        """Valid capabilities should pass."""
        cap = StrategyCapabilities(
            supports_live_trading=True,
            supports_backtest=True,
            supports_pre_papertrade=True,
        )
        cap.validate()  # Should not raise
    
    def test_no_trading_mode_fails(self):
        """At least one trading mode required."""
        cap = StrategyCapabilities(
            supports_live_trading=False,
            supports_backtest=False,
            supports_pre_papertrade=False,
        )
        with pytest.raises(AssertionError, match="at least one trading mode"):
            cap.validate()
    
    def test_no_signal_type_fails(self):
        """At least one signal type required."""
        cap = StrategyCapabilities(
            supports_backtest=True,
            supports_live_trading=False,
            supports_pre_papertrade=False,
            generates_long_signals=False,
            generates_short_signals=False,
        )
        with pytest.raises(AssertionError, match="long or short signals"):
            cap.validate()


class TestStrategyMetadata:
    """Test StrategyMetadata validation and serialization."""
    
    @pytest.fixture
    def valid_metadata(self):
        """Create valid metadata for testing."""
        return StrategyMetadata(
            strategy_id="inside_bar_v2",
            canonical_name="inside_bar",
            display_name="Inside Bar Breakout",
            version="2.0.0",
            description="Inside bar pattern with ATR-based breakouts",
            capabilities=StrategyCapabilities(
                supports_live_trading=True,
                supports_backtest=True,
                supports_pre_papertrade=True,
            ),
            data_requirements=DataRequirements(
                required_timeframes=["M5"],
                min_history_days=30,
            ),
            config_class_path="strategies.inside_bar.core.InsideBarConfig",
            default_parameters={"atr_period": 14},
            signal_module_path="signals.cli_inside_bar",
            core_module_path="strategies.inside_bar.core",
        )
    
    def test_valid_metadata_creation(self, valid_metadata):
        """Valid metadata should be created successfully."""
        assert valid_metadata.strategy_id == "inside_bar_v2"
        assert valid_metadata.version == "2.0.0"
    
    def test_invalid_strategy_id_fails(self):
        """Invalid strategy_id format should fail."""
        with pytest.raises(ValueError, match="Invalid strategy_id"):
            StrategyMetadata(
                strategy_id="inside bar!",  # spaces and special chars
                canonical_name="inside_bar",
                display_name="Test",
                version="1.0.0",
                description="Test",
                capabilities=StrategyCapabilities(
                    supports_backtest=True,
                    supports_live_trading=False,
                    supports_pre_papertrade=False,
                ),
                data_requirements=DataRequirements(
                    required_timeframes=["M5"],
                    min_history_days=30,
                ),
                config_class_path="test.Config",
                default_parameters={},
                signal_module_path="test.signals",
                core_module_path="test.core",
            )
    
    def test_invalid_version_fails(self):
        """Invalid version format should fail."""
        with pytest.raises(ValueError, match="Invalid version"):
            StrategyMetadata(
                strategy_id="test_v1",
                canonical_name="test",
                display_name="Test",
                version="1.0",  # Not semver
                description="Test",
                capabilities=StrategyCapabilities(
                    supports_backtest=True,
                    supports_live_trading=False,
                    supports_pre_papertrade=False,
                ),
                data_requirements=DataRequirements(
                    required_timeframes=["M5"],
                    min_history_days=30,
                ),
                config_class_path="test.Config",
                default_parameters={},
                signal_module_path="test.signals",
                core_module_path="test.core",
            )
    
    def test_serialization_round_trip(self, valid_metadata):
        """to_dict() and from_dict() should be reversible."""
        # Serialize
        data_dict = valid_metadata.to_dict()
        
        # Deserialize
        restored = StrategyMetadata.from_dict(data_dict)
        
        # Verify
        assert restored.strategy_id == valid_metadata.strategy_id
        assert restored.version == valid_metadata.version
        assert restored.capabilities.supports_backtest == valid_metadata.capabilities.supports_backtest
    
    def test_environment_compatibility(self, valid_metadata):
        """is_compatible_with_environment() should work correctly."""
        # Supports pre-papertrade
        assert valid_metadata.is_compatible_with_environment(
            DeploymentEnvironment.PRE_PAPERTRADE_LAB
        )
        
        # Supports live
        assert valid_metadata.is_compatible_with_environment(
            DeploymentEnvironment.LIVE_TRADING
        )
        
        # All strategies support explore
        assert valid_metadata.is_compatible_with_environment(
            DeploymentEnvironment.EXPLORE_LAB
        )
    
    def test_repr_format(self, valid_metadata):
        """__repr__() should be informative."""
        repr_str = repr(valid_metadata)
        assert "inside_bar_v2" in repr_str
        assert "2.0.0" in repr_str
        assert "Inside Bar Breakout" in repr_str


class TestDeploymentInfo:
    """Test DeploymentInfo dataclass."""
    
    def test_default_deployment_info(self):
        """Default deployment info should work."""
        info = DeploymentInfo()
        assert info.deployment_status == DeploymentStatus.DEVELOPMENT
        assert info.deployed_environments == []
    
    def test_production_deployment(self):
        """Production deployment info."""
        info = DeploymentInfo(
            deployed_environments=[DeploymentEnvironment.LIVE_TRADING],
            deployment_status=DeploymentStatus.PRODUCTION,
            deployed_since=datetime(2025, 12, 7, 11, 30),
            deployed_by="mirko",
            git_tag="insidebar-v2.0.0",
        )
        assert info.deployment_status == DeploymentStatus.PRODUCTION
        assert DeploymentEnvironment.LIVE_TRADING in info.deployed_environments


class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_minimal_metadata(self):
        """Metadata with only required fields."""
        metadata = StrategyMetadata(
            strategy_id="minimal",
            canonical_name="minimal",
            display_name="Minimal Strategy",
            version="1.0.0",
            description="Minimal test",
            capabilities=StrategyCapabilities(
                supports_backtest=True,
                supports_live_trading=False,
                supports_pre_papertrade=False,
            ),
            data_requirements=DataRequirements(
                required_timeframes=["M5"],
                min_history_days=1,
            ),
            config_class_path="test.Config",
            default_parameters={},
            signal_module_path="test.signals",
            core_module_path="test.core",
        )
        metadata.validate()  # Should not raise
    
    def test_complex_metadata(self):
        """Metadata with all optional fields."""
        metadata = StrategyMetadata(
            strategy_id="complex_v3_2_1",
            canonical_name="complex",
            display_name="Complex Strategy",
            version="3.2.1",
            description="Complex test with all fields",
            capabilities=StrategyCapabilities(
                supports_backtest=True,
                supports_live_trading=True,
                supports_pre_papertrade=True,
                requires_two_stage_pipeline=True,
                generates_short_signals=True,
                supports_limit_orders=True,
                supports_portfolio_mode=True,
            ),
            data_requirements=DataRequirements(
                required_timeframes=["M5", "M15", "D1"],
                requires_intraday=True,
                requires_daily=True,
                requires_universe=True,
                min_history_days=365,
            ),
            config_class_path="strategies.complex.core.ComplexConfig",
            default_parameters={"param1": 123, "param2": "test"},
            parameter_schema={"type": "object", "properties": {}},
            signal_module_path="signals.complex",
            core_module_path="strategies.complex.core",
            required_indicators=["ATR", "SMA", "RSI"],
            deployment_info=DeploymentInfo(
                deployed_environments=[DeploymentEnvironment.LIVE_TRADING],
                deployment_status=DeploymentStatus.PRODUCTION,
            ),
            documentation_url="https://docs.example.com/complex",
        )
        metadata.validate()  # Should not raise
        assert len(metadata.required_indicators) == 3
