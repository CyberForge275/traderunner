"""Helper wrapper for building broker-ready orders from strategy signals.

This module provides a thin, adapter-friendly wrapper around the canonical
`_build_inside_bar_orders` function used by the CLI. It avoids pulling
argparse/CLI concerns into higher layers and exposes a simple
`build_orders_for_backtest` function for programmatic use.
"""

from __future__ import annotations

import argparse
import logging
from typing import Dict, List, Optional

import pandas as pd

from core.settings import DEFAULT_INITIAL_CASH
from trade.cli_export_orders import _build_inside_bar_orders, Session
from trade.validity import calculate_validity_window

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
    expire_policy = str(
        strategy_params.get(
            "order_validity_policy",
            strategy_params.get("expire_policy", "session_end"),
        )
    )

    initial_cash = float(strategy_params.get("initial_cash", DEFAULT_INITIAL_CASH))
    risk_pct = float(strategy_params.get("risk_pct", 1.0))
    pos_pct = float(strategy_params.get("pos_pct", 10.0))
    max_position_pct = strategy_params.get("max_position_pct")
    if max_position_pct is None:
        logger.warning(
            "Parameter 'max_position_pct' missing from strategy_params. "
            "Using Legacy-parity default of 100.0%. "
            "Please update your strategy configuration to include this parameter."
        )
        max_position_pct = 100.0
    else:
        max_position_pct = float(max_position_pct)

    sizing = str(strategy_params.get("sizing", "risk"))
    qty = float(strategy_params.get("qty", 1.0))
    min_qty = int(strategy_params.get("min_qty", 1))

    # Max notional per order; defaults to full equity at max_position_pct.
    max_notional = strategy_params.get("max_notional")
    if max_notional is None:
        max_notional = initial_cash * max_position_pct / 100.0

    # Infer timeframe_minutes for validity calculations; default to 5 for M5.
    timeframe_minutes: int = 5
    tf_param: Optional[object] = strategy_params.get("timeframe_minutes")
    if tf_param is None:
        tf_param = strategy_params.get("timeframe") or strategy_params.get("timeframe_min")
    if isinstance(tf_param, str):
        tf_upper = tf_param.upper()
        if tf_upper.startswith("M") and tf_upper[1:].isdigit():
            timeframe_minutes = int(tf_upper[1:])
    elif isinstance(tf_param, (int, float)):
        timeframe_minutes = int(tf_param)

    validity_minutes = int(strategy_params.get("validity_minutes", 60))
    valid_from_policy = str(strategy_params.get("valid_from_policy", "signal_ts"))

    args = argparse.Namespace(
        tz=market_tz,
        tick_size=tick_size,
        round_mode=round_mode,
        expire_policy=expire_policy,
        validity_policy=expire_policy,
        validity_minutes=validity_minutes,
        valid_from_policy=valid_from_policy,
        timeframe_minutes=timeframe_minutes,
        tif=str(strategy_params.get("tif", "DAY")),
        sizing=sizing,
        qty=qty,
        equity=initial_cash,
        pos_pct=pos_pct,
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

    # Recompute validity windows using the canonical validity calculator so that
    # policies like "one_bar" take effect even when expire_policy was not set.
    if not orders_df.empty:
        session_filter = strategy_params.get("session_filter") or ["09:30-16:00"]
        session_timezone = strategy_params.get("session_timezone", market_tz)
        validity_policy = args.validity_policy
        validity_minutes = args.validity_minutes
        timeframe_minutes = args.timeframe_minutes
        valid_from_policy = args.valid_from_policy

        def _to_tz(ts_val: object) -> pd.Timestamp:
            ts = pd.to_datetime(ts_val, utc=True)
            return ts.tz_convert(session_timezone)

        new_valid_from: List[str] = []
        new_valid_to: List[str] = []

        for _, row in orders_df.iterrows():
            signal_ts = _to_tz(row["valid_from"])
            vf, vt = calculate_validity_window(
                signal_ts=signal_ts,
                timeframe_minutes=timeframe_minutes,
                session_filter=session_filter,
                session_timezone=session_timezone,
                validity_policy=validity_policy,
                validity_minutes=validity_minutes,
                valid_from_policy=valid_from_policy,
            )
            new_valid_from.append(vf.isoformat())
            new_valid_to.append(vt.isoformat())

        orders_df = orders_df.copy()
        orders_df["valid_from"] = new_valid_from
        orders_df["valid_to"] = new_valid_to

    # Phase 5: Apply validity validation (CRITICAL for fills)
    if not orders_df.empty and 'valid_from' in orders_df.columns and 'valid_to' in orders_df.columns:
        # Check for invalid windows (valid_to <= valid_from)
        invalid_mask = (
            pd.to_datetime(orders_df['valid_to'], utc=True)
            <= pd.to_datetime(orders_df['valid_from'], utc=True)
        )

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

    # Add timezone debug columns for easier debugging
    if not orders_df.empty and 'valid_from' in orders_df.columns:
        # Convert valid_from to NY and Berlin time for debug visibility
        valid_from_ts = pd.to_datetime(orders_df['valid_from'], utc=True)

        # NY time (already in this TZ usually, but ensure conversion)
        ny_time = valid_from_ts.dt.tz_convert('America/New_York')
        orders_df['NY_time'] = ny_time.dt.strftime('%Y-%m-%d %H:%M:%S %Z')

        # Berlin time
        berlin_time = valid_from_ts.dt.tz_convert('Europe/Berlin')
        orders_df['Berlin_time'] = berlin_time.dt.strftime('%Y-%m-%d %H:%M:%S %Z')

        logger.debug(f"Added timezone debug columns: NY_time, Berlin_time")

    return orders_df
