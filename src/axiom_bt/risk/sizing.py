"""
Position sizing with mathematical invariants.

Implements three sizing modes from v2 architecture:
1. Fixed quantity
2. Percentage of equity
3. Risk-based (% of equity at risk per trade)
"""

from enum import Enum
from decimal import Decimal, ROUND_DOWN
from typing import Optional
from dataclasses import dataclass


class SizingMode(Enum):
    """Position sizing modes."""
    FIXED = "fixed"
    PCT_EQUITY = "pct_equity"
    RISK_BASED = "risk"


@dataclass
class SizingConfig:
    """Configuration for position sizing."""
    mode: SizingMode
    
    # For FIXED mode
    fixed_qty: Optional[Decimal] = None
    
    # For PCT_EQUITY mode
    equity: Optional[Decimal] = None
    pos_pct: Optional[float] = None  # e.g., 10.0 for 10%
    
    # For RISK_BASED mode
    risk_pct: Optional[float] = None  # e.g., 1.0 for 1%
    max_pos_pct: Optional[float] = None  # e.g., 20.0 for 20% cap
    
    # Common settings
    min_qty: Decimal = Decimal('1')
    tick_size: Decimal = Decimal('1')  # For rounding


class PositionSizer:
    """
    Position sizing calculator with invariant enforcement.
    
    Guarantees:
    - All quantities are tick-rounded
    - Quantities >= min_qty
    - Risk-based sizing respects max_pos_pct
    - Deterministic (same inputs = same output)
    """
    
    def __init__(self, config: SizingConfig):
        self.config = config
        self._validate_config()
    
    def _validate_config(self):
        """Validate sizing configuration."""
        if self.config.mode == SizingMode.FIXED:
            if self.config.fixed_qty is None:
                raise ValueError("FIXED mode requires fixed_qty")
        
        elif self.config.mode == SizingMode.PCT_EQUITY:
            if self.config.equity is None or self.config.pos_pct is None:
                raise ValueError("PCT_EQUITY mode requires equity and pos_pct")
        
        elif self.config.mode == SizingMode.RISK_BASED:
            if (self.config.equity is None or 
                self.config.risk_pct is None or 
                self.config.max_pos_pct is None):
                raise ValueError("RISK_BASED mode requires equity, risk_pct, max_pos_pct")
    
    def calculate(
        self,
        entry_price: Decimal,
        stop_price: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate position size.
        
        Args:
            entry_price: Entry price
            stop_price: Stop loss price (required for risk-based sizing)
            
        Returns:
            Position size (tick-rounded, >= min_qty)
        """
        if self.config.mode == SizingMode.FIXED:
            return self._calculate_fixed()
        
        elif self.config.mode == SizingMode.PCT_EQUITY:
            return self._calculate_pct_equity(entry_price)
        
        elif self.config.mode == SizingMode.RISK_BASED:
            if stop_price is None:
                raise ValueError("RISK_BASED mode requires stop_price")
            return self._calculate_risk_based(entry_price, stop_price)
        
        else:
            raise ValueError(f"Unknown sizing mode: {self.config.mode}")
    
    def _calculate_fixed(self) -> Decimal:
        """Fixed quantity mode."""
        qty = self.config.fixed_qty
        qty = self._round_to_tick(qty)
        qty = max(qty, self.config.min_qty)
        return qty
    
    def _calculate_pct_equity(self, entry_price: Decimal) -> Decimal:
        """
        Percentage of equity mode.
        
        Formula:
            notional = equity * pos_pct / 100
            qty = floor(notional / entry_price)
            qty = round_to_tick(qty)
        """
        notional = self.config.equity * Decimal(str(self.config.pos_pct)) / Decimal('100')
        qty = (notional / entry_price).quantize(Decimal('1'), rounding=ROUND_DOWN)
        qty = self._round_to_tick(qty)
        qty = max(qty, self.config.min_qty)
        return qty
    
    def _calculate_risk_based(
        self,
        entry_price: Decimal,
        stop_price: Decimal
    ) -> Decimal:
        """
        Risk-based mode.
        
        Formula:
            risk_amount = equity * risk_pct / 100
            stop_distance = abs(entry_price - stop_price)
            stop_distance_ticks = round_to_tick(stop_distance)
            qty = floor(risk_amount / stop_distance_ticks)
            qty = round_to_tick(qty)
            
            # Cap at max_pos_pct
            max_qty = floor((equity * max_pos_pct / 100) / entry_price)
            qty = min(qty, max_qty)
        """
        # Calculate risk amount
        risk_amount = self.config.equity * Decimal(str(self.config.risk_pct)) / Decimal('100')
        
        # Calculate stop distance in ticks
        stop_distance = abs(entry_price - stop_price)
        stop_distance_ticks = self._round_to_tick(stop_distance)
        
        if stop_distance_ticks == 0:
            # Avoid division by zero
            return self.config.min_qty
        
        # Calculate quantity based on risk
        qty = (risk_amount / stop_distance_ticks).quantize(Decimal('1'), rounding=ROUND_DOWN)
        qty = self._round_to_tick(qty)
        
        # Enforce max position size
        max_notional = self.config.equity * Decimal(str(self.config.max_pos_pct)) / Decimal('100')
        max_qty = (max_notional / entry_price).quantize(Decimal('1'), rounding=ROUND_DOWN)
        max_qty = self._round_to_tick(max_qty)
        
        qty = min(qty, max_qty)
        qty = max(qty, self.config.min_qty)
        
        return qty
    
    def _round_to_tick(self, value: Decimal) -> Decimal:
        """Round value to nearest tick size."""
        if self.config.tick_size == Decimal('1'):
            return value.quantize(Decimal('1'), rounding=ROUND_DOWN)
        
        # Round down to nearest tick
        ticks = (value / self.config.tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN)
        return ticks * self.config.tick_size


# Convenience functions

def calculate_fixed_size(qty: Decimal, tick_size: Decimal = Decimal('1')) -> Decimal:
    """Calculate fixed position size."""
    config = SizingConfig(mode=SizingMode.FIXED, fixed_qty=qty, tick_size=tick_size)
    sizer = PositionSizer(config)
    return sizer.calculate(entry_price=Decimal('1'))  # Price doesn't matter


def calculate_pct_equity_size(
    equity: Decimal,
    pos_pct: float,
    entry_price: Decimal,
    tick_size: Decimal = Decimal('1'),
    min_qty: Decimal = Decimal('1')
) -> Decimal:
    """Calculate size as percentage of equity."""
    config = SizingConfig(
        mode=SizingMode.PCT_EQUITY,
        equity=equity,
        pos_pct=pos_pct,
        tick_size=tick_size,
        min_qty=min_qty
    )
    sizer = PositionSizer(config)
    return sizer.calculate(entry_price=entry_price)


def calculate_risk_based_size(
    equity: Decimal,
    risk_pct: float,
    entry_price: Decimal,
    stop_price: Decimal,
    max_pos_pct: float = 20.0,
    tick_size: Decimal = Decimal('1'),
    min_qty: Decimal = Decimal('1')
) -> Decimal:
    """Calculate size based on risk percentage."""
    config = SizingConfig(
        mode=SizingMode.RISK_BASED,
        equity=equity,
        risk_pct=risk_pct,
        max_pos_pct=max_pos_pct,
        tick_size=tick_size,
        min_qty=min_qty
    )
    sizer = PositionSizer(config)
    return sizer.calculate(entry_price=entry_price, stop_price=stop_price)
