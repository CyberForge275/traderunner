from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple, Union

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
    import logging
    logger = logging.getLogger(__name__)

    # Prefer RTH, then RAW (all sessions), then older ALL-suffix, then legacy unsuffixed.
    names = [
        f"{symbol}_rth.parquet",
        f"{symbol}_raw.parquet",
        f"{symbol}_all.parquet",
        f"{symbol}.parquet",
    ]

    def first_existing(base: Path) -> Optional[Path]:
        for name in names:
            p = base / name
            if p.exists():
                return p
        return None

    if m1_dir is not None:
        p = first_existing(m1_dir)
        if p is not None:
            logger.debug(f"Resolved {symbol} → {p} (M1 data)")
            return p, True

    p = first_existing(fallback_dir)
    if p is not None:
        logger.debug(f"Resolved {symbol} → {p} (fallback data)")
        return p, False

    logger.warning(f"No data file found for {symbol} (searched: {m1_dir}, {fallback_dir})")
    return None, False


def simulate_insidebar_from_orders(
    orders_csv: Path,
    data_path: Path,
    tz: str,
    costs: Costs,
    initial_cash: float = DEFAULT_INITIAL_CASH,
    data_path_m1: Optional[Path] = None,
    requested_end: Optional[Union[str, pd.Timestamp]] = None,
) -> Dict[str, Any]:
    import logging
    logger = logging.getLogger(__name__)

    orders = pd.read_csv(orders_csv)

    # Enhanced datetime conversion with better error handling
    logger.info(f"Processing orders from {orders_csv}")
    logger.info(f"Orders shape: {orders.shape}")
    logger.info(f"Orders columns: {orders.columns.tolist()}")

    # Convert datetime columns with explicit error handling
    for col in ["valid_from", "valid_to"]:
        if col in orders.columns:
            try:
                # First, check if all values can be converted
                orders[col] = pd.to_datetime(orders[col], utc=True)
                logger.info(f"Successfully converted '{col}' to datetime. Dtype: {orders[col].dtype}")
            except Exception as e:
                # Log detailed error information
                logger.error(f"Failed to convert '{col}' column to datetime")
                logger.error(f"Error: {type(e).__name__}: {str(e)}")
                logger.error(f"Sample values from '{col}': {orders[col].head().tolist()}")
                logger.error(f"Column dtype: {orders[col].dtype}")
                raise ValueError(
                    f"Failed to convert '{col}' to datetime. "
                    f"Please ensure all values are valid datetime strings. "
                    f"Sample values: {orders[col].head().tolist()}"
                ) from e

    if orders.empty:
        empty = pd.DataFrame()
        return {
            "filled_orders": empty,
            "trades": empty,
            "equity": empty,
            "metrics": {"num_trades": 0, "pnl": 0.0},
        }

    # Validate that datetime conversion worked before using .dt accessor
    for column in ["valid_from", "valid_to"]:
        # Only validate if column exists (it should after the conversion above)
        if column not in orders.columns:
            logger.error(f"Required column '{column}' is missing from orders CSV")
            raise ValueError(
                f"Missing required column '{column}' in orders file. "
                f"Available columns: {orders.columns.tolist()}"
            )

        if not pd.api.types.is_datetime64_any_dtype(orders[column]):
            logger.error(f"Column '{column}' is not datetime dtype: {orders[column].dtype}")
            raise TypeError(
                f"Column '{column}' must be datetime type, got {orders[column].dtype}. "
                f"This usually means datetime conversion failed silently."
            )

        # Handle timezone
        if orders[column].dt.tz is None:
            logger.info(f"Localizing '{column}' to {tz}")
            orders[column] = orders[column].dt.tz_localize(tz)
        else:
            logger.info(f"Converting '{column}' from {orders[column].dt.tz} to {tz}")
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

    # Defensive: Ensure paths are directories, not files
    # If user passed a file path, use the parent directory
    if m1_dir is not None and m1_dir.is_file():
        logger.warning(f"data_path_m1 points to file instead of directory, using parent: {m1_dir} → {m1_dir.parent}")
        m1_dir = m1_dir.parent

    if data_path.is_file():
        logger.warning(f"data_path points to file instead of directory, using parent: {data_path} → {data_path.parent}")
        data_path = data_path.parent


    filled = []
    trades = []
    cash = initial_cash
    equity_points = []
    filled_indices: list[int] = []
    fill_ts_map: dict[int, pd.Timestamp] = {}
    last_data_ts: Optional[pd.Timestamp] = None

    for symbol, group in ib_orders.groupby("symbol"):
        file_path, _ = _resolve_symbol_path(symbol, m1_dir, data_path)
        if file_path is None:
            continue
        ohlcv = pd.read_parquet(file_path)
        ohlcv = _ensure_dtindex_and_ohlcv(ohlcv, tz)
        # ensure chronological order when switching between sources
        ohlcv = ohlcv.sort_index()
        if not ohlcv.empty:
            ts_max = ohlcv.index.max()
            if last_data_ts is None or ts_max > last_data_ts:
                last_data_ts = ts_max
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

    if equity_points:
        equity_df = pd.DataFrame(equity_points).sort_values("ts")
    else:
        # No equity points were generated (e.g. all orders expired
        # without entry). Synthesize a flat equity curve at a
        # deterministic timestamp so downstream code can always rely on
        # a non-empty equity frame.
        fallback_ts: Optional[pd.Timestamp] = None
        rule = None

        # Priority 1: explicit requested_end from the caller.
        if requested_end is not None:
            try:
                ts = pd.Timestamp(requested_end)
                if ts.tzinfo is None:
                    ts = ts.tz_localize(tz)
                else:
                    ts = ts.tz_convert(tz)
                fallback_ts = ts
                rule = "prio_requested_end"
            except Exception:
                fallback_ts = None

        # Priority 2: derive from orders timestamps.
        if fallback_ts is None and not orders.empty:
            for col, label in (("valid_to", "prio_orders_valid_to"), ("valid_from", "prio_orders_valid_from")):
                if col in orders.columns:
                    series = pd.to_datetime(orders[col], errors="coerce", utc=True).dropna()
                    if not series.empty:
                        candidate = series.max().tz_convert(tz)
                        fallback_ts = candidate
                        rule = label
                        break

        # Priority 3: latest available market data timestamp.
        if fallback_ts is None and last_data_ts is not None:
            fallback_ts = last_data_ts
            rule = "prio_data_index"

        # Priority 4: deterministic epoch fallback.
        if fallback_ts is None:
            ts_epoch = pd.Timestamp("1970-01-01T00:00:00Z")
            fallback_ts = ts_epoch.tz_convert(tz)
            rule = "prio_epoch_fallback"

        logger.info(
            "simulate_insidebar_from_orders: synthesized flat equity (rule=%s, ts=%s)",
            rule,
            fallback_ts.isoformat() if isinstance(fallback_ts, pd.Timestamp) else None,
        )

        equity_df = pd.DataFrame(
            [
                {
                    "ts": fallback_ts.isoformat(),
                    "equity": float(initial_cash),
                }
            ]
        )
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
    import logging
    logger = logging.getLogger(__name__)

    orders = pd.read_csv(orders_csv)

    # Enhanced datetime conversion with better error handling
    logger.info(f"Processing MOC orders from {orders_csv}")
    logger.info(f"Orders shape: {orders.shape}")

    if "valid_from" in orders.columns:
        try:
            orders["valid_from"] = pd.to_datetime(orders["valid_from"], utc=True)
            logger.info(f"Successfully converted 'valid_from' to datetime. Dtype: {orders['valid_from'].dtype}")
        except Exception as e:
            logger.error(f"Failed to convert 'valid_from' to datetime: {type(e).__name__}: {str(e)}")
            logger.error(f"Sample values: {orders['valid_from'].head().tolist()}")
            raise ValueError(
                f"Failed to convert 'valid_from' to datetime. "
                f"Sample values: {orders['valid_from'].head().tolist()}"
            ) from e

    if orders.empty:
        empty = pd.DataFrame()
        return {
            "filled_orders": empty,
            "trades": empty,
            "equity": empty,
            "metrics": {"num_trades": 0, "pnl": 0.0},
        }

    # Validate datetime dtype before using .dt accessor
    if not pd.api.types.is_datetime64_any_dtype(orders["valid_from"]):
        logger.error(f"Column 'valid_from' is not datetime dtype: {orders['valid_from'].dtype}")
        raise TypeError(
            f"Column 'valid_from' must be datetime type, got {orders['valid_from'].dtype}"
        )

    if orders["valid_from"].dt.tz is None:
        logger.info(f"Localizing 'valid_from' to {tz}")
        orders["valid_from"] = orders["valid_from"].dt.tz_localize(tz)
    else:
        logger.info(f"Converting 'valid_from' from {orders['valid_from'].dt.tz} to {tz}")
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
