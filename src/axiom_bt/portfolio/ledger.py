"""
Portfolio Ledger - Single Source of Truth for cash/equity tracking.

This module provides PortfolioLedger for tracking equity evolution over time
in backtests. Step 1 (dual-track): mirror existing cash accounting without
changing behavior.

Hardening: Added START entry, deterministic sequencing, and optional reporting.
Step A: Monotonic safety for multi-symbol + timestamp normalization.
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import logging
import os

logger = logging.getLogger(__name__)


@dataclass
class LedgerEntry:
    """Immutable entry in the portfolio ledger."""
    
    seq: int  # Monotonic sequence number for deterministic ordering
    ts: pd.Timestamp
    event_type: str  # START, TRADE_EXIT, FEES, etc.
    pnl: float
    fees: float
    slippage: float
    cash_before: float
    cash_after: float
    equity_before: float
    equity_after: float
    meta: Optional[dict] = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure timestamp is pandas Timestamp and tz-aware (UTC normalized)."""
        if not isinstance(self.ts, pd.Timestamp):
            self.ts = pd.Timestamp(self.ts)
        
        # Step A2: Timestamp normalization with evidence tracking
        ts_was_naive = False
        if self.ts.tz is None:
            ts_was_naive = True
            # Check if strict mode is enabled
            if os.getenv("AXIOM_BT_LEDGER_STRICT_TIME") == "1":
                raise ValueError(
                    f"AXIOM_BT_LEDGER_STRICT_TIME=1: Naive timestamp not allowed. "
                    f"Received: {self.ts}"
                )
            # Default: auto-convert to UTC with warning
            logger.warning(
                f"Portfolio ledger received naive timestamp {self.ts}, "
                f"auto-converting to UTC. Set timezone explicitly to avoid this warning."
            )
            self.ts = self.ts.tz_localize("UTC")
        
        # Normalize to UTC for consistent comparisons
        if str(self.ts.tz) != "UTC":
            self.ts = self.ts.tz_convert("UTC")
        
        # Store evidence if timestamp was naive
        if ts_was_naive and "ts_was_naive" not in self.meta:
            self.meta["ts_was_naive"] = True


