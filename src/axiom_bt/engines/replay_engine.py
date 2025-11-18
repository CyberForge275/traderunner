from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

import pandas as pd

from core.settings import DEFAULT_INITIAL_CASH

Side = Literal["BUY", "SELL"]


def _ensure_dtindex_and_ohlcv(df: pd.DataFrame, tz: str) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        ts_col = next((c for c in ["ts", "timestamp", "datetime", "date"] if c in df.columns), None)
        if ts_col is None:
            raise ValueError("OHLCV frame requires DatetimeIndex or timestamp column")
        idx = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
        df = df.drop(columns=[ts_col]).set_index(idx)

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    if tz:
        df.index = df.index.tz_convert(tz)

    rename = {}
    for column in df.columns:
        lower = column.lower()
        if lower in ("open", "high", "low", "close", "volume"):
            rename[column] = lower.capitalize() if lower != "volume" else "Volume"
    if rename:
        df = df.rename(columns=rename)

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")

    return df.sort_index()


@dataclass
class Costs:
    fees_bps: float = 0.0
    slippage_bps: float = 0.0


def _apply_slippage(price: float, side: Side, bps: float) -> float:
    if bps <= 0:
        return price
    adjustment = price * (bps / 1e4)
    return price + adjustment if side == "BUY" else price - adjustment


def _fees(qty: float, price: float, bps: float) -> float:
    return abs(qty) * price * (bps / 1e4)


