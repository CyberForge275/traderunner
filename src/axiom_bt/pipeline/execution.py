"""Execution layer: sizing + trade construction from fills and intent.

Keeps fills immutable; sizing can vary by mode.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class ExecutionError(ValueError):
    """Raised when execution cannot produce trades."""


@dataclass(frozen=True)
class ExecutionArtifacts:
    trades: pd.DataFrame  # UI contract ready (snake_case)
    equity_curve: pd.DataFrame
    portfolio_ledger: pd.DataFrame


def _apply_sizing(fills: pd.DataFrame, initial_cash: float, compound_enabled: bool) -> pd.DataFrame:
    fills = fills.copy()
    fills["qty"] = 1.0
    if compound_enabled:
        # simple cash-based qty: floor(cash/price) updated per fill
        cash = initial_cash
        qtys = []
        for _, row in fills.iterrows():
            qty = int(max(cash // row["fill_price"], 1))
            qtys.append(qty)
            cash -= qty * row["fill_price"]  # naive cash debit
        fills["qty"] = qtys
    return fills


def _build_trades(fills: pd.DataFrame, events_intent: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    # One-fill trades: map intent side and exit info to trades
    intent_cols = ["template_id", "side", "exit_ts", "exit_reason"]
    merged = fills.merge(events_intent[intent_cols], on="template_id", how="left")
    
    merged = merged.rename(
        columns={
            "fill_ts": "entry_ts",
            "fill_price": "entry_price",
            "side": "side",
            "qty": "qty",
            "symbol": "symbol",
        }
    )
    
    # Map exit price from bars
    bar_idx = bars.set_index("timestamp")["close"]
    # Ensure indices match for mapping (both should be UTC timestamps)
    merged["exit_price"] = merged["exit_ts"].map(bar_idx)
    
    # Fallback/Safety: if no exit_ts defined by strategy, use entry
    merged["exit_ts"] = merged["exit_ts"].fillna(merged["entry_ts"])
    merged["exit_price"] = merged["exit_price"].fillna(merged["entry_price"])
    
    # Calculate PnL
    merged["pnl"] = (merged["exit_price"] - merged["entry_price"]) * merged["qty"]
    # For SELL, PnL is (entry - exit) * qty
    merged.loc[merged["side"] == "SELL", "pnl"] = (merged["entry_price"] - merged["exit_price"]) * merged["qty"]
    
    merged["reason"] = merged["exit_reason"].fillna(merged.get("reason", "signal_fill"))
    
    cols = ["symbol", "side", "qty", "entry_ts", "entry_price", "exit_ts", "exit_price", "pnl", "reason"]
    return merged[cols]


def _equity_from_trades(trades: pd.DataFrame, initial_cash: float) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["ts", "equity"])
    eq = trades[["exit_ts", "pnl"]].copy()
    eq["ts"] = pd.to_datetime(eq["exit_ts"], utc=True)
    eq = eq.sort_values("ts")
    eq["equity"] = float(initial_cash) + eq["pnl"].cumsum()
    return eq[["ts", "equity"]]


def execute(fills: pd.DataFrame, events_intent: pd.DataFrame, bars: pd.DataFrame, *, initial_cash: float, compound_enabled: bool) -> ExecutionArtifacts:
    """Apply sizing and produce trades/ledger/equity.

    Fills remain identical; sizing adjusts qty only, then trades/equity/ledger are derived.
    """
    if fills.empty:
        raise ExecutionError("fills empty; cannot execute")

    sized_fills = _apply_sizing(fills, initial_cash, compound_enabled)
    trades = _build_trades(sized_fills, events_intent, bars)

    equity_curve = _equity_from_trades(trades, initial_cash)
    ledger = equity_curve.rename(columns={"ts": "timestamp", "equity": "cash"}).reset_index(drop=True)
    ledger["seq"] = ledger.index
    logger.info(
        "actions: execution_complete trades=%d compound=%s", len(trades), compound_enabled
    )
    return ExecutionArtifacts(trades=trades, equity_curve=equity_curve, portfolio_ledger=ledger)
