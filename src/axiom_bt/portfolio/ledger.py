"""
Portfolio Ledger - Single Source of Truth for cash/equity tracking.

This module provides PortfolioLedger for tracking equity evolution over time
in backtests. Step 1 (dual-track): mirror existing cash accounting without
changing behavior.
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class LedgerEntry:
    """Immutable entry in the portfolio ledger."""
    
    ts: pd.Timestamp
    pnl: float
    fees: float
    slippage: float
    cash_after: float
    equity_after: float
    meta: Optional[dict] = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure timestamp is pandas Timestamp."""
        if not isinstance(self.ts, pd.Timestamp):
            self.ts = pd.Timestamp(self.ts)


class PortfolioLedger:
    """
    Portfolio cash/equity ledger for backtest accounting.
    
    Step 1 (Dual-Track): This class mirrors the existing `cash += pnl` logic
    in replay_engine.py but provides a centralized, auditable ledger.
    
    Future steps will use this for compound sizing.
    """
    
    def __init__(self, initial_cash: float):
        """
        Initialize ledger with starting cash.
        
        Args:
            initial_cash: Starting equity in dollars
        """
        self._initial_cash = float(initial_cash)
        self._cash = float(initial_cash)
        self._equity = float(initial_cash)
        self._peak_equity = float(initial_cash)
        self._entries: list[LedgerEntry] = []
    
    @property
    def cash(self) -> float:
        """Current cash (same as equity in Step 1)."""
        return self._cash
    
    @property
    def equity(self) -> float:
        """Current equity (cash + positions; just cash in Step 1)."""
        return self._equity
    
    @property
    def peak_equity(self) -> float:
        """Peak equity reached."""
        return self._peak_equity
    
    @property
    def initial_cash(self) -> float:
        """Initial cash at start."""
        return self._initial_cash
    
    def apply_trade(
        self,
        exit_ts: pd.Timestamp,
        pnl: float,
        fees: float = 0.0,
        slippage: float = 0.0,
        meta: Optional[dict] = None
    ) -> None:
        """
        Apply a closed trade to the ledger.
        
        Args:
            exit_ts: Timestamp of trade exit
            pnl: Profit/loss (positive or negative)
            fees: Total fees paid
            slippage: Total slippage cost
            meta: Optional metadata (symbol, side, etc.)
        """
        # Update cash (mirrors: cash += pnl in replay_engine.py:368)
        self._cash += pnl
        
        # For Step 1: equity == cash (no open positions)
        self._equity = self._cash
        
        # Track peak
        if self._equity > self._peak_equity:
            self._peak_equity = self._equity
        
        # Record entry
        entry = LedgerEntry(
            ts=exit_ts,
            pnl=pnl,
            fees=fees,
            slippage=slippage,
            cash_after=self._cash,
            equity_after=self._equity,
            meta=meta or {}
        )
        self._entries.append(entry)
    
    def to_frame(self) -> pd.DataFrame:
        """
        Export ledger as DataFrame.
        
        Returns:
            DataFrame with columns: ts, equity, cash, pnl, fees, slippage
        """
        if not self._entries:
            # Empty ledger - return baseline row
            return pd.DataFrame([{
                "ts": pd.Timestamp.min,
                "equity": self._initial_cash,
                "cash": self._initial_cash,
                "pnl": 0.0,
                "fees": 0.0,
                "slippage": 0.0
            }])
        
        rows = []
        for entry in self._entries:
            rows.append({
                "ts": entry.ts,
                "equity": entry.equity_after,
                "cash": entry.cash_after,
                "pnl": entry.pnl,
                "fees": entry.fees,
                "slippage": entry.slippage
            })
        
        df = pd.DataFrame(rows)
        return df.sort_values("ts").reset_index(drop=True)
    
    def __repr__(self) -> str:
        return (
            f"PortfolioLedger(initial={self._initial_cash:.2f}, "
            f"current={self._equity:.2f}, entries={len(self._entries)})"
        )