def _first_touch_entry(
    df: pd.DataFrame,
    side: Side,
    price: float,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> Optional[pd.Timestamp]:
    window = df.loc[(df.index >= start) & (df.index <= end)]
    if window.empty:
        return None
    if side == "BUY":
        hit = window[window["High"] >= price]
    else:
        hit = window[window["Low"] <= price]
    if hit.empty:
        return None
    return hit.index[0]


def _exit_after_entry(
    df: pd.DataFrame,
    side: Side,
    entry_ts: pd.Timestamp,
    stop_loss: Optional[float],
    take_profit: Optional[float],
    valid_until: pd.Timestamp,
):
    window = df.loc[(df.index >= entry_ts) & (df.index <= valid_until)]
    for ts, row in window.iterrows():
        low = row["Low"]
        high = row["High"]
        if side == "BUY":
            sl_hit = stop_loss is not None and low <= stop_loss
            tp_hit = take_profit is not None and high >= take_profit
            if sl_hit and tp_hit:
                return ts, stop_loss, "SL"
            if sl_hit:
                return ts, stop_loss, "SL"
            if tp_hit:
                return ts, take_profit, "TP"
        else:
            sl_hit = stop_loss is not None and high >= stop_loss
            tp_hit = take_profit is not None and low <= take_profit
            if sl_hit and tp_hit:
                return ts, stop_loss, "SL"
            if sl_hit:
                return ts, stop_loss, "SL"
            if tp_hit:
                return ts, take_profit, "TP"
    last_ts = window.index[-1]
    last_close = float(window.iloc[-1]["Close"])
    return last_ts, last_close, "EOD"


def _derive_m1_dir(data_path: Path) -> Optional[Path]:
    name = data_path.name.lower()
    if "m5" in name:
        candidate = data_path.with_name(data_path.name.replace("m5", "m1"))
        if candidate.exists():
            return candidate
    if "m15" in name:
        candidate = data_path.with_name(data_path.name.replace("m15", "m1"))
        if candidate.exists():
            return candidate
    sibling = data_path.parent / "data_m1"
    if sibling.exists():
        return sibling
    return None


def _resolve_symbol_path(symbol: str, m1_dir: Optional[Path], fallback_dir: Path) -> Tuple[Optional[Path], bool]:
    if m1_dir is not None:
        candidate = m1_dir / f"{symbol}.parquet"
        if candidate.exists():
            return candidate, True
    fallback = fallback_dir / f"{symbol}.parquet"
    if fallback.exists():
        return fallback, False
    return None, False


def simulate_insidebar_from_orders(
    orders_csv: Path,
    data_path: Path,
    tz: str,
    costs: Costs,
    initial_cash: float = DEFAULT_INITIAL_CASH,
    data_path_m1: Optional[Path] = None,
) -> Dict[str, Any]:
    orders = pd.read_csv(orders_csv)
    orders["valid_from"] = pd.to_datetime(orders.get("valid_from"), utc=True, errors="coerce")
    orders["valid_to"] = pd.to_datetime(orders.get("valid_to"), utc=True, errors="coerce")
    if orders.empty:
        empty = pd.DataFrame()
        return {
            "filled_orders": empty,
            "trades": empty,
            "equity": empty,
            "metrics": {"num_trades": 0, "pnl": 0.0},
        }

    for column in ["valid_from", "valid_to"]:
        if orders[column].dt.tz is None:
            orders[column] = orders[column].dt.tz_localize(tz)
        else:
            orders[column] = orders[column].dt.tz_convert(tz)

    ib_orders = orders.query('order_type == "STOP"').copy()
    if ib_orders.empty:
        empty = pd.DataFrame()
        return {
            "filled_orders": empty,
            "trades": empty,
            "equity": empty,
            "metrics": {"num_trades": 0, "pnl": 0.0},
            "orders": ib_orders,
        }

    data_path = Path(data_path)
    m1_dir = Path(data_path_m1) if data_path_m1 is not None else _derive_m1_dir(data_path)

    filled = []
    trades = []
    cash = initial_cash
    equity_points = []
    filled_indices: list[int] = []
    fill_ts_map: dict[int, pd.Timestamp] = {}

    for symbol, group in ib_orders.groupby("symbol"):
        file_path, _ = _resolve_symbol_path(symbol, m1_dir, data_path)
        if file_path is None:
            continue
        ohlcv = pd.read_parquet(file_path)
        ohlcv = _ensure_dtindex_and_ohlcv(ohlcv, tz)
        # ensure chronological order when switching between sources
        ohlcv = ohlcv.sort_index()
        group = group.sort_values("valid_from")

        for oco_group, oco_orders in group.groupby("oco_group"):
            for _, row in oco_orders.iterrows():
                side: Side = "BUY" if row["side"] == "BUY" else "SELL"
                entry_price = float(row["price"])
                valid_from = pd.to_datetime(row["valid_from"]).tz_convert(tz)
                valid_to = pd.to_datetime(row["valid_to"]).tz_convert(tz)
                entry_ts = _first_touch_entry(ohlcv, side, entry_price, valid_from, valid_to)
                if entry_ts is None:
                    continue

                quantity = float(row.get("qty", 1.0))
                adjusted_entry = _apply_slippage(entry_price, side, costs.slippage_bps)
                fill_entry_price = adjusted_entry
                slippage_entry = quantity * (fill_entry_price - entry_price)
                fees_entry = _fees(quantity, fill_entry_price, costs.fees_bps)
                stop_loss = float(row["stop_loss"]) if not pd.isna(row["stop_loss"]) else None
                take_profit = float(row["take_profit"]) if not pd.isna(row["take_profit"]) else None

                exit_ts, raw_exit_price, exit_reason = _exit_after_entry(
                    ohlcv, side, entry_ts, stop_loss, take_profit, valid_to
                )

                opposite_side: Side = "SELL" if side == "BUY" else "BUY"
                adjusted_exit = _apply_slippage(raw_exit_price, opposite_side, costs.slippage_bps)
                fill_exit_price = adjusted_exit
                slippage_exit = quantity * (fill_exit_price - raw_exit_price)
                fees_exit = _fees(quantity, fill_exit_price, costs.fees_bps)

                pnl = quantity * (fill_exit_price - fill_entry_price)
                if side == "SELL":
                    pnl = quantity * (fill_entry_price - fill_exit_price)
                total_fees = fees_entry + fees_exit
                total_slippage = slippage_entry + slippage_exit
                pnl -= total_fees
                cash += pnl

                filled.append(
                    {
                        "symbol": symbol,
                        "side": side,
                        "entry_ts": entry_ts.isoformat(),
                        "entry_price": fill_entry_price,
                        "exit_ts": exit_ts.isoformat(),
                        "exit_price": fill_exit_price,
                        "pnl": pnl,
                        "fees_entry": fees_entry,
                        "fees_exit": fees_exit,
                        "slippage_entry": slippage_entry,
                        "slippage_exit": slippage_exit,
                        "fees_total": total_fees,
                        "slippage_total": total_slippage,
                        "exit_reason": exit_reason,
                        "oco_group": oco_group,
                        "qty": quantity,
                    }
                )
                trades.append(
                    {
                        "symbol": symbol,
                        "side": side,
                        "qty": quantity,
                        "entry_ts": entry_ts.isoformat(),
                        "entry_price": fill_entry_price,
                        "exit_ts": exit_ts.isoformat(),
                        "exit_price": fill_exit_price,
                        "pnl": pnl,
                        "reason": exit_reason,
                        "fees_entry": fees_entry,
                        "fees_exit": fees_exit,
                        "fees_total": total_fees,
                        "slippage_entry": slippage_entry,
                        "slippage_exit": slippage_exit,
                        "slippage_total": total_slippage,
                    }
                )
                equity_points.append({"ts": exit_ts.isoformat(), "equity": cash})
                filled_indices.append(int(row.name))
                fill_ts_map[int(row.name)] = entry_ts
                break

    filled_df = pd.DataFrame(filled)
    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_points).sort_values("ts")
    total_pnl = float(trades_df["pnl"].sum()) if not trades_df.empty else 0.0
    num_trades = int(len(trades_df))
    win_rate = float((trades_df["pnl"] > 0).mean()) if num_trades > 0 else 0.0

    metrics = {
        "initial_cash": initial_cash,
        "final_cash": initial_cash + total_pnl,
        "pnl": total_pnl,
        "num_trades": num_trades,
        "win_rate": win_rate,
    }
    annotated_orders = ib_orders.copy()
    if not annotated_orders.empty:
        annotated_orders["filled"] = False
        annotated_orders["fill_timestamp"] = None
        for idx in filled_indices:
            if idx in annotated_orders.index:
                annotated_orders.at[idx, "filled"] = True
                annotated_orders.at[idx, "fill_timestamp"] = fill_ts_map.get(idx)
        annotated_orders["fill_timestamp"] = annotated_orders["fill_timestamp"].apply(
            lambda ts: ts.isoformat() if isinstance(ts, pd.Timestamp) else None
        )

    return {
        "filled_orders": filled_df,
        "trades": trades_df,
        "equity": equity_df,
        "metrics": metrics,
        "orders": annotated_orders,
    }


