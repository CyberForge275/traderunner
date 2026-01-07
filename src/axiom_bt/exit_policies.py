"""
P3-C3: Exit policies for TradeTemplates

Provides minimal deterministic exit logic to complete entry-only templates.
This allows EventEngine to process full ENTRY+EXIT event pairs.

Current implementation: Time-based exit (hold for N bars).
Future: SL/TP-based exits, session-end exits, etc.
"""

from __future__ import annotations
from typing import List
import pandas as pd

from axiom_bt.trade_templates import TradeTemplate


def apply_time_exit(
    templates: List[TradeTemplate],
    bars_df: pd.DataFrame,
    hold_bars: int = 1
) -> List[TradeTemplate]:
    """
    Add time-based exit to entry-only templates.
    
    For each template:
    - Find bar index containing entry_ts
    - Exit at entry_idx + hold_bars (clamped to last bar)
    - exit_price = close price at exit bar
    - exit_reason = "time_exit_{hold_bars}"
    
    Args:
        templates: List of TradeTemplate objects (may have exits already)
        bars_df: DataFrame with DatetimeIndex and 'close' column
        hold_bars: Number of bars to hold position (default: 1)
        
    Returns:
        List of TradeTemplate objects with exit info added where missing
        
    Notes:
        - Templates with existing exit info are unchanged
        - If entry_ts not in index: uses next bar (searchsorted)
        - If no next bar exists:  template unchanged (entry-only)
        - Deterministic: same inputs → same outputs
        - No I/O, pure computation
    """
    if bars_df is None or bars_df.empty:
        # No bars data → return templates unchanged
        return templates
    
    if not isinstance(bars_df.index, pd.DatetimeIndex):
        # Index not datetime → can't match timestamps
        return templates
    
    updated_templates = []
    
    for template in templates:
        # Skip if already has exit
        if template.exit_ts is not None and template.exit_price is not None:
            updated_templates.append(template)
            continue
        
        # Find entry bar index
        entry_ts = template.entry_ts
        
        # Use searchsorted to find position (handles exact match or next bar)
        idx_pos = bars_df.index.searchsorted(entry_ts, side='left')
        
        # Check if entry is beyond last bar
        if idx_pos >= len(bars_df):
            # No bars after entry → keep entry-only
            updated_templates.append(template)
            continue
        
        # Calculate exit index (clamp to last bar)
        exit_idx = min(idx_pos + hold_bars, len(bars_df) - 1)
        
        # Get exit timestamp and price
        exit_ts = bars_df.index[exit_idx]
        exit_price = float(bars_df.iloc[exit_idx]['close'])
        
        # Create updated template with exit
        updated_template = TradeTemplate(
            template_id=template.template_id,
            symbol=template.symbol,
            side=template.side,
            entry_ts=template.entry_ts,
            entry_price=template.entry_price,
            entry_reason=template.entry_reason,
            exit_ts=exit_ts,
            exit_price=exit_price,
            exit_reason=f"time_exit_{hold_bars}",
        )
        
        updated_templates.append(updated_template)
    
    return updated_templates
