"""
Trade Templates - Compound Sizing Phase 2 (F1)

Extracts trade intentions WITHOUT quantity calculation.
Templates represent "what to trade" (entry/exit signals) but not "how much" (sizing).

Design Principles:
- Deterministic: Same inputs → same templates
- Shuffle-invariant: Order of processing doesn't matter
- No side effects: Pure data extraction
- Reuses existing detection logic
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional
import pandas as pd


@dataclass(frozen=True)
class TradeTemplate:
    """
    Trade template representing entry/exit intention.
    
    Does NOT include qty - that's calculated at execution time based on equity.
    Immutable for determinism and safety.
    """
    # Identity
    template_id: str  # Unique identifier for this template
    symbol: str
    side: Literal["BUY", "SELL"]
    
    # Entry
    entry_ts: pd.Timestamp
    entry_price: float  # Intended entry price
    entry_reason: str  # e.g., "inside_bar_long"
    
    # Exit
    exit_ts: Optional[pd.Timestamp] = None  # None if position still open
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # e.g., "stop_loss", "take_profit", "session_end"
    
    # Risk Management (prices, not qty)
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    
    # Metadata
    atr_at_entry: Optional[float] = None  # For sizing context
    session_start: Optional[pd.Timestamp] = None
    session_end: Optional[pd.Timestamp] = None
    
    def __post_init__(self):
        """Validate template integrity."""
        if self.entry_price <= 0:
            raise ValueError(f"entry_price must be positive, got {self.entry_price}")
        
        if self.exit_price is not None and self.exit_price <= 0:
            raise ValueError(f"exit_price must be positive, got {self.exit_price}")
        
        if self.exit_ts is not None and self.entry_ts >= self.exit_ts:
            raise ValueError(
                f"entry_ts ({self.entry_ts}) must be before exit_ts ({self.exit_ts})"
            )
    
    @property
    def is_closed(self) -> bool:
        """Whether this template represents a closed trade."""
        return self.exit_ts is not None
    
    @property
    def is_long(self) -> bool:
        """Whether this is a long position."""
        return self.side == "BUY"
    
    def to_dict(self) -> dict:
        """Export as dict for testing/debugging."""
        return {
            "template_id": self.template_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_ts": self.entry_ts.isoformat() if self.entry_ts else None,
            "entry_price": self.entry_price,
            "entry_reason": self.entry_reason,
            "exit_ts": self.exit_ts.isoformat() if self.exit_ts else None,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "atr_at_entry": self.atr_at_entry,
            "is_closed": self.is_closed,
        }


def extract_templates_from_orders(
    orders_df: pd.DataFrame,
    symbol: str,
) -> list[TradeTemplate]:
    """
    Extract trade templates from orders DataFrame.
    
    This is a minimal builder for F1-C1. Full implementation will come later.
    For now, just proves the dataclass works and is deterministic.
    
    Args:
        orders_df: Orders with columns [entry_ts, side, entry_price, ...]
        symbol: Symbol to extract templates for
        
    Returns:
        List of TradeTemplate objects (deterministic order)
    """
    if orders_df.empty:
        return []
    
    # Sort deterministically (crucial for shuffle-invariance)
    if "entry_ts" in orders_df.columns:
        orders_sorted = orders_df.sort_values(
            ["entry_ts", "entry_price", "side"],
            ascending=[True, True, True]
        ).reset_index(drop=True)
    else:
        orders_sorted = orders_df.reset_index(drop=True)
    
    templates = []
    
    for idx, row in orders_sorted.iterrows():
        # Generate deterministic template_id
        entry_ts = pd.Timestamp(row["entry_ts"])
        template_id = f"{symbol}_{entry_ts.strftime('%Y%m%d_%H%M%S')}_{idx}"
        
        # Extract fields (with safe defaults)
        template = TradeTemplate(
            template_id=template_id,
            symbol=symbol,
            side=row.get("side", "BUY"),
            entry_ts=entry_ts,
            entry_price=float(row["entry_price"]),
            entry_reason=row.get("reason", "unknown"),
            exit_ts=pd.Timestamp(row["exit_ts"]) if pd.notna(row.get("exit_ts")) else None,
            exit_price=float(row["exit_price"]) if pd.notna(row.get("exit_price")) else None,
            exit_reason=row.get("exit_reason"),
            stop_loss_price=float(row["stop_loss"]) if pd.notna(row.get("stop_loss")) else None,
            take_profit_price=float(row["take_profit"]) if pd.notna(row.get("take_profit")) else None,
            atr_at_entry=float(row["atr"]) if pd.notna(row.get("atr")) else None,
        )
        
        templates.append(template)
    
    return templates