def simulate_daily_moc_from_orders(
    orders_csv: Path,
    data_path: Path,
    tz: str,
    costs: Costs,
    initial_cash: float = DEFAULT_INITIAL_CASH,
) -> Dict[str, Any]:
    orders = pd.read_csv(orders_csv)
    orders["valid_from"] = pd.to_datetime(orders.get("valid_from"), utc=True, errors="coerce")
    if orders.empty:
        empty = pd.DataFrame()
        return {
            "filled_orders": empty,
            "trades": empty,
            "equity": empty,
            "metrics": {"num_trades": 0, "pnl": 0.0},
        }

    if orders["valid_from"].dt.tz is None:
        orders["valid_from"] = orders["valid_from"].dt.tz_localize(tz)
    else:
        orders["valid_from"] = orders["valid_from"].dt.tz_convert(tz)

    filled = []
    trades = []
    cash = initial_cash

    for symbol, group in orders.groupby("symbol"):
        file_path = data_path / f"{symbol}.parquet"
        if not file_path.exists():
            continue
        ohlcv = pd.read_parquet(file_path)
        ohlcv = _ensure_dtindex_and_ohlcv(ohlcv, tz)

        for _, row in group.iterrows():
            day = row["valid_from"].date()
            row_slice = ohlcv.loc[ohlcv.index.date == day]
            if row_slice.empty:
                continue
            candle = row_slice.iloc[0]
            close = float(candle["Close"])
            side = "BUY" if row["side"] == "BUY" else "SELL"
            quantity = float(row.get("qty", 1.0))
            fill_price = _apply_slippage(close, side, costs.slippage_bps)
            fees = _fees(quantity, fill_price, costs.fees_bps)
            trades.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "qty": quantity,
                    "entry_ts": str(candle.name),
                    "entry_price": fill_price,
                    "exit_ts": str(candle.name),
                    "exit_price": fill_price,
                    "pnl": -fees,
                    "reason": "MOC_fill_only",
                }
            )
            filled.append(
                {
                    "symbol": symbol,
                    "side": side,
                    "ts": str(candle.name),
                    "price": fill_price,
                    "note": "MOC fill",
                }
            )
            cash -= fees

    filled_df = pd.DataFrame(filled)
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        equity_df = pd.DataFrame({"ts": trades_df["exit_ts"], "equity": cash}).head(1)
    else:
        equity_df = pd.DataFrame(columns=["ts", "equity"])

    total_pnl = float(trades_df["pnl"].sum()) if not trades_df.empty else 0.0
    num_trades = int(len(trades_df))
    win_rate = float((trades_df["pnl"] > 0).mean()) if num_trades > 0 else 0.0

    metrics = {
        "initial_cash": initial_cash,
        "final_cash": initial_cash + total_pnl,
        "pnl": total_pnl,
        "num_trades": num_trades,
        "win_rate": win_rate,
    }
    return {
        "filled_orders": filled_df,
        "trades": trades_df,
        "equity": equity_df,
        "metrics": metrics,
    }
