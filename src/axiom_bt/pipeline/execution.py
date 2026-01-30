"""Execution layer: sizing + trade construction from fills and intent.

Keeps fills immutable; sizing can vary by mode.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Tuple

import pandas as pd

from trade.session_windows import session_end_for_day

logger = logging.getLogger(__name__)


class ExecutionError(ValueError):
    """Raised when execution cannot produce trades."""


@dataclass(frozen=True)
class ExecutionArtifacts:
    trades: pd.DataFrame  # UI contract ready (snake_case)
    equity_curve: pd.DataFrame
    portfolio_ledger: pd.DataFrame


def _apply_sizing(fills: pd.DataFrame, initial_cash: float, compound_enabled: bool) -> pd.DataFrame:
    """Apply position sizing to fills.
    
    NOTE: This function is NOT used for compound sizing anymore!
    Compound sizing now happens in _build_trades() where we have access to exit prices.
    """
    fills = fills.copy()
    fills["qty"] = 1.0  # Default qty (overridden in _build_trades if compound)
    return fills


def _build_trades(
    fills: pd.DataFrame,
    events_intent: pd.DataFrame,
    bars: pd.DataFrame,
    initial_cash: float,
    compound_enabled: bool,
    *,
    order_validity_policy: str | None,
    session_timezone: str | None,
    session_filter: list[str] | None,
) -> pd.DataFrame:
    """Build trades from fills with proper compound sizing.
    
    CRITICAL FIX FOR COMPOUND SIZING BUG:
    - Track cash through each completed trade
    - Start with initial_cash
    - For each trade: calculate qty = floor(cash / entry_price)
    - After trade: cash += PnL
    - Next trade uses updated cash for sizing
    """
    # One-fill trades: map intent side and exit info to trades
    intent_cols = ["template_id", "side", "exit_ts", "exit_reason"]
    merged = fills.merge(events_intent[intent_cols], on="template_id", how="left")
    
    merged = merged.rename(
        columns={
            "fill_ts": "entry_ts",
            "fill_price": "entry_price",
            "side": "side",
            "symbol": "symbol",
        }
    )
    
    # Fallback for missing exit_ts: enforce session_end (no instant trades)
    if merged["exit_ts"].isna().any():
        if order_validity_policy != "session_end":
            raise ValueError(
                "exit_ts missing in intent and order_validity_policy is not session_end; "
                "cannot determine deterministic exit_ts"
            )
        if not session_filter or not session_timezone:
            raise ValueError(
                "exit_ts missing in intent and session_end fallback requires "
                "session_filter + session_timezone"
            )
        def _fallback_exit(row):
            if pd.notna(row["exit_ts"]):
                return row["exit_ts"]
            return session_end_for_day(
                pd.to_datetime(row["entry_ts"], utc=True),
                session_filter,
                session_timezone,
            )
        merged["exit_ts"] = merged.apply(_fallback_exit, axis=1)
        merged["exit_reason"] = merged["exit_reason"].fillna("session_end")

    # Map exit price from bars (after exit_ts is final)
    bar_idx = bars.set_index("timestamp")["close"]
    merged["exit_price"] = merged["exit_ts"].map(bar_idx)
    if merged["exit_price"].isna().any():
        raise ValueError("exit_price could not be mapped for one or more exit_ts values")
    
    # COMPOUND SIZING: Calculate qty for each trade based on running cash balance
    if compound_enabled:
        # CRITICAL: Sort by entry timestamp to process in chronological order!
        merged = merged.sort_values("entry_ts").reset_index(drop=True)
        
        cash = initial_cash
        qtys = []
        
        for idx, row in merged.iterrows():
            # Calculate position size based on CURRENT available cash
            qty = int(max(cash // row["entry_price"], 1))
            qtys.append(qty)
            
            # Calculate PnL for this trade
            if row["side"] == "BUY":
                pnl = (row["exit_price"] - row["entry_price"]) * qty
            else:  # SELL
                pnl = (row["entry_price"] - row["exit_price"]) * qty
            
            # Update cash: add back PnL (profit or loss)
            # This makes cash available for next position
            cash += pnl
            
            logger.debug(
                f"Trade {idx}: {row['side']} qty={qty} @ {row['entry_price']:.2f} "
                f"→ {row['exit_price']:.2f}, pnl={pnl:.2f}, cash_after={cash:.2f}"
            )
        
        merged["qty"] = qtys
    else:
        # Fixed sizing: qty=1 for all trades
        merged["qty"] = 1.0
    
    # Calculate PnL (needed for equity curve even if already calculated above)
    merged["pnl"] = (merged["exit_price"] - merged["entry_price"]) * merged["qty"]
    merged.loc[merged["side"] == "SELL", "pnl"] = (merged["entry_price"] - merged["exit_price"]) * merged["qty"]
    
    merged["reason"] = merged["exit_reason"].fillna("UNKNOWN_EXIT_REASON")
    
    cols = [
        "template_id",
        "symbol",
        "side",
        "qty",
        "entry_ts",
        "entry_price",
        "exit_ts",
        "exit_price",
        "pnl",
        "reason",
    ]
    return merged[cols]


def _equity_from_trades(trades: pd.DataFrame, initial_cash: float) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["ts", "equity"])
    eq = trades[["exit_ts", "pnl"]].copy()
    eq["ts"] = pd.to_datetime(eq["exit_ts"], utc=True)
    eq = eq.sort_values("ts")
    eq["equity"] = float(initial_cash) + eq["pnl"].cumsum()
    return eq[["ts", "equity"]]


def execute(
    fills: pd.DataFrame,
    events_intent: pd.DataFrame,
    bars: pd.DataFrame,
    *,
    initial_cash: float,
    compound_enabled: bool,
    order_validity_policy: str | None = None,
    session_timezone: str | None = None,
    session_filter: list[str] | None = None,
) -> ExecutionArtifacts:
    """Apply sizing and produce trades/ledger/equity.

    Fills remain identical; sizing adjusts qty in _build_trades(), then trades/equity/ledger are derived.
    """
    if fills.empty:
        logger.info("actions: execution_skipped_empty_fills")
        empty_trades = pd.DataFrame(
            columns=[
                "template_id",
                "symbol",
                "side",
                "qty",
                "entry_ts",
                "entry_price",
                "exit_ts",
                "exit_price",
                "pnl",
                "reason",
            ]
        )
        empty_equity = pd.DataFrame(columns=["ts", "equity"])
        empty_ledger = pd.DataFrame(columns=["timestamp", "cash", "seq"])
        return ExecutionArtifacts(trades=empty_trades, equity_curve=empty_equity, portfolio_ledger=empty_ledger)

    sized_fills = _apply_sizing(fills, initial_cash, compound_enabled)
    trades = _build_trades(
        sized_fills,
        events_intent,
        bars,
        initial_cash,
        compound_enabled,
        order_validity_policy=order_validity_policy,
        session_timezone=session_timezone,
        session_filter=session_filter,
    )

    equity_curve = _equity_from_trades(trades, initial_cash)
    ledger = equity_curve.rename(columns={"ts": "timestamp", "equity": "cash"}).reset_index(drop=True)
    ledger["seq"] = ledger.index
    logger.info(
        "actions: execution_complete trades=%d compound=%s", len(trades), compound_enabled
    )
    return ExecutionArtifacts(trades=trades, equity_curve=equity_curve, portfolio_ledger=ledger)
