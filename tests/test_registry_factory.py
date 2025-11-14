#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 14 17:22:39 2025

@author: mirko
"""

"""Test suite for strategy registry and factory components."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
from typing import Dict, Any, List

# Add src to path for testing
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from strategies.base import BaseStrategy, Signal, IStrategy
from strategies.registry import StrategyRegistry, registry
from strategies.factory import StrategyFactory, create_strategy


class MockStrategy(BaseStrategy):
    """Mock strategy for testing."""
    
    @property
    def name(self) -> str:
        return "mock_strategy"
    
    @property
    def description(self) -> str:
        return "A mock strategy for testing"
    
    @property
    def config_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "number", "default": 1.0},
                "param2": {"type": "string", "default": "test"}
            },
            "required": ["param1"]
        }
    
    def generate_signals(
        self, data: pd.DataFrame, symbol: str, config: Dict[str, Any]
    ) -> List[Signal]:
        return [
            self.create_signal(
                timestamp="2025-01-01T10:00:00",
                symbol=symbol,
                signal_type="LONG",
                entry_price=100.0,
                metadata={"test": True}
            )
        ]


class InvalidStrategy:
    """Invalid strategy for testing error cases."""
    pass


class TestStrategyRegistry:
    """Test cases for StrategyRegistry."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.registry = StrategyRegistry()
    
    def test_register_valid_strategy(self):
        """Test registering a valid strategy."""
        self.registry.register("test_strategy", MockStrategy)
        
        assert "test_strategy" in self.registry.list_strategies()
        assert self.registry.get("test_strategy") == MockStrategy
    
    def test_register_duplicate_strategy(self):
        """Test registering duplicate strategy raises error."""
        self.registry.register("test_strategy", MockStrategy)
        
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register("test_strategy", MockStrategy)
    
    def test_register_empty_name(self):
        """Test registering with empty name raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            self.registry.register("", MockStrategy)
    
    def test_register_invalid_strategy(self):
        """Test registering invalid strategy raises error."""
        with pytest.raises(ValueError, match="does not implement IStrategy"):
            self.registry.register("invalid", InvalidStrategy)
    
    def test_unregister_strategy(self):
        """Test unregistering a strategy."""
        self.registry.register("test_strategy", MockStrategy)
        
        assert self.registry.unregister("test_strategy") == True
        assert "test_strategy" not in self.registry.list_strategies()
        assert self.registry.get("test_strategy") is None
    
    def test_unregister_nonexistent_strategy(self):
        """Test unregistering nonexistent strategy returns False."""
        assert self.registry.unregister("nonexistent") == False
    
    def test_get_nonexistent_strategy(self):
        """Test getting nonexistent strategy returns None."""
        assert self.registry.get("nonexistent") is None
    
    def test_list_strategies(self):
        """Test listing strategies."""
        assert self.registry.list_strategies() == []
        
        self.registry.register("strategy1", MockStrategy)
        self.registry.register("strategy2", MockStrategy)
        
        strategies = self.registry.list_strategies()
        assert len(strategies) == 2
        assert "strategy1" in strategies
        assert "strategy2" in strategies
    
    def test_metadata_handling(self):
        """Test strategy metadata handling."""
        metadata = {"type": "technical", "author": "test"}
        self.registry.register("test_strategy", MockStrategy, metadata)
        
        retrieved_metadata = self.registry.get_metadata("test_strategy")
        assert retrieved_metadata == metadata
    
    def test_clear_registry(self):
        """Test clearing the registry."""
        self.registry.register("strategy1", MockStrategy)
        self.registry.register("strategy2", MockStrategy)
        
        self.registry.clear()
        
        assert len(self.registry.list_strategies()) == 0
        assert self.registry.get("strategy1") is None
    
    def test_get_strategies_by_type(self):
        """Test filtering strategies by type."""
        self.registry.register("technical1", MockStrategy, {"type": "technical"})
        self.registry.register("fundamental1", MockStrategy, {"type": "fundamental"})
        self.registry.register("technical2", MockStrategy, {"type": "technical"})
        
        technical_strategies = self.registry.get_strategies_by_type("technical")
        assert len(technical_strategies) == 2
        assert "technical1" in technical_strategies
        assert "technical2" in technical_strategies
    
    def test_discovery_stats(self):
        """Test getting discovery statistics."""
        self.registry.register("test_strategy", MockStrategy)
        
        stats = self.registry.get_discovery_stats()
        
        assert stats["total_strategies"] == 1
        assert "test_strategy" in stats["strategies"]
        assert stats["strategies"]["test_strategy"]["class"] == "MockStrategy"


