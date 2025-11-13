"""Base classes and interfaces for trading strategies."""

from abc import ABC, abstractmethod
from typing import Protocol, List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from pydantic import BaseModel, Field, ConfigDict


class Signal(BaseModel):
    """Standardized signal format for all strategies."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}, validate_assignment=True
    )

    timestamp: str = Field(..., description="Signal timestamp in ISO format")
    symbol: str = Field(..., description="Trading symbol")
    signal_type: str = Field(..., description="Signal type: LONG, SHORT, CLOSE")
    strategy: str = Field(..., description="Strategy name that generated the signal")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Signal confidence (0-1)")
    entry_price: Optional[float] = Field(default=None, description="Suggested entry price")
    stop_loss: Optional[float] = Field(default=None, description="Stop loss price")
    take_profit: Optional[float] = Field(default=None, description="Take profit price")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional strategy-specific data"
    )

    def __str__(self) -> str:
        return f"Signal({self.strategy}: {self.signal_type} {self.symbol} @ {self.timestamp})"


class StrategyConfig(BaseModel):
    """Base configuration for all strategies."""

    name: str = Field(..., description="Strategy unique name")
    version: str = Field(default="1.0.0", description="Strategy version")
    description: Optional[str] = Field(default=None, description="Strategy description")
    enabled: bool = Field(default=True, description="Whether strategy is enabled")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Strategy-specific parameters"
    )


class IStrategy(Protocol):
    """Protocol defining the interface that all trading strategies must implement.

    This uses Python's Protocol for structural typing, allowing any class
    that implements these methods to be considered a valid strategy.
    """
