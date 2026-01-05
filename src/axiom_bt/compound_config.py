"""
Compound sizing configuration loader.

Extracts compound_sizing and compound_equity_basis from strategy config
and provides validation.
"""

from dataclasses import dataclass
from typing import Literal, Dict, Any


@dataclass
class CompoundConfig:
    """
    Compound sizing configuration.
    
    Controls whether position sizing uses growing equity (compound=true)
    or fixed initial cash (compound=false, default).
    """
    enabled: bool = False
    equity_basis: Literal["cash_only", "mark_to_market"] = "cash_only"
    
    @classmethod
    def from_strategy_params(cls, strategy_params: Dict[str, Any]) -> "CompoundConfig":
        """
        Extract compound config from strategy params dict.
        
        Args:
            strategy_params: Strategy parameters (from YAML or runtime config)
            
        Returns:
            CompoundConfig with defaults if keys missing
        """
        # Try backtesting section first (SSOT), then root level
        backtesting = strategy_params.get("backtesting", {})
        
        enabled = backtesting.get("compound_sizing", False)
        equity_basis = backtesting.get("compound_equity_basis", "cash_only")
        
        return cls(enabled=enabled, equity_basis=equity_basis)
    
    def validate(self):
        """
        Validate compound configuration.
        
        Raises:
            ValueError: If configuration is invalid
            NotImplementedError: If mark_to_market is requested
        """
        if not isinstance(self.enabled, bool):
            raise ValueError(f"compound_sizing must be bool, got {type(self.enabled)}")
        
        if self.equity_basis not in ["cash_only", "mark_to_market"]:
            raise ValueError(
                f"Invalid compound_equity_basis: {self.equity_basis}. "
                "Must be 'cash_only' or 'mark_to_market'."
            )
        
        # CHECK 4: mark_to_market guard
        if self.enabled and self.equity_basis == "mark_to_market":
            raise NotImplementedError(
                "Compound sizing with mark_to_market equity basis is not yet implemented. "
                "Use compound_equity_basis='cash_only' instead."
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Export as dict for manifest/logging."""
        return {
            "compound_sizing": self.enabled,
            "compound_equity_basis": self.equity_basis
        }