class TestStrategyFactory:
    """Test cases for StrategyFactory."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.registry = StrategyRegistry()
        self.registry.register("mock_strategy", MockStrategy)
    
    def test_create_strategy_success(self):
        """Test successful strategy creation."""
        with patch('strategies.factory.registry', self.registry):
            config = {"param1": 2.0, "param2": "test_value"}
            strategy = StrategyFactory.create_strategy("mock_strategy", config)
            
            assert isinstance(strategy, MockStrategy)
            assert strategy.name == "mock_strategy"
    
    def test_create_strategy_not_found(self):
        """Test creating nonexistent strategy raises error."""
        with patch('strategies.factory.registry', self.registry):
            with pytest.raises(ValueError, match="Unknown strategy"):
                StrategyFactory.create_strategy("nonexistent", {})
    
    def test_create_strategy_invalid_config(self):
        """Test creating strategy with invalid config raises error."""
        with patch('strategies.factory.registry', self.registry):
            config = {}  # Missing required param1
            with pytest.raises(ValueError, match="Invalid configuration"):
                StrategyFactory.create_strategy("mock_strategy", config)
    
    def test_create_strategy_skip_validation(self):
        """Test creating strategy with validation disabled."""
        with patch('strategies.factory.registry', self.registry):
            config = {}  # Invalid config, but validation disabled
            strategy = StrategyFactory.create_strategy(
                "mock_strategy", config, validate_config=False
            )
            
            assert isinstance(strategy, MockStrategy)
    
    def test_create_strategy_with_defaults(self):
        """Test creating strategy with default configuration."""
        with patch('strategies.factory.registry', self.registry):
            strategy = StrategyFactory.create_strategy_with_defaults("mock_strategy")
            
            assert isinstance(strategy, MockStrategy)
    
    def test_create_multiple_strategies(self):
        """Test creating multiple strategy instances."""
        with patch('strategies.factory.registry', self.registry):
            configs = [
                {"name": "mock_strategy", "config": {"param1": 1.0}},
                {"name": "mock_strategy", "config": {"param1": 2.0}}
            ]
            
            strategies = StrategyFactory.create_multiple_strategies(configs)
            
            assert len(strategies) == 2
            assert "mock_strategy" in strategies
            assert "mock_strategy_1" in strategies  # Duplicate handling
    
    def test_create_multiple_strategies_with_failures(self):
        """Test creating multiple strategies with some failures."""
        with patch('strategies.factory.registry', self.registry):
            configs = [
                {"name": "mock_strategy", "config": {"param1": 1.0}},
                {"name": "nonexistent", "config": {}}  # This will fail
            ]
            
            with pytest.raises(ValueError, match="Failed to create"):
                StrategyFactory.create_multiple_strategies(configs)
    
    def test_list_available_strategies(self):
        """Test listing available strategies."""
        with patch('strategies.factory.registry', self.registry):
            strategies = StrategyFactory.list_available_strategies()
            
            assert "mock_strategy" in strategies
    
    def test_get_strategy_schema(self):
        """Test getting strategy configuration schema."""
        with patch('strategies.factory.registry', self.registry):
            schema = StrategyFactory.get_strategy_schema("mock_strategy")
            
            assert "properties" in schema
            assert "param1" in schema["properties"]
    
    def test_validate_strategy_config(self):
        """Test validating strategy configuration."""
        with patch('strategies.factory.registry', self.registry):
            # Valid config
            assert StrategyFactory.validate_strategy_config(
                "mock_strategy", {"param1": 1.0}
            ) == True
            
            # Invalid config
            assert StrategyFactory.validate_strategy_config(
                "mock_strategy", {}
            ) == False
    
    def test_get_strategy_info(self):
        """Test getting comprehensive strategy information."""
        with patch('strategies.factory.registry', self.registry):
            info = StrategyFactory.get_strategy_info("mock_strategy")
            
            assert info["name"] == "mock_strategy"
            assert info["class"] == "MockStrategy"
            assert info["description"] == "A mock strategy for testing"
            assert "config_schema" in info
            assert "required_columns" in info


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.test_registry = StrategyRegistry()
        self.test_registry.register("mock_strategy", MockStrategy)
    
    def test_create_strategy_function(self):
        """Test create_strategy convenience function."""
        with patch('strategies.factory.registry', self.test_registry):
            strategy = create_strategy("mock_strategy", {"param1": 1.0})
            
            assert isinstance(strategy, MockStrategy)
    
    def test_list_strategies_function(self):
        """Test list_strategies convenience function."""
        with patch('strategies.factory.registry', self.test_registry):
            from strategies.factory import list_strategies
            strategies = list_strategies()
            
            assert "mock_strategy" in strategies


class TestIntegration:
    """Integration tests for registry and factory working together."""
    
    def setup_method(self):
        """Setup for integration tests."""
        # Use the global registry for integration tests
        registry.clear()
        registry.register("integration_strategy", MockStrategy)
    
    def teardown_method(self):
        """Cleanup after integration tests."""
        registry.clear()
    
    def test_end_to_end_workflow(self):
        """Test complete workflow from registration to strategy execution."""
        # Create strategy using factory
        config = {"param1": 1.5, "param2": "integration_test"}
        strategy = StrategyFactory.create_strategy("integration_strategy", config)
        
        # Test strategy functionality
        test_data = pd.DataFrame({
            'timestamp': ['2025-01-01T10:00:00'],
            'open': [100.0],
            'high': [105.0],
            'low': [95.0],
            'close': [102.0],
            'volume': [1000]
        })
        
        signals = strategy.generate_signals(test_data, "TEST", config)
        
        assert len(signals) == 1
        assert signals[0].symbol == "TEST"
        assert signals[0].signal_type == "LONG"
        assert signals[0].strategy == "integration_strategy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])