"""Helper wrapper for building broker-ready orders from strategy signals.

This module provides a thin, adapter-friendly wrapper around the canonical
`_build_inside_bar_orders` function used by the CLI. It avoids pulling
argparse/CLI concerns into higher layers and exposes a simple
`build_orders_for_backtest` function for programmatic use.
"""

from __future__ import annotations

import argparse
import logging
from typing import Dict, List

import pandas as pd

from trade.cli_export_orders import _build_inside_bar_orders, Session
from trade.validity import calculate_validity_window
from strategies.inside_bar.config import SessionFilter

logger = logging.getLogger(__name__)


def _detect_timestamp_column(signals: pd.DataFrame) -> str:
    """Return the timestamp column name used for signal timestamps.

    Prefers ``"timestamp"`` when present, otherwise falls back to ``"ts"``.
    Raises ``ValueError`` if neither column exists so callers get an
    explicit and debuggable failure instead of a silent misalignment.
    """

    columns = list(signals.columns)
    if "timestamp" in signals.columns:
        return "timestamp"
    if "ts" in signals.columns:
        return "ts"
    raise ValueError(
        f"Signals DataFrame must contain a 'timestamp' or 'ts' column; got columns={columns}"
    )


def _build_sessions(strategy_params: Dict, market_tz: str) -> List[Session]:  # noqa: ARG001
    """Construct trading sessions from strategy parameters.

    If ``session_filter`` is provided as a list of strings like
    ``["09:30-16:00", "16:00-22:00"]``, these windows are converted into
    :class:`Session` objects. Otherwise a single regular-trading-hours
    session (09:30–16:00) is used.

    The ``market_tz`` argument is accepted for future use should we need
    to derive session windows dynamically; it is currently unused.
    """

    raw = strategy_params.get("session_filter")
    sessions: List[Session] = []

    if isinstance(raw, (list, tuple)):
        for value in raw:
            if not isinstance(value, str):
                continue
            if "-" not in value:
                continue
            start, end = [token.strip() for token in value.split("-", 1)]
            if start and end:
                sessions.append(Session(start=start, end=end))

    if not sessions:
        sessions = [Session(start="09:30", end="16:00")]

    return sessions


def _build_args_from_params(strategy_params: Dict, market_tz: str) -> argparse.Namespace:
    """Create an ``argparse.Namespace`` compatible with the CLI builder.

    Only the fields actually used by ``_build_inside_bar_orders`` and its
    helpers are populated. Sensible defaults are provided so the adapter
    can be used without requiring a full CLI-style argument set.
    """

    tick_size = float(strategy_params.get("tick_size", 0.01))
    round_mode = str(strategy_params.get("round_mode", "floor"))
    expire_policy = str(strategy_params.get("expire_policy", "session_end"))

    initial_cash = float(strategy_params.get("initial_cash", 100000.0))
    risk_pct = float(strategy_params.get("risk_pct", 1.0))
    max_position_pct = float(strategy_params.get("max_position_pct", 100.0))

    sizing = str(strategy_params.get("sizing", "risk"))
    qty = float(strategy_params.get("qty", 1.0))
    min_qty = int(strategy_params.get("min_qty", 1))

    # Max notional per order; defaults to full equity at max_position_pct.
    max_notional = strategy_params.get("max_notional")
    if max_notional is None:
        max_notional = initial_cash * max_position_pct / 100.0

    args = argparse.Namespace(
        tz=market_tz,
        tick_size=tick_size,
        round_mode=round_mode,
        expire_policy=expire_policy,
        tif=str(strategy_params.get("tif", "DAY")),
        sizing=sizing,
        qty=qty,
        equity=initial_cash,
        pos_pct=max_position_pct,
        risk_pct=risk_pct,
        min_qty=min_qty,
        max_notional=max_notional,
    )

    return args


def build_orders_for_backtest(
    signals: pd.DataFrame,
    strategy_params: Dict,
    market_tz: str = "America/New_York",
) -> pd.DataFrame:
    """Convert strategy signals into broker-ready orders for backtests.

    This is a thin wrapper around :func:`_build_inside_bar_orders` that:

    - selects the appropriate timestamp column (``timestamp`` or ``ts``),
    - constructs :class:`Session` windows from ``session_filter`` (or
      defaults to a single RTH session),
    - builds a minimal ``argparse.Namespace`` with sizing and risk
      parameters derived from ``strategy_params``,
    - applies validity window validation using the new validity calculator.

    The underlying builder is responsible for detailed price rounding,
    sizing, and timestamp localization. When ``signals`` is empty, the
    function simply returns the empty orders DataFrame from the builder.
    
    Phase 5 Integration: Orders with invalid validity windows (valid_to <= valid_from)
    are now filtered out to prevent zero-fill scenarios. This is critical for
    November parity.
    """

    # Short-circuit early for the empty-frame case but still delegate to
    # the canonical builder so that the column layout stays consistent.
    ts_col = _detect_timestamp_column(signals) if not signals.empty else (
        "timestamp" if "timestamp" in signals.columns else ("ts" if "ts" in signals.columns else "timestamp")
    )

    sessions = _build_sessions(strategy_params, market_tz)
    args = _build_args_from_params(strategy_params, market_tz)

    # Build base orders using existing logic
    orders_df = _build_inside_bar_orders(signals, ts_col, sessions, args)
    
    # Phase 5: Apply validity validation (CRITICAL for fills)
    if not orders_df.empty and 'valid_from' in orders_df.columns and 'valid_to' in orders_df.columns:
        # Check for invalid windows (valid_to <= valid_from)
        invalid_mask = pd.to_datetime(orders_df['valid_to']) <= pd.to_datetime(orders_df['valid_from'])
        
        if invalid_mask.any():
            num_invalid = invalid_mask.sum()
            logger.warning(
                f"Filtered {num_invalid} orders with invalid validity windows (valid_to <= valid_from). "
                "This prevents zero-fill scenarios and ensures November parity."
            )
            
            # Log details for first few invalid orders
            for idx in orders_df[invalid_mask].head(3).index:
                row = orders_df.loc[idx]
                logger.debug(
                    f"Invalid order #{idx}: valid_from={row['valid_from']}, "
                    f"valid_to={row['valid_to']}, symbol={row.get('symbol', 'N/A')}"
                )
            
            # Filter out invalid orders
            orders_df = orders_df[~invalid_mask].copy()
            logger.info(f"Remaining valid orders: {len(orders_df)}")
    
    return orders_df
