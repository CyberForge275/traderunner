"""
P3-C1a: InsideBar → TradeTemplates Adapter

Converts InsideBar RawSignal objects to TradeTemplate format for compound sizing.

NOTE: RawSignals contain entry + SL/TP levels, but NO exit timestamps.
Therefore, generated templates will have entry info only (exit_ts=None).
Exit handling will be added in future phases (e.g., when integrating fill simulation).
"""

from __future__ import annotations
from typing import List, Any, Union
import hashlib
import pandas as pd

from axiom_bt.trade_templates import TradeTemplate


def inside_bar_to_trade_templates(
    signals: Union[List[Any], Any]
) -> List[TradeTemplate]:
    """
    Convert InsideBar RawSignal objects to TradeTemplates.
    
    Args:
        signals: List of RawSignal objects or list[dict] or DataFrame-like
            Expected fields (with aliases):
            - timestamp / entry_ts / entry_time
            - side (BUY/SELL)
            - entry_price / entry
            - symbol (optional, defaults to "UNKNOWN")
            - metadata dict (optional)
            
    Returns:
        List of TradeTemplate objects (sorted for determinism)
        
    Raises:
        ValueError: If required fields missing or invalid
        
    Notes:
        - template_id generated deterministically from hash(symbol|entry_ts|side)
        - Output sorted by (entry_ts, symbol, side, template_id) for shuffle-invariance
        - Empty input → empty output (valid)
        - Exit fields (exit_ts, exit_price) set to None (signals don't have exit info)
    """
    if not signals:
        return []
    
    # Handle DataFrame-like input
    if hasattr(signals, 'to_dict') and callable(signals.to_dict):
        # Convert DataFrame to list of dicts
        signals = signals.to_dict('records')
    
    templates = []
    
    for signal in signals:
        # Handle both object attributes and dict keys
        if hasattr(signal, '__dict__'):
            # Object (like RawSignal)
            timestamp = getattr(signal, 'timestamp', None) or getattr(signal, 'entry_ts', None)
            side = getattr(signal, 'side', None)
            entry_price = getattr(signal, 'entry_price', None) or getattr(signal, 'entry', None)
            symbol = getattr(signal, 'symbol', None)
            metadata = getattr(signal, 'metadata', {})
        else:
            # Dict
            timestamp = signal.get('timestamp') or signal.get('entry_ts') or signal.get('entry_time')
            side = signal.get('side') or signal.get('direction')
            entry_price = signal.get('entry_price') or signal.get('entry') or signal.get('entry_px')
            symbol = signal.get('symbol') or signal.get('ticker')
            metadata = signal.get('metadata', {})
        
        # Get symbol from metadata if not at top level
        if not symbol and metadata:
            symbol = metadata.get('symbol')
        
        # Default symbol if still missing
        if not symbol:
            symbol = "UNKNOWN"
        
        # Validate timestamp
        if timestamp is None:
            raise ValueError(f"Signal missing timestamp/entry_ts: {signal}")
        
        # Convert to pd.Timestamp if needed
        if not isinstance(timestamp, pd.Timestamp):
            timestamp = pd.to_datetime(timestamp)
        
        # Normalize side
        if side:
            side_upper = str(side).upper()
            if side_upper in ['BUY', 'LONG', '1', '+1']:
                side = 'BUY'
            elif side_upper in ['SELL', 'SHORT', '-1']:
                side = 'SELL'
            else:
                raise ValueError(f"Invalid side: {side} (must be BUY/SELL/LONG/SHORT)")
        else:
            raise ValueError(f"Signal missing side: {signal}")
        
        # Validate entry price
        if not entry_price or entry_price <= 0:
            raise ValueError(f"Signal missing or invalid entry_price: {signal}")
        
        # Generate deterministic template_id
        # Use hash of symbol|timestamp_iso|side for stability
        ts_iso = timestamp.isoformat()
        hash_input = f"{symbol}|{ts_iso}|{side}"
        hash_bytes = hashlib.sha1(hash_input.encode('utf-8')).hexdigest()
        template_id = f"ib_{hash_bytes[:12]}"  # 12-char hex
        
        # Extract entry reason from metadata if available
        entry_reason = metadata.get('entry_reason', 'inside_bar_breakout')
        
        # Create TradeTemplate (entry only, no exit yet)
        template = TradeTemplate(
            template_id=template_id,
            symbol=symbol,
            side=side,
            entry_ts=timestamp,
            entry_price=float(entry_price),
            entry_reason=entry_reason,
            exit_ts=None,  # No exit info in RawSignal
            exit_price=None,
            exit_reason=None,
        )
        
        templates.append(template)
    
    # Sort for deterministic output (shuffle-invariant)
    templates.sort(key=lambda t: (t.entry_ts, t.symbol, t.side, t.template_id))
    
    return templates
