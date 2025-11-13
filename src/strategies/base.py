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

    @property
    def name(self) -> str:
        """Return the unique name of this strategy."""
        ...

    @property
    def version(self) -> str:
        """Return the version of this strategy."""
        ...

    @property
    def description(self) -> str:
        """Return a description of what this strategy does."""
        ...

    @property
    def config_schema(self) -> Dict[str, Any]:
        """Return the JSON schema for this strategy's configuration parameters."""
        ...

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate the provided configuration parameters.

        Args:
            config: Dictionary of configuration parameters

        Returns:
            True if configuration is valid, False otherwise
        """
        ...

    def generate_signals(
        self, data: pd.DataFrame, symbol: str, config: Dict[str, Any]
    ) -> List[Signal]:
        """Generate trading signals based on market data.

        Args:
            data: OHLCV data as pandas DataFrame
            symbol: Trading symbol
            config: Strategy configuration parameters

        Returns:
            List of Signal objects
        """
        ...

    def get_required_data_columns(self) -> List[str]:
        """Return the list of required columns in the input data DataFrame.

        Returns:
            List of column names (e.g., ['open', 'high', 'low', 'close', 'volume'])
        """
        ...

    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Preprocess the input data before signal generation.

        Args:
            data: Raw OHLCV data

        Returns:
            Preprocessed data ready for signal generation
        """
        ...


class BaseStrategy(ABC):
    """Abstract base class providing common functionality for strategies.

    Strategies can inherit from this class to get default implementations
    of common methods while still implementing the IStrategy protocol.
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        """Initialize the strategy with configuration.

        Args:
            config: Strategy configuration object
        """
        self._config = config or StrategyConfig(name=self.name)

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this strategy."""
        pass

    @property
    def version(self) -> str:
        """Return the version of this strategy."""
        return self._config.version

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of what this strategy does."""
        pass

    @property
    @abstractmethod
    def config_schema(self) -> Dict[str, Any]:
        """Return the JSON schema for this strategy's configuration parameters."""
        pass

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Default validation implementation.

        Override this method for custom validation logic.
        """
        try:
            # Basic validation - check if all required fields are present
            schema = self.config_schema
            required = schema.get("required", [])

            for field in required:
                if field not in config:
                    return False

            return True
        except Exception:
            return False

    @abstractmethod
    def generate_signals(
        self, data: pd.DataFrame, symbol: str, config: Dict[str, Any]
    ) -> List[Signal]:
        """Generate trading signals - must be implemented by subclasses."""
        pass

    def get_required_data_columns(self) -> List[str]:
        """Default required columns for OHLCV data."""
        return ["timestamp", "open", "high", "low", "close", "volume"]

    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Default preprocessing - return data as-is.

        Override this method to add custom preprocessing logic.
        """
        # Ensure timestamp is datetime
        if "timestamp" in data.columns and data["timestamp"].dtype == "object":
            data = data.copy()
            data["timestamp"] = pd.to_datetime(data["timestamp"])

        return data

    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate that the input data has all required columns."""
        required_columns = set(self.get_required_data_columns())
        available_columns = set(data.columns)

        missing_columns = required_columns - available_columns
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        return True

    def create_signal(
        self,
        timestamp: str,
        symbol: str,
        signal_type: str,
        confidence: float = 1.0,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        **metadata,
    ) -> Signal:
        """Helper method to create a standardized signal.

        Args:
            timestamp: Signal timestamp
            symbol: Trading symbol
            signal_type: Type of signal (LONG, SHORT, CLOSE)
            confidence: Signal confidence (0-1)
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            **metadata: Additional metadata

        Returns:
            Signal object
        """
        return Signal(
            timestamp=timestamp,
            symbol=symbol,
            signal_type=signal_type,
            strategy=self.name,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata=metadata,
        )
