"""
Signal output schema contract.

Defines the canonical format for strategy signals to ensure
consistency across different strategy implementations.
"""

from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field, validator


class SignalOutputSpec(BaseModel):
    """
    Canonical signal output format for all strategies.
    
    This contract ensures all signals contain:
    - Entry prices (long/short)
    - Stop loss levels
    - Take profit targets
    - Metadata for debugging and analysis
    """
    
    # Required fields
    symbol: str = Field(..., description="Ticker symbol")
    timestamp: datetime = Field(..., description="Signal generation timestamp (UTC)")
    strategy: str = Field(..., description="Strategy name")
    strategy_version: str = Field(..., description="Strategy version (semver)")
    
    # Entry signals (Optional - at least one should be set)
    long_entry: Optional[Decimal] = Field(None, description="Long entry price")
    short_entry: Optional[Decimal] = Field(None, description="Short entry price")
    
    # Stop loss levels
    sl_long: Optional[Decimal] = Field(None, description="Stop loss for long position")
    sl_short: Optional[Decimal] = Field(None, description="Stop loss for short position")
    
    # Take profit targets
    tp_long: Optional[Decimal] = Field(None, description="Take profit for long position")
    tp_short: Optional[Decimal] = Field(None, description="Take profit for short position")
    
    # Signal metadata
    setup: Optional[str] = Field(None, description="Setup type (e.g., 'inside_bar', 'breakout')")
    score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    score_components: Optional[Dict[str, float]] = Field(
        None, 
        description="Score breakdown (e.g., {'volatility': 0.8, 'volume': 0.9})"
    )
    
    # Additional metadata
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }
    
    @validator('timestamp')
    def timestamp_must_be_utc(cls, v):
        """Ensure timestamp is UTC."""
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")
        return v
    
    @validator('score')
    def score_must_be_valid(cls, v):
        """Validate score is in range."""
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("Score must be between 0.0 and 1.0")
        return v
    
    def to_csv_row(self) -> Dict[str, Any]:
        """Convert to flat dictionary for CSV export."""
        return {
            'Symbol': self.symbol,
            'Timestamp': self.timestamp.isoformat(),
            'Strategy': self.strategy,
            'StrategyVersion': self.strategy_version,
            'LongEntry': str(self.long_entry) if self.long_entry else '',
            'ShortEntry': str(self.short_entry) if self.short_entry else '',
            'SL_Long': str(self.sl_long) if self.sl_long else '',
            'SL_Short': str(self.sl_short) if self.sl_short else '',
            'TP_Long': str(self.tp_long) if self.tp_long else '',
            'TP_Short': str(self.tp_short) if self.tp_short else '',
            'Setup': self.setup or '',
            'Score': self.score if self.score is not None else '',
        }


# Legacy compatibility - DataFrame columns format
SIGNAL_COLUMNS = [
    'Symbol',
    'long_entry',
    'short_entry', 
    'sl_long',
    'sl_short',
    'tp_long',
    'tp_short',
    'setup',
    'score',
    'strategy',
    'strategy_version'
]