class PortfolioLedger:
    """
    Portfolio cash/equity ledger for backtest accounting.
    
    Step 1 (Dual-Track): This class mirrors the existing `cash += pnl` logic
    in replay_engine.py but provides a centralized, auditable ledger.
    
    Hardening additions:
    - START entry created at initialization
    - Sequence numbers for deterministic ordering
    - cash_before/cash_after for full evidence trail
    - Optional monotonic timestamp enforcement
    
    Future steps will use this for compound sizing.
    """
    
    def __init__(
        self, 
        initial_cash: float,
        start_ts: Optional[pd.Timestamp] = None,
        enforce_monotonic: bool = True
    ):
        """
        Initialize ledger with starting cash.
        
        Args:
            initial_cash: Starting equity in dollars
            start_ts: Optional start timestamp (defaults to pd.Timestamp.min with UTC)
            enforce_monotonic: If True, raise error on non-monotonic timestamps
        """
        self._initial_cash = float(initial_cash)
        self._cash = float(initial_cash)
        self._equity = float(initial_cash)
        self._peak_equity = float(initial_cash)
        self._seq = 0
        self._entries: list[LedgerEntry] = []
        self._enforce_monotonic = enforce_monotonic
        self._last_ts: Optional[pd.Timestamp] = None
        
        # Create START entry
        if start_ts is None:
            start_ts = pd.Timestamp.min.tz_localize("UTC")
        elif start_ts.tz is None:
            start_ts = start_ts.tz_localize("UTC")
        
        self._add_entry(
            ts=start_ts,
            event_type="START",
            pnl=0.0,
            fees=0.0,
            slippage=0.0,
            cash_before=initial_cash,
            cash_after=initial_cash,
            equity_before=initial_cash,
            equity_after=initial_cash,
            meta={"note": "Initial portfolio state"}
        )
    
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
    
    @property
    def entries(self) -> list[LedgerEntry]:
        """All ledger entries (read-only)."""
        return self._entries.copy()
    
    def _add_entry(
        self,
        ts: pd.Timestamp,
        event_type: str,
        pnl: float,
        fees: float,
        slippage: float,
        cash_before: float,
        cash_after: float,
        equity_before: float,
        equity_after: float,
        meta: Optional[dict]
    ) -> None:
        """Internal: Add entry with timestamp validation."""
        # Enforce monotonic if enabled
        if self._enforce_monotonic and self._last_ts is not None:
            if ts < self._last_ts:
                raise ValueError(
                    f"Non-monotonic timestamp: {ts} < {self._last_ts}. "
                    "Ledger requires monotonic timestamps (or set enforce_monotonic=False)"
                )
        
        entry = LedgerEntry(
            seq=self._seq,
            ts=ts,
            event_type=event_type,
            pnl=pnl,
            fees=fees,
            slippage=slippage,
            cash_before=cash_before,
            cash_after=cash_after,
            equity_before=equity_before,
            equity_after=equity_after,
            meta=meta or {}
        )
        self._entries.append(entry)
        self._seq += 1
        self._last_ts = ts
    
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
        # Capture state before update
        cash_before = self._cash
        equity_before = self._equity
        
        # Update cash (mirrors: cash += pnl in replay_engine.py:368)
        self._cash += pnl
        
        # For Step 1: equity == cash (no open positions)
        self._equity = self._cash
        
        # Track peak
        if self._equity > self._peak_equity:
            self._peak_equity = self._equity
        
        # Record entry with before/after states
        self._add_entry(
            ts=exit_ts,
            event_type="TRADE_EXIT",
            pnl=pnl,
            fees=fees,
            slippage=slippage,
            cash_before=cash_before,
            cash_after=self._cash,
            equity_before=equity_before,
            equity_after=self._equity,
            meta=meta
        )
    
    def to_frame(self) -> pd.DataFrame:
        """
        Export ledger as DataFrame.
        
        Returns:
            DataFrame with columns: seq, ts, event_type, pnl, fees, slippage,
                                   cash_before, cash_after, equity_before, equity_after
        """
        if not self._entries:
            # Should not happen (START entry always exists)
            return pd.DataFrame()
        
        rows = []
        for entry in self._entries:
            rows.append({
                "seq": entry.seq,
                "ts": entry.ts,
                "event_type": entry.event_type,
                "pnl": entry.pnl,
                "fees": entry.fees,
                "slippage": entry.slippage,
                "cash_before": entry.cash_before,
                "cash_after": entry.cash_after,
                "equity_before": entry.equity_before,
                "equity_after": entry.equity_after
            })
        
        df = pd.DataFrame(rows)
        # Sort by ts, then seq (should already be ordered, but explicit)
        df = df.sort_values(["ts", "seq"]).reset_index(drop=True)
        return df
    
    def summary(self) -> dict:
        """
        Get portfolio summary statistics.
        
        Returns:
            Dict with initial_cash, final_cash, total_pnl, total_fees, etc.
        """
        if len(self._entries) <= 1:  # Only START entry
            return {
                "initial_cash": self._initial_cash,
                "final_cash": self._initial_cash,
                "total_pnl": 0.0,
                "total_fees": 0.0,
                "total_slippage": 0.0,
                "peak_equity": self._initial_cash,
                "num_events": 0
            }
        
        # Sum all non-START entries
        trade_entries = [e for e in self._entries if e.event_type != "START"]
        total_pnl = sum(e.pnl for e in trade_entries)
        total_fees = sum(e.fees for e in trade_entries)
        total_slippage = sum(e.slippage for e in trade_entries)
        
        return {
            "initial_cash": self._initial_cash,
            "final_cash": self._cash,
            "total_pnl": total_pnl,
            "total_fees": total_fees,
            "total_slippage": total_slippage,
            "peak_equity": self._peak_equity,
            "num_events": len(trade_entries)
        }
    
    def __repr__(self) -> str:
        return (
            f"PortfolioLedger(initial={self._initial_cash:.2f}, "
            f"current={self._equity:.2f}, entries={len(self._entries)}, seq={self._seq})"
        )

