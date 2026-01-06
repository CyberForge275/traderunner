"""
F2-C3: Template to Event Extraction

Converts TradeTemplate → TradeEvent pairs (ENTRY + EXIT).

Deterministic, validates prices/timestamps, supports A1 ordering.
"""

from __future__ import annotations
from typing import Sequence
import pandas as pd

from axiom_bt.trade_templates import TradeTemplate
from axiom_bt.event_ordering import TradeEvent, EventKind


def templates_to_events(templates: Sequence[TradeTemplate]) -> list[TradeEvent]:
    """
    F2-C3: Extract TradeEvent pairs from TradeTemplates.
    
    Maps each template to 2 events: ENTRY + EXIT
    
    Args:
        templates: Sequence of TradeTemplate objects
        
    Returns:
        List of TradeEvent objects (2 per template)
        
    Raises:
        ValueError: If required fields missing or invalid
    """
    if not templates:
        return []
    
    events = []
    
    for template in templates:
        # Validate required fields
        if template.entry_ts is None:
            raise ValueError(f"Template {template.template_id} missing entry_ts")
        
        if template.entry_price <= 0:
            raise ValueError(f"Template {template.template_id} has invalid entry_price: {template.entry_price}")
        
        # Create ENTRY event
        entry_event = TradeEvent(
            timestamp=template.entry_ts,
            kind=EventKind.ENTRY,
            symbol=template.symbol,
            template_id=template.template_id,
            side=template.side,
            price=template.entry_price,
        )
        events.append(entry_event)
        
        # Create EXIT event (if exit info available)
        if template.exit_ts is not None:
            if template.exit_price is None or template.exit_price <= 0:
                raise ValueError(
                    f"Template {template.template_id} has exit_ts but invalid exit_price"
                )
            
            # Opposite side for exit
            exit_side = "SELL" if template.side == "BUY" else "BUY"
            
            exit_event = TradeEvent(
                timestamp=template.exit_ts,
                kind=EventKind.EXIT,
                symbol=template.symbol,
                template_id=template.template_id,
                side=exit_side,
                price=template.exit_price,
            )
            events.append(exit_event)
    
    return events
