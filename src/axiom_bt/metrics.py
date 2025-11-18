from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd


def _coerce_ts_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "ts" not in df.columns:
        return df
    out = df.copy()
    out["ts"] = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    return out.sort_values("ts")


def _ensure_baseline_equity(equity: pd.DataFrame, initial_cash: float) -> pd.DataFrame:
    if equity is None or equity.empty:
        return equity

    eq = _coerce_ts_df(equity)
    if eq["ts"].isna().all():
        return eq

    first_equity = float(pd.to_numeric(eq["equity"].iloc[0], errors="coerce"))
    if np.isfinite(first_equity) and first_equity < float(initial_cash):
        baseline_ts = eq["ts"].iloc[0] - pd.Timedelta(seconds=1)
        base = pd.DataFrame({"ts": [baseline_ts], "equity": [float(initial_cash)]})
        base = _coerce_ts_df(base)
        eq = pd.concat([base, eq], ignore_index=True)
        eq = _coerce_ts_df(eq)
    return eq


def compute_drawdown(equity: pd.Series) -> Tuple[float, float]:
    series = pd.to_numeric(equity, errors="coerce").astype(float)
    if series.empty or np.isnan(series).all():
        return 0.0, 0.0

    roll_max = series.cummax()
    dd_abs = roll_max - series
    max_dd = float(dd_abs.max()) if len(dd_abs) else 0.0

    denom = float(roll_max.max()) if float(roll_max.max()) > 0 else 0.0
    max_dd_pct = float(max_dd / denom) if denom > 0 else 0.0
    return max_dd, max_dd_pct


def equity_from_trades(trades: pd.DataFrame, initial_cash: float) -> pd.DataFrame:
    if trades is None or trades.empty:
        return pd.DataFrame({"ts": pd.to_datetime([], utc=True), "equity": []})

    eq = trades[["exit_ts", "pnl"]].copy()
    eq["ts"] = pd.to_datetime(eq["exit_ts"], utc=True, errors="coerce")
    pnl = pd.to_numeric(eq["pnl"], errors="coerce").astype(float)
    eq["equity"] = float(initial_cash) + pnl.cumsum()
    eq = eq[["ts", "equity"]]
    eq = _coerce_ts_df(eq)
    return eq


def drawdown_series(equity: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    if equity is None or equity.empty:
        idx = pd.to_datetime([], utc=True)
        return pd.Series([], index=idx, dtype=float), pd.Series([], index=idx, dtype=float)

    eq = _coerce_ts_df(equity)
    indexed = eq.set_index(eq["ts"])["equity"].astype(float)
    peak = np.maximum.accumulate(indexed.values)
    dd_abs = pd.Series(peak - indexed.values, index=indexed.index, name="dd_abs")
    with np.errstate(divide="ignore", invalid="ignore"):
        dd_pct = pd.Series((indexed.values / peak) - 1.0, index=indexed.index, name="dd_pct")
    return dd_abs, dd_pct


def max_drawdown(equity: pd.DataFrame) -> Tuple[float, float]:
    dd_abs, dd_pct = drawdown_series(equity)
    if dd_abs.empty:
        return 0.0, 0.0
    return float(dd_abs.max()), float(-dd_pct.min())


def sharpe_daily(equity: pd.DataFrame, risk_free: float = 0.0) -> float:
    if equity is None or equity.empty:
        return 0.0

    series = _coerce_ts_df(equity).copy()
    series["date"] = series["ts"].dt.normalize()
    daily = series.groupby("date", as_index=False)["equity"].last()
    returns = daily["equity"].pct_change().dropna()

    if len(returns) < 2:
        return 0.0

    excess = returns - (risk_free / 252.0)
    sigma = excess.std(ddof=1)
    if not np.isfinite(sigma) or sigma <= 0:
        return 0.0

    mu = excess.mean()
    return float(np.sqrt(252.0) * mu / (sigma + 1e-12))


def trade_stats(trades: pd.DataFrame) -> Dict[str, float]:
    if trades is None or trades.empty:
        return {
            "num_trades": 0,
            "win_rate": 0.0,
            "gross_pnl": 0.0,
            "net_pnl": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "turnover_abs": 0.0,
        }

    pnl = pd.to_numeric(trades["pnl"], errors="coerce").astype(float)
    gross_pnl = float(pnl.sum())
    net_pnl = gross_pnl

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    num_trades = int(len(trades))
    win_rate = float((len(wins) / num_trades) if num_trades > 0 else 0.0)
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0

    if len(losses) and abs(losses.sum()) > 0:
        profit_factor = float(wins.sum() / abs(losses.sum()))
    else:
        profit_factor = float("inf") if len(wins) and len(losses) == 0 else 0.0

    if all(col in trades.columns for col in ["qty", "entry_price", "exit_price"]):
        turnover_abs = (
            trades["qty"].abs()
            * (trades["entry_price"].abs() + trades["exit_price"].abs())
        ).sum()
    else:
        turnover_abs = 0.0

    return {
        "num_trades": num_trades,
        "win_rate": win_rate,
        "gross_pnl": float(gross_pnl),
        "net_pnl": float(net_pnl),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": float(profit_factor),
        "turnover_abs": float(turnover_abs),
    }


def compose_metrics(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    initial_cash: float,
    risk_free: float = 0.0,
) -> Dict[str, float]:
    stats = trade_stats(trades)

    eq = pd.DataFrame(columns=["ts", "equity"]) if equity is None else equity.copy()
    eq = _coerce_ts_df(eq)
    eq = _ensure_baseline_equity(eq, initial_cash)

    if not eq.empty:
        max_dd, max_dd_pct = compute_drawdown(eq["equity"])
    else:
        max_dd, max_dd_pct = 0.0, 0.0

    sharpe = sharpe_daily(eq, risk_free=risk_free)

    if trades is None or trades.empty:
        exposure = 0.0
    else:
        entry = pd.to_datetime(trades["entry_ts"], utc=True, errors="coerce")
        exit_ = pd.to_datetime(trades["exit_ts"], utc=True, errors="coerce")
        durations = (exit_ - entry).dt.total_seconds().clip(lower=0).fillna(0)
        period = (exit_.max() - entry.min()).total_seconds() if len(trades) else 0
        exposure = float(durations.sum() / period) if period > 0 else 0.0

    turnover_rel = float(
        stats.get("turnover_abs", 0.0) / (initial_cash if initial_cash > 0 else 1.0)
    )

    return {
        "initial_cash": float(initial_cash),
        "final_cash": float(eq["equity"].iloc[-1]) if not eq.empty else float(initial_cash + stats["net_pnl"]),
        "net_pnl": float(stats["net_pnl"]),
        "gross_pnl": float(stats["gross_pnl"]),
        "num_trades": int(stats["num_trades"]),
        "win_rate": float(stats["win_rate"]),
        "avg_win": float(stats["avg_win"]),
        "avg_loss": float(stats["avg_loss"]),
        "profit_factor": float(stats["profit_factor"]),
        "max_drawdown": float(max_dd),
        "max_drawdown_pct": float(max_dd_pct),
        "sharpe_ratio": float(sharpe),
        "exposure": float(exposure),
        "turnover": float(turnover_rel),
    }
