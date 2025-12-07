"""Canonical order schema contract.

Defines the standard order format with idempotency guarantees
for safe retry logic and order lifecycle tracking.
"""

from typing import Optional, Literal
from decimal import Decimal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict, field_validator
import hashlib


class OrderSchema(BaseModel):
    """
    Canonical order format with idempotency.
    
    Key features:
    - Deterministic idempotency_key for safe retries
    - OCO (One-Cancels-Other) support
    - Session-based validity
    - Full audit trail metadata
    """
    
    # Identity & Idempotency
    order_id: Optional[str] = Field(None, description="Internal order ID (UUID)")
    idempotency_key: str = Field(..., description="Deterministic key for retry safety")
    oco_id: Optional[str] = Field(None, description="OCO group identifier")
    
    # Tracing
    run_id: str = Field(..., description="Backtest/Live run identifier")
    strategy: str = Field(..., description="Strategy name")
    strategy_version: str = Field(..., description="Strategy version")
    
    # Order details
    symbol: str = Field(..., description="Ticker symbol")
    side: Literal['BUY', 'SELL'] = Field(..., description="Order side")
    qty: Decimal = Field(..., gt=0, description="Quantity (shares)")
    
    # Prices
    limit_price: Optional[Decimal] = Field(None, description="Limit price")
    stop_price: Optional[Decimal] = Field(None, description="Stop price")
    take_profit_price: Optional[Decimal] = Field(None, description="Take profit price")
    
    # Validity
    valid_from: datetime = Field(..., description="Order valid from (UTC)")
    valid_to: datetime = Field(..., description="Order valid until (UTC)")
    session: Optional[str] = Field(None, description="Trading session (e.g., 'RTH')")
    time_in_force: Literal['DAY', 'GTC', 'IOC', 'FOK'] = Field(
        'DAY', 
        description="Time in force"
    )
    
    # Metadata
    source: Literal['backtest', 'paper', 'live'] = Field(..., description="Order source")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
            datetime: lambda v: v.isoformat(),
        }
    )

    @field_validator('valid_from', 'valid_to', 'created_at')
    @classmethod
    def datetime_must_be_utc(cls, v: datetime) -> datetime:
        """Ensure all datetimes are UTC."""
        if v.tzinfo is None:
            raise ValueError("Datetime must be timezone-aware (UTC)")
        return v

    @field_validator('idempotency_key')
    @classmethod
    def idempotency_key_format(cls, v: str) -> str:
        """Validate idempotency key format."""
        if len(v) < 8:
            raise ValueError("Idempotency key must be at least 8 characters")
        return v
    
    @classmethod
    def generate_idempotency_key(
        cls,
        run_id: str,
        strategy: str,
        strategy_version: str,
        symbol: str,
        side: str,
        oco_id: Optional[str] = None
    ) -> str:
        """
        Generate deterministic idempotency key.
        
        Given the same inputs, always produces the same key.
        This enables safe retries without duplicate orders.
        
        Args:
            run_id: Run identifier
            strategy: Strategy name
            strategy_version: Strategy version
            symbol: Ticker symbol
            side: BUY or SELL
            oco_id: Optional OCO group ID
            
        Returns:
            16-character hex string (SHA1 hash truncated)
        """
        components = [
            run_id,
            strategy,
            strategy_version,
            symbol,
            side,
            oco_id or ''
        ]
        hash_input = '|'.join(components)
        hash_obj = hashlib.sha1(hash_input.encode('utf-8'))
        return hash_obj.hexdigest()[:16]
    
    def to_csv_row(self) -> dict:
        """Convert to flat dictionary for CSV export."""
        return {
            'order_id': self.order_id or '',
            'idempotency_key': self.idempotency_key,
            'oco_id': self.oco_id or '',
            'run_id': self.run_id,
            'symbol': self.symbol,
            'side': self.side,
            'qty': str(self.qty),
            'limit_price': str(self.limit_price) if self.limit_price else '',
            'stop_price': str(self.stop_price) if self.stop_price else '',
            'take_profit_price': str(self.take_profit_price) if self.take_profit_price else '',
            'valid_from': self.valid_from.isoformat(),
            'valid_to': self.valid_to.isoformat(),
            'session': self.session or '',
            'time_in_force': self.time_in_force,
            'source': self.source,
            'strategy': self.strategy,
            'strategy_version': self.strategy_version,
            'created_at': self.created_at.isoformat()
        }


# CSV column order
ORDER_CSV_COLUMNS = [
    'order_id',
    'idempotency_key',
    'oco_id',
    'run_id',
    'symbol',
    'side',
    'qty',
    'limit_price',
    'stop_price',
    'take_profit_price',
    'valid_from',
    'valid_to',
    'session',
    'time_in_force',
    'source',
    'strategy',
    'strategy_version',
    'created_at'
]
