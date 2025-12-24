"""
Risk guards and kill switch for order safety.

Implements central risk controls before order submission.
All guards must pass before an order can be sent to broker.
"""

from typing import List, Optional, Protocol
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
from abc import ABC, abstractmethod


@dataclass
class GuardRejection:
    """Rejection from a risk guard."""
    guard_name: str
    reason: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class Portfolio(Protocol):
    """Portfolio state interface for guards."""
    cash: Decimal
    positions: dict  # {symbol: qty}
    daily_pnl: Decimal
    peak_equity: Decimal


class Order(Protocol):
    """Order interface for guards."""
    symbol: str
    side: str  # 'BUY' or 'SELL'
    qty: Decimal
    limit_price: Optional[Decimal]


class RiskGuard(ABC):
    """Abstract base class for risk guards."""
    
    @abstractmethod
    def check(self, order: Order, portfolio: Portfolio) -> Optional[GuardRejection]:
        """
        Check if order passes this guard.
        
        Returns:
            None if passed, GuardRejection if rejected
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Guard name for logging."""
        pass


class MaxGrossExposureGuard(RiskGuard):
    """Prevent total exposure from exceeding limit."""
    
    def __init__(self, max_exposure: Decimal):
        self.max_exposure = max_exposure
    
    @property
    def name(self) -> str:
        return "MaxGrossExposure"
    
    def check(self, order: Order, portfolio: Portfolio) -> Optional[GuardRejection]:
        # Calculate current exposure
        current_exposure = sum(
            abs(qty * Decimal('100'))  # Simplified: assume $100/share
            for qty in portfolio.positions.values()
        )
        
        # Calculate new exposure if order fills
        new_exposure = current_exposure
        if order.side == 'BUY':
            new_exposure += order.qty * (order.limit_price or Decimal('100'))
        
        if new_exposure > self.max_exposure:
            return GuardRejection(
                guard_name=self.name,
                reason=f"Exposure would exceed limit: {new_exposure} > {self.max_exposure}"
            )
        
        return None


class PerSymbolMaxQtyGuard(RiskGuard):
    """Prevent position size from exceeding per-symbol limit."""
    
    def __init__(self, max_qty_per_symbol: Decimal):
        self.max_qty_per_symbol = max_qty_per_symbol
    
    @property
    def name(self) -> str:
        return "PerSymbolMaxQty"
    
    def check(self, order: Order, portfolio: Portfolio) -> Optional[GuardRejection]:
        current_qty = portfolio.positions.get(order.symbol, Decimal('0'))
        
        new_qty = current_qty
        if order.side == 'BUY':
            new_qty += order.qty
        else:
            new_qty -= order.qty
        
        if abs(new_qty) > self.max_qty_per_symbol:
            return GuardRejection(
                guard_name=self.name,
                reason=f"Position would exceed limit: {abs(new_qty)} > {self.max_qty_per_symbol}"
            )
        
        return None


class MaxDailyLossGuard(RiskGuard):
    """Kill switch: Stop trading if daily loss exceeds limit."""
    
    def __init__(self, max_daily_loss: Decimal):
        self.max_daily_loss = abs(max_daily_loss)  # Always positive
    
    @property
    def name(self) -> str:
        return "MaxDailyLoss"
    
    def check(self, order: Order, portfolio: Portfolio) -> Optional[GuardRejection]:
        if portfolio.daily_pnl < -self.max_daily_loss:
            return GuardRejection(
                guard_name=self.name,
                reason=f"Daily loss limit breached: {portfolio.daily_pnl} < -{self.max_daily_loss}"
            )
        
        return None


class MaxDrawdownGuard(RiskGuard):
    """Kill switch: Stop trading if drawdown from peak exceeds limit."""
    
    def __init__(self, max_drawdown: Decimal):
        self.max_drawdown = abs(max_drawdown)
    
    @property
    def name(self) -> str:
        return "MaxDrawdown"
    
    def check(self, order: Order, portfolio: Portfolio) -> Optional[GuardRejection]:
        current_equity = portfolio.cash + sum(
            qty * Decimal('100')  # Simplified
            for qty in portfolio.positions.values()
        )
        
        drawdown = portfolio.peak_equity - current_equity
        
        if drawdown > self.max_drawdown:
            return GuardRejection(
                guard_name=self.name,
                reason=f"Drawdown limit breached: {drawdown} > {self.max_drawdown}"
            )
        
        return None


class SlippageSanityGuard(RiskGuard):
    """Reject orders with unrealistic limit prices (sanity check)."""
    
    def __init__(self, max_slippage_pct: float = 5.0):
        self.max_slippage_pct = max_slippage_pct
    
    @property
    def name(self) -> str:
        return "SlippageSanity"
    
    def check(self, order: Order, portfolio: Portfolio) -> Optional[GuardRejection]:
        # TODO: Compare order.limit_price against recent market price
        # For now, just a placeholder
        return None


class GuardRegistry:
    """
    Registry of risk guards to check before order submission.
    
    Usage:
        registry = GuardRegistry()
        registry.add(MaxDailyLossGuard(max_daily_loss=Decimal('1000')))
        registry.add(MaxGrossExposureGuard(max_exposure=Decimal('50000')))
        
        rejection = registry.check_all(order, portfolio)
        if rejection:
            logger.warning(f"Order rejected: {rejection.reason}")
        else:
            broker.send_order(order)
    """
    
    def __init__(self):
        self.guards: List[RiskGuard] = []
    
    def add(self, guard: RiskGuard):
        """Add a guard to the registry."""
        self.guards.append(guard)
    
    def check_all(
        self, 
        order: Order, 
        portfolio: Portfolio
    ) -> Optional[GuardRejection]:
        """
        Check order against all guards.
        
        Returns:
            First rejection encountered, or None if all pass
        """
        for guard in self.guards:
            rejection = guard.check(order, portfolio)
            if rejection is not None:
                return rejection
        
        return None
    
    def check_all_detailed(
        self,
        order: Order,
        portfolio: Portfolio
    ) -> List[GuardRejection]:
        """
        Check order against all guards, collect all rejections.
        
        Returns:
            List of all rejections (empty if all pass)
        """
        rejections = []
        for guard in self.guards:
            rejection = guard.check(order, portfolio)
            if rejection is not None:
                rejections.append(rejection)
        
        return rejections


# Convenience function

def create_default_guards(
    max_daily_loss: Decimal = Decimal('1000'),
    max_drawdown: Decimal = Decimal('1500'),
    max_exposure: Decimal = Decimal('50000'),
    max_qty_per_symbol: Decimal = Decimal('100')
) -> GuardRegistry:
    """Create a registry with sensible default guards."""
    registry = GuardRegistry()
    registry.add(MaxDailyLossGuard(max_daily_loss))
    registry.add(MaxDrawdownGuard(max_drawdown))
    registry.add(MaxGrossExposureGuard(max_exposure))
    registry.add(PerSymbolMaxQtyGuard(max_qty_per_symbol))
    registry.add(SlippageSanityGuard())
    return registry
