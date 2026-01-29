"""SignalFrame factory: build + validate via decoupled strategy registry."""

from __future__ import annotations

import logging
from typing import Dict, Tuple

import pandas as pd

from axiom_bt.contracts.signal_frame_contract_v1 import validate_signal_frame_v1, SignalFrameSchemaV1
from strategies.registry import get_strategy

logger = logging.getLogger(__name__)


def build_signal_frame(
    bars: pd.DataFrame,
    strategy_id: str,
    strategy_version: str,
    strategy_params: Dict,
    *,
    hook_registry=None,
) -> Tuple[pd.DataFrame, SignalFrameSchemaV1]:
    """Build and validate SignalFrame via strategy discovery.

    Args:
        bars: OHLCV DataFrame (timestamp, open, high, low, close, volume).
        strategy_id: Strategy identifier.
        strategy_version: Version string.
        strategy_params: Parameters (passed to strategy builder).
        hook_registry: Deprecated (ignored for backward compatibility).

    Returns:
        Tuple of (Validated SignalFrame DataFrame, SignalFrameSchemaV1).

    Raises:
        ValueError: if strategy_id unknown or validation fails.
    """
    # Decoupled strategy dispatch
    try:
        plugin = get_strategy(strategy_id)
    except KeyError as exc:
        raise ValueError(f"Unknown strategy_id: {strategy_id}") from exc

    schema = plugin.get_schema(strategy_version)
    
    # We pass strategy_version in params to match expectations in some strategies
    params = {**strategy_params, "strategy_version": strategy_version}
    
    df = plugin.extend_signal_frame(bars, params)

    # Normalize all datetime64[ns, UTC] columns to tz-aware UTC before validation.
    for col in schema.all_columns():
        if not col.dtype.startswith("datetime64"):
            continue
        if col.name not in df.columns:
            continue
        df[col.name] = pd.to_datetime(
            df[col.name],
            utc=True,
            errors="coerce" if col.nullable else "raise",
        )

    validate_signal_frame_v1(df, schema)

    logger.info(
        "actions: signal_frame_built strategy_id=%s version=%s rows=%d cols=%d",
        strategy_id,
        strategy_version,
        len(df),
        df.shape[1],
    )
    return df, schema
