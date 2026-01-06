"""
Event Engine Skeleton - Compound Sizing Phase 2 (F1-C3)

Minimal, deterministic event processing engine.
Processes events in order but does NOT implement trade logic yet.

This is a skeleton to prove ordering/determinism before adding complexity.

NOT implemented in this skeleton:
- Qty calculation (comes in F2)
- Equity tracking (comes in F2)
- Fees/slippage (comes in F2)
- Position management (comes in F2)
- Integration with runner (comes in F1-C4)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Sequence
import pandas as pd

from axiom_bt.event_ordering import TradeEvent, EventKind, order_events


@dataclass(frozen=True)
class ProcessedEvent:
    """
    Result of processing a single event.
    
    F2-C1: Extended with qty and cash tracking for actual execution.
    """
    timestamp: pd.Timestamp
    symbol: str
    kind: EventKind
    template_id: str
    side: str
    status: Literal["accepted", "rejected", "skipped", "filled"] = "accepted"
    reason: str = ""  # Optional reason (e.g., why rejected)
    
    # F2-C1: Execution details
    qty: float = 0.0  # Quantity filled (0 if rejected)
    price: float = 0.0  # Fill price
    cash_after: float = 0.0  # Cash balance after this event
    
    def to_dict(self) -> dict:
        """Export as dict for testing."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "kind": self.kind.name,
            "template_id": self.template_id,
            "side": self.side,
            "status": self.status,
            "reason": self.reason,
            "qty": self.qty,
            "price": self.price,
            "cash_after": self.cash_after,
        }


@dataclass
class Position:
    """Simple position tracker for cash-only equity."""
    symbol: str
    qty: float  # Positive for long, negative for short (but F2-C1 only long)
    avg_price: float = 0.0  # Average entry price (optional for F2-C1)


@dataclass
class CashEquityTracker:
    """
    F2-C1: Cash-only equity tracker.
    
    Equity = cash balance only (no mark-to-market of open positions).
    Updates cash on fills:
    - BUY: cash -= (qty * price)
    - SELL: cash += (qty * price)
    """
    cash: float
    positions: dict = field(default_factory=dict)  # symbol -> Position
    
    def equity(self) -> float:
        """Cash-only equity (F2-C1: ignores MTM of positions)."""
        return self.cash
    
    def can_afford(self, cost: float) -> bool:
        """Check if we have enough cash."""
        return self.cash >= cost
    
    def get_position_qty(self, symbol: str) -> float:
        """Get current position quantity."""
        pos = self.positions.get(symbol)
        return pos.qty if pos else 0.0
    
    def apply_fill(self, side: str, symbol: str, qty: float, price: float):
        """
        Apply a fill to the tracker (updates cash and positions).
        
        Args:
            side: "BUY" or "SELL"
            symbol: Symbol
            qty: Quantity (positive)
            price: Fill price
        """
        if side == "BUY":
            # Cash outflow
            cost = qty * price
            if not self.can_afford(cost):
                raise ValueError(f"Insufficient cash: need {cost}, have {self.cash}")
            
            self.cash -= cost
            
            # Update position
            if symbol not in self.positions:
                self.positions[symbol] = Position(symbol=symbol, qty=qty, avg_price=price)
            else:
                pos = self.positions[symbol]
                # Accumulate (simple for F2-C1, no avg price recalc yet)
                object.__setattr__(pos, "qty", pos.qty + qty)
        
        elif side == "SELL":
            # Cash inflow
            proceeds = qty * price
            self.cash += proceeds
            
            # Update position
            if symbol not in self.positions:
                # Selling without position (should be rejected upstream, but handle)
                raise ValueError(f"Cannot SELL {symbol}: no position")
            
            pos = self.positions[symbol]
            new_qty = pos.qty - qty
            
            if new_qty < 0:
                raise ValueError(f"Cannot SELL {qty} of {symbol}: only have {pos.qty}")
            
            if new_qty == 0:
                # Position closed
                del self.positions[symbol]
            else:
                object.__setattr__(pos, "qty", new_qty)



