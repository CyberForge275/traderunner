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
    
    Minimal representation for skeleton - no trade details yet.
    """
    timestamp: pd.Timestamp
    symbol: str
    kind: EventKind
    template_id: str
    side: str
    status: Literal["accepted", "rejected", "skipped"] = "accepted"
    reason: str = ""  # Optional reason (e.g., why rejected)
    
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
        }


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
    
    def __init__(self, *, validate_ordering: bool = True):
        """
        Initialize event engine.
        
        Args:
            validate_ordering: If True, validates A1 ordering after sorting
        """
        self.validate_ordering = validate_ordering
    
    def process(self, events: Sequence[TradeEvent]) -> EngineResult:
        """
        Process events deterministically.
        
        Steps:
        1. Order events using order_events() (A1-compliant)
        2. Process each event (currently no-op)
        3. Collect stats
        4. Return EngineResult
        
        Args:
            events: Sequence of TradeEvent objects (can be unsorted)
            
        Returns:
            EngineResult with ordered events, processed results, stats
            
        Raises:
            ValueError: If ordering validation fails
        """
        if not events:
            return EngineResult(
                ordered_events=tuple(),
                processed=tuple(),
                stats={"num_entries": 0, "num_exits": 0, "num_total": 0}
            )
        
        # Step 1: Order events (A1-compliant)
        ordered = order_events(events)
        
        # Optional validation
        if self.validate_ordering:
            self._validate_ordering(ordered)
        
        # Step 2: Process each event (skeleton - just create ProcessedEvent)
        processed = []
        for event in ordered:
            # Skeleton processing - just accept everything
            processed_event = ProcessedEvent(
                timestamp=event.timestamp,
                symbol=event.symbol,
                kind=event.kind,
                template_id=event.template_id,
                side=event.side,
                status="accepted",
                reason="",
            )
            processed.append(processed_event)
        
        # Step 3: Collect stats
        stats = self._compute_stats(ordered)
        
        # Step 4: Return immutable result
        return EngineResult(
            ordered_events=tuple(ordered),
            processed=tuple(processed),
            stats=stats,
        )
    
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
