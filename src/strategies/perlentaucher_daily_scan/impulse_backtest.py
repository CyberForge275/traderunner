"""Deterministic first-trigger portfolio backtest for the Perlentaucher impulse research path."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .daily_pipeline import normalize_daily_ohlcv_frame
from .impulse_scan import (
    FIRST_TRIGGER_MODE,
    ImpulseScanCriteria,
    build_impulse_scan_artifacts,
    load_relaxed_impulse_scan_criteria,
)
from .market_dates import market_date_series


FIRST_TRIGGER_BACKTEST_MODE = "first_trigger_backtest"
DEFAULT_INITIAL_CAPITAL = 15_000.0
DEFAULT_SLOT_COUNT = 15
DEFAULT_HOLD_DAYS = 50
DEFAULT_STOP_LOSS_PCT = 0.50


@dataclass(frozen=True)
class ImpulseBacktestArtifacts:
    summary_df: pd.DataFrame
    detail_df: pd.DataFrame
    backtest_summary: dict[str, object]


def _build_symbol_frames(
    daily_df: pd.DataFrame,
    *,
    session_timezone: str,
) -> tuple[dict[str, pd.DataFrame], dict[tuple[str, str], float]]:
    frames: dict[str, pd.DataFrame] = {}
    close_map: dict[tuple[str, str], float] = {}
    for symbol, sym_df in daily_df.groupby("symbol", sort=True):
        frame = sym_df.sort_values("timestamp").reset_index(drop=True).copy()
        frame["session_date"] = market_date_series(
            frame["timestamp"],
            session_timezone=session_timezone,
            error_prefix="impulse backtest bars",
        ).astype(str)
        frames[str(symbol)] = frame
        for row in frame.itertuples(index=False):
            close_map[(str(row.symbol), str(row.session_date))] = float(row.close)
    return frames, close_map


def _build_trade_plan(
    trigger_row: pd.Series,
    *,
    symbol_frame: pd.DataFrame,
    hold_days: int,
    stop_loss_pct: float,
) -> dict[str, object]:
    entry_date = trigger_row.get("entry_date")
    entry_price = trigger_row.get("entry_open")
    if pd.isna(entry_date) or pd.isna(entry_price):
        return {"simulation_status": "missing_entry_bar"}

    tradable = symbol_frame.loc[pd.to_numeric(symbol_frame["volume"], errors="coerce").gt(0)].reset_index(drop=True)
    entry_matches = tradable.index[tradable["session_date"] == str(entry_date)].tolist()
    if not entry_matches:
        return {"simulation_status": "non_tradable_entry_bar"}

    entry_idx = int(entry_matches[0])
    hold_window = tradable.iloc[entry_idx : entry_idx + hold_days].reset_index(drop=True)
    if len(hold_window) < hold_days:
        return {"simulation_status": "missing_forward_bars"}

    stop_price = float(entry_price) * (1.0 - float(stop_loss_pct))
    stop_hits = hold_window.loc[pd.to_numeric(hold_window["low"], errors="coerce").le(stop_price)]
    if not stop_hits.empty:
        stop_row = stop_hits.iloc[0]
        exit_date = str(stop_row["session_date"])
        exit_price = stop_price
        exit_reason = f"stop_{int(stop_loss_pct * 100)}pct"
    else:
        exit_row = hold_window.iloc[hold_days - 1]
        exit_date = str(exit_row["session_date"])
        exit_price = float(exit_row["close"])
        exit_reason = f"hold_{hold_days}d"

    return {
        "simulation_status": "planned",
        "entry_date": str(entry_date),
        "entry_price": float(entry_price),
        "stop_price": stop_price,
        "exit_date": exit_date,
        "exit_price": float(exit_price),
        "exit_reason": exit_reason,
    }


def _simulate_adjusted_portfolio(
    planned_df: pd.DataFrame,
    *,
    close_map: dict[tuple[str, str], float],
    initial_capital: float,
    slot_count: int,
) -> tuple[pd.DataFrame, dict[str, object]]:
    detail_df = planned_df.copy().reset_index(drop=True)
    if detail_df.empty:
        return detail_df, {
            "start_capital": initial_capital,
            "end_equity": initial_capital,
            "profit": 0.0,
            "return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "max_open_positions": 0,
            "trade_count": 0,
        }

    detail_df["position_notional"] = pd.NA
    detail_df["shares"] = pd.NA
    detail_df["pnl"] = pd.NA
    detail_df["return_pct"] = pd.NA

    planned_only = detail_df.loc[detail_df["simulation_status"] == "planned"].reset_index(drop=False)
    entries_by_date = {
        entry_date: day_df.sort_values(["symbol", "as_of_date"])["index"].tolist()
        for entry_date, day_df in planned_only.groupby("entry_date", sort=True)
    }
    if planned_only.empty:
        all_dates: list[str] = []
    else:
        min_date = str(planned_only["entry_date"].min())
        max_date = str(planned_only["exit_date"].max())
        all_dates = sorted(
            {
                session_date
                for _, session_date in close_map
                if min_date <= session_date <= max_date
            }
        )

    cash = float(initial_capital)
    open_positions: dict[int, dict[str, object]] = {}
    equity_curve: list[float] = []
    max_open_positions = 0

    for session_date in all_dates:
        current_gross = sum(float(pos["shares"]) * float(pos["last_close"]) for pos in open_positions.values())
        start_equity = cash + current_gross

        for row_idx in entries_by_date.get(session_date, []):
            target_notional = float(start_equity) / float(slot_count)
            gross_capacity = (
                float(start_equity)
                if start_equity <= initial_capital
                else float(start_equity) + (float(start_equity) - float(initial_capital))
            )
            available_capacity = gross_capacity - current_gross
            position_notional = min(target_notional, available_capacity)
            if position_notional <= 0.0:
                detail_df.at[row_idx, "simulation_status"] = "skipped_capacity"
                continue

            entry_price = float(detail_df.at[row_idx, "entry_price"])
            shares = position_notional / entry_price
            cash -= position_notional
            detail_df.at[row_idx, "position_notional"] = position_notional
            detail_df.at[row_idx, "shares"] = shares
            detail_df.at[row_idx, "simulation_status"] = "executed"
            open_positions[row_idx] = {
                "symbol": str(detail_df.at[row_idx, "symbol"]),
                "shares": shares,
                "entry_price": entry_price,
                "last_close": entry_price,
            }
            current_gross += position_notional
            max_open_positions = max(max_open_positions, len(open_positions))

        exit_indices = [
            row_idx
            for row_idx, pos in open_positions.items()
            if str(detail_df.at[row_idx, "exit_date"]) == session_date
        ]
        for row_idx in sorted(exit_indices):
            position = open_positions.pop(row_idx)
            shares = float(position["shares"])
            entry_price = float(position["entry_price"])
            exit_price = float(detail_df.at[row_idx, "exit_price"])
            cash += shares * exit_price
            pnl = shares * (exit_price - entry_price)
            detail_df.at[row_idx, "pnl"] = pnl
            detail_df.at[row_idx, "return_pct"] = (exit_price / entry_price) - 1.0

        for row_idx, position in open_positions.items():
            close_price = close_map.get((str(position["symbol"]), session_date))
            if close_price is not None:
                position["last_close"] = float(close_price)

        end_equity = cash + sum(float(pos["shares"]) * float(pos["last_close"]) for pos in open_positions.values())
        equity_curve.append(float(end_equity))

    executed = detail_df.loc[detail_df["simulation_status"] == "executed"].reset_index(drop=True)
    running_max = pd.Series(equity_curve, dtype=float).cummax() if equity_curve else pd.Series(dtype=float)
    drawdown = ((pd.Series(equity_curve, dtype=float) / running_max) - 1.0) if not running_max.empty else pd.Series(dtype=float)
    end_equity = float(equity_curve[-1]) if equity_curve else float(initial_capital)
    return detail_df, {
        "start_capital": float(initial_capital),
        "end_equity": end_equity,
        "profit": end_equity - float(initial_capital),
        "return_pct": ((end_equity / float(initial_capital)) - 1.0) * 100.0 if initial_capital else 0.0,
        "max_drawdown_pct": float(drawdown.min() * 100.0) if not drawdown.empty else 0.0,
        "max_open_positions": int(max_open_positions),
        "trade_count": int(len(executed)),
    }


def build_first_trigger_backtest_artifacts(
    raw_daily_df: pd.DataFrame,
    *,
    valid_from: str,
    valid_to: str,
    criteria: ImpulseScanCriteria | None = None,
    session_timezone: str = "America/New_York",
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    slot_count: int = DEFAULT_SLOT_COUNT,
    hold_days: int = DEFAULT_HOLD_DAYS,
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
) -> ImpulseBacktestArtifacts:
    resolved_criteria = criteria if criteria is not None else load_relaxed_impulse_scan_criteria()
    daily_df = normalize_daily_ohlcv_frame(raw_daily_df)
    scan_artifacts = build_impulse_scan_artifacts(
        raw_daily_df=daily_df,
        valid_from=valid_from,
        valid_to=valid_to,
        trigger_mode=FIRST_TRIGGER_MODE,
        criteria=resolved_criteria,
        session_timezone=session_timezone,
    )
    symbol_frames, close_map = _build_symbol_frames(daily_df, session_timezone=session_timezone)

    plan_rows: list[dict[str, object]] = []
    if not scan_artifacts.detail_df.empty:
        for trigger_row in scan_artifacts.detail_df.sort_values(["entry_date", "symbol"]).to_dict(orient="records"):
            symbol = str(trigger_row["symbol"])
            plan_rows.append(
                {
                    **trigger_row,
                    **_build_trade_plan(
                        pd.Series(trigger_row),
                        symbol_frame=symbol_frames[symbol],
                        hold_days=hold_days,
                        stop_loss_pct=stop_loss_pct,
                    ),
                }
            )

    planned_df = pd.DataFrame(plan_rows).sort_values(["entry_date", "symbol"]).reset_index(drop=True) if plan_rows else pd.DataFrame()
    detail_df, backtest_summary = _simulate_adjusted_portfolio(
        planned_df,
        close_map=close_map,
        initial_capital=initial_capital,
        slot_count=slot_count,
    )
    return ImpulseBacktestArtifacts(
        summary_df=scan_artifacts.summary_df,
        detail_df=detail_df,
        backtest_summary=backtest_summary,
    )


__all__ = [
    "DEFAULT_HOLD_DAYS",
    "DEFAULT_INITIAL_CAPITAL",
    "DEFAULT_SLOT_COUNT",
    "DEFAULT_STOP_LOSS_PCT",
    "FIRST_TRIGGER_BACKTEST_MODE",
    "ImpulseBacktestArtifacts",
    "build_first_trigger_backtest_artifacts",
]