@dataclass
class EngineResult:
    """
    Result of event engine processing.
    
    Contains ordered events, processed results, and stats.
    Immutable after creation for determinism.
    """
    ordered_events: tuple[TradeEvent, ...]
    processed: tuple[ProcessedEvent, ...]
    stats: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure immutability after creation."""
        # Convert to tuples if needed
        if isinstance(self.ordered_events, list):
            object.__setattr__(self, "ordered_events", tuple(self.ordered_events))
        if isinstance(self.processed, list):
            object.__setattr__(self, "processed", tuple(self.processed))
    
    @property
    def num_events(self) -> int:
        """Total number of events processed."""
        return len(self.ordered_events)
    
    @property
    def num_entries(self) -> int:
        """Number of ENTRY events."""
        return self.stats.get("num_entries", 0)
    
    @property
    def num_exits(self) -> int:
        """Number of EXIT events."""
        return self.stats.get("num_exits", 0)


class EventEngine:
    """
    Deterministic event processing engine (skeleton).
    
    Processes events in A1-compliant order but does NOT implement
    actual trade logic yet. This is a minimal skeleton to prove
    ordering and determinism before adding complexity.
    
    Usage:
        engine = EventEngine()
        result = engine.process(events)
        assert result.num_entries == 5
    """
    
    def __init__(self, *, initial_cash: float = 10000.0, validate_ordering: bool = True, fixed_qty: float = 0.0):
        """
        Initialize event engine.
        
        Args:
            initial_cash: Starting cash balance (F2-C1)
            validate_ordering: If True, validates A1 ordering after sorting
            fixed_qty: If > 0, use fixed qty for all entries (F2-C1 policy)
        """
        self.validate_ordering = validate_ordering
        self.fixed_qty = fixed_qty  # F2-C1: simple qty policy
    
    def process(self, events: Sequence[TradeEvent], initial_cash: float = 10000.0) -> EngineResult:
        """
        Process events deterministically with F2-C1 cash-only execution.
        
        Steps:
        1. Order events using order_events() (A1-compliant)
        2. Process each event: calculate qty at entry, apply fills, update cash
        3. Collect stats
        4. Return EngineResult
        
        Args:
            events: Sequence of TradeEvent objects (can be unsorted)
            initial_cash: Starting cash balance
            
        Returns:
            EngineResult with ordered events, processed results, stats
            
        Raises:
            ValueError: If ordering validation fails
        """
        if not events:
            return EngineResult(
                ordered_events=tuple(),
                processed=tuple(),
                stats={"num_entries": 0, "num_exits": 0, "num_total": 0, "final_cash": initial_cash}
            )
        
        # Step 1: Order events (A1-compliant)
        ordered = order_events(events)
        
        # Optional validation
        if self.validate_ordering:
            self._validate_ordering(ordered)
        
        # F2-C1: Initialize cash equity tracker
        tracker = CashEquityTracker(cash=initial_cash)
        
        # Step 2: Process each event with qty calculation and fills
        processed = []
        for event in ordered:
            if event.kind == EventKind.ENTRY:
                # F2-C1: Calculate qty at entry
                qty = self._calculate_qty(tracker, event)
                
                if qty < 1:
                    # Reject: insufficient cash or qty too small
                    processed_event = ProcessedEvent(
                        timestamp=event.timestamp,
                        symbol=event.symbol,
                        kind=event.kind,
                        template_id=event.template_id,
                        side=event.side,
                        status="rejected",
                        reason="insufficient_cash_for_min_qty",
                        qty=0.0,
                        price=event.price,
                        cash_after=tracker.cash,
                    )
                else:
                    # Fill entry
                    try:
                        tracker.apply_fill(event.side, event.symbol, qty, event.price)
                        processed_event = ProcessedEvent(
                            timestamp=event.timestamp,
                            symbol=event.symbol,
                            kind=event.kind,
                            template_id=event.template_id,
                            side=event.side,
                            status="filled",
                            reason="",
                            qty=qty,
                            price=event.price,
                            cash_after=tracker.cash,
                        )
                    except ValueError as e:
                        # Apply_fill raised error (shouldn't happen for ENTRY if qty calc correct)
                        processed_event = ProcessedEvent(
                            timestamp=event.timestamp,
                            symbol=event.symbol,
                            kind=event.kind,
                            template_id=event.template_id,
                            side=event.side,
                            status="rejected",
                            reason=str(e),
                            qty=0.0,
                            price=event.price,
                            cash_after=tracker.cash,
                        )
            
            elif event.kind == EventKind.EXIT:
                # F2-C1: Exit uses existing position qty
                position_qty = tracker.get_position_qty(event.symbol)
                
                if position_qty <= 0:
                    # Reject: no position to exit
                    processed_event = ProcessedEvent(
                        timestamp=event.timestamp,
                        symbol=event.symbol,
                        kind=event.kind,
                        template_id=event.template_id,
                        side=event.side,
                        status="rejected",
                        reason="no_position_to_exit",
                        qty=0.0,
                        price=event.price,
                        cash_after=tracker.cash,
                    )
                else:
                    # Fill exit
                    try:
                        tracker.apply_fill(event.side, event.symbol, position_qty, event.price)
                        processed_event = ProcessedEvent(
                            timestamp=event.timestamp,
                            symbol=event.symbol,
                            kind=event.kind,
                            template_id=event.template_id,
                            side=event.side,
                            status="filled",
                            reason="",
                            qty=position_qty,
                            price=event.price,
                            cash_after=tracker.cash,
                        )
                    except ValueError as e:
                        processed_event = ProcessedEvent(
                            timestamp=event.timestamp,
                            symbol=event.symbol,
                            kind=event.kind,
                            template_id=event.template_id,
                            side=event.side,
                            status="rejected",
                            reason=str(e),
                            qty=0.0,
                            price=event.price,
                            cash_after=tracker.cash,
                        )
            
            processed.append(processed_event)
        
        # Step 3: Collect stats
        stats = self._compute_stats(ordered)
        stats["final_cash"] = tracker.cash
        stats["final_equity"] = tracker.equity()
        
        # Step 4: Return immutable result
        return EngineResult(
            ordered_events=tuple(ordered),
            processed=tuple(processed),
            stats=stats,
        )
    
    def _calculate_qty(self, tracker: CashEquityTracker, event: TradeEvent) -> float:
        """
        F2-C1: Calculate qty at entry time.
        
        Policy:
        - If self.fixed_qty > 0: use fixed_qty
        - Else: floor(cash / price)
        
        Returns:
            Quantity (integer, floored)
        """
        if self.fixed_qty > 0:
            return self.fixed_qty
        
        # Default policy: floor(cash / price)
        cash = tracker.cash
        price = event.price
        
        if price <= 0:
            return 0.0
        
        qty = int(cash // price)  # Floor division
        return float(qty)

    
    def _validate_ordering(self, events: Sequence[TradeEvent]) -> None:
        """
        Validate that events follow A1 ordering rules.
        
        Raises:
            ValueError: If ordering violation detected
        """
        if not events:
            return
        
        # Check A1: EXIT before ENTRY at same timestamp
        current_ts = None
        seen_entry = False
        
        for event in events:
            if event.timestamp != current_ts:
                current_ts = event.timestamp
                seen_entry = False
            
            if event.kind == EventKind.EXIT:
                if seen_entry:
                    raise ValueError(
                        f"A1 VIOLATION in engine: EXIT after ENTRY at {current_ts}"
                    )
            elif event.kind == EventKind.ENTRY:
                seen_entry = True
    
    def _compute_stats(self, events: Sequence[TradeEvent]) -> dict:
        """
        Compute stats from ordered events.
        
        Returns:
            Dict with counts by kind, symbols, etc.
        """
        num_entries = sum(1 for e in events if e.kind == EventKind.ENTRY)
        num_exits = sum(1 for e in events if e.kind == EventKind.EXIT)
        
        symbols = set(e.symbol for e in events)
        
        return {
            "num_total": len(events),
            "num_entries": num_entries,
            "num_exits": num_exits,
            "num_symbols": len(symbols),
            "symbols": sorted(symbols),
        }
