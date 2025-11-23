from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

from core.settings import (
    DEFAULT_INITIAL_CASH,
    DEFAULT_MIN_QTY,
    DEFAULT_RISK_PCT,
    INSIDE_BAR_SESSIONS,
    INSIDE_BAR_TIMEZONE,
)
from trade.position_sizing import qty_fixed, qty_pct_of_equity, qty_risk_based


ARTIFACTS = Path("artifacts")
SIGNALS_DIR = ARTIFACTS / "signals"
ORDERS_DIR = ARTIFACTS / "orders"
BERLIN_TZ = INSIDE_BAR_TIMEZONE


@dataclass
class Session:
    start: str
    end: str


def _parse_sessions(raw: str) -> List[Session]:
    windows: List[Session] = []
    for chunk in [part.strip() for part in raw.split(",") if part.strip()]:
        start, end = [token.strip() for token in chunk.split("-")]
        windows.append(Session(start, end))
    return windows


def _tz_to_local(ts: pd.Series, tz: str) -> pd.Series:
    parsed = pd.to_datetime(ts, errors="coerce", utc=True)
    return parsed.dt.tz_convert(tz)


def _round_price(value: float, tick: float, mode: str) -> float:
    if np.isnan(value):
        return np.nan
    if tick <= 0:
        return value
    quotient = value / tick
    if mode == "floor":
        quotient = np.floor(quotient)
    elif mode == "ceil":
        quotient = np.ceil(quotient)
    else:
        quotient = np.round(quotient)
    return float(quotient * tick)


def _oco_id(symbol: str, ts: pd.Timestamp) -> str:
    return f"{symbol}_{ts.strftime('%Y%m%d_%H%M%S')}"


def _session_end(ts: pd.Timestamp, sessions: List[Session], tz: str) -> pd.Timestamp:
    local = ts
    for window in sessions:
        start = pd.Timestamp(f"{local.date()} {window.start}", tz=tz)
        end = pd.Timestamp(f"{local.date()} {window.end}", tz=tz)
        if start <= local <= end:
            return end
    return local


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export broker-ready orders from strategy signals")
    parser.add_argument("--source", default=str(SIGNALS_DIR / "current_signals_ib.csv"))
    parser.add_argument("--sessions", default=",".join(INSIDE_BAR_SESSIONS))
    parser.add_argument("--tick-size", type=float, default=0.01)
    parser.add_argument("--round-mode", choices=["nearest", "floor", "ceil"], default="nearest")
    parser.add_argument("--tif", default="DAY")
    parser.add_argument("--expire-policy", choices=["session_end", "good_till_cancel"], default="session_end")

    parser.add_argument("--strategy", default="inside_bar_v1")
    parser.add_argument("--exchange", default="SMART/AMEX")
    parser.add_argument("--sec-type", default="STK")
    parser.add_argument("--currency", default="")
    parser.add_argument("--gtd-tz", default="America/New_York")

    parser.add_argument("--sizing", choices=["fixed", "pct_of_equity", "risk"], default="fixed")
    parser.add_argument("--qty", type=float, default=1.0)
    parser.add_argument("--equity", type=float, default=DEFAULT_INITIAL_CASH)
    parser.add_argument("--pos-pct", type=float, default=10.0)
    parser.add_argument("--risk-pct", type=float, default=DEFAULT_RISK_PCT)
    parser.add_argument("--min-qty", type=int, default=DEFAULT_MIN_QTY)
    parser.add_argument("--max-notional", type=float, default=None, help="Maximum notional per order (default: equity)")
    parser.add_argument("--tz", default=INSIDE_BAR_TIMEZONE)
    return parser


def _compute_qty(
    entry_price: float,
    stop_price: float,
    args: argparse.Namespace,
) -> int:
    min_qty = max(args.min_qty, 1)
    if args.sizing == "fixed":
        qty = qty_fixed(args.qty, min_qty=min_qty)
    elif args.sizing == "pct_of_equity":
        qty = qty_pct_of_equity(args.equity, args.pos_pct, entry_price, min_qty=min_qty)
    else:
        qty = qty_risk_based(
            entry_price=entry_price,
            stop_price=stop_price,
            equity=args.equity,
            risk_pct=args.risk_pct,
            tick_size=args.tick_size,
            round_mode=args.round_mode,
            min_qty=min_qty,
            max_notional=args.max_notional or args.equity,
        )
    return max(int(qty), 0)


def _format_good_til(ts: pd.Timestamp, target_tz: str) -> str:
    localized = ts.tz_convert(target_tz)
    tz_name = localized.tzname() or target_tz
    return f"{localized.strftime('%Y%m%d %H:%M:%S')} {tz_name}"


def _prepare_timestamp(ts_value: pd.Timestamp, tz: str) -> pd.Timestamp:
    ts = ts_value if isinstance(ts_value, pd.Timestamp) else pd.Timestamp(ts_value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(tz)
    else:
        ts = ts.tz_convert(tz)
    return ts


def _build_inside_bar_orders(
    signals: pd.DataFrame,
    ts_col: str,
    sessions: List[Session],
    args: argparse.Namespace,
) -> pd.DataFrame:
    orders: List[dict] = []

    for _, row in signals.iterrows():
        ts = _prepare_timestamp(row[ts_col], args.tz)
        symbol = str(row.get("Symbol") or row.get("symbol", "").upper())
        if not symbol:
            continue

        oco = _oco_id(symbol, ts)
        valid_from = ts.isoformat()
        valid_to = (
            _session_end(ts, sessions, args.tz).isoformat()
            if args.expire_policy == "session_end"
            else ts.isoformat()
        )

        def add_order(side: str, entry_col: str, sl_col: str, tp_col: str, source_tag: str) -> None:
            entry = row.get(entry_col)
            if pd.isna(entry):
                return
            stop = row.get(sl_col)
            target = row.get(tp_col)

            price = _round_price(float(entry), args.tick_size, args.round_mode)
            stop_price = _round_price(float(stop), args.tick_size, args.round_mode) if pd.notna(stop) else np.nan
            take_profit = _round_price(float(target), args.tick_size, args.round_mode) if pd.notna(target) else np.nan

            qty = _compute_qty(price, stop_price, args)
            if qty == 0:
                return

            notional = float(price * qty)
            total_buy = notional if side == "BUY" else 0.0
            total_sell = notional if side == "SELL" else 0.0

            orders.append(
                {
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "symbol": symbol,
                    "side": side,
                    "order_type": "STOP",
                    "price": price,
                    "stop_loss": stop_price,
                    "take_profit": take_profit,
                    "qty": qty,
                    "notional": notional,
                    "total_buy_value": total_buy,
                    "total_sell_value": total_sell,
                    "tif": args.tif,
                    "oco_group": oco,
                    "source": source_tag,
                }
            )

        add_order("BUY", "long_entry", "sl_long", "tp_long", "IB_LONG")
        add_order("SELL", "short_entry", "sl_short", "tp_short", "IB_SHORT")

    order_columns = [
        "valid_from",
        "valid_to",
        "symbol",
        "side",
        "order_type",
        "price",
        "stop_loss",
        "take_profit",
        "qty",
        "notional",
        "total_buy_value",
        "total_sell_value",
        "tif",
        "oco_group",
        "source",
    ]

    if not orders:
        return pd.DataFrame(columns=order_columns)
    return pd.DataFrame(orders, columns=order_columns)


def _build_rudometkin_orders(
    signals: pd.DataFrame,
    ts_col: str,
    sessions: List[Session],
    args: argparse.Namespace,
) -> pd.DataFrame:
    orders: List[dict] = []
    order_id = 1

    for _, row in signals.iterrows():
        ts = _prepare_timestamp(row[ts_col], args.tz)
        symbol = str(row.get("Symbol") or row.get("symbol", "").upper())
        if not symbol:
            continue

        strategy_label = str(row.get("setup") or row.get("Strategy") or args.strategy)
        session_end = (
            _session_end(ts, sessions, args.tz)
            if args.expire_policy == "session_end"
            else ts
        )
        good_til_date = _format_good_til(session_end, args.gtd_tz)
        trade_date = ts.tz_convert(args.gtd_tz).date().isoformat()

        def add_rudometkin_orders(entry_col: str, sl_col: str, side_value: int) -> None:
            nonlocal order_id
            entry = row.get(entry_col)
            if pd.isna(entry):
                return

            stop = row.get(sl_col)
            entry_price = _round_price(float(entry), args.tick_size, args.round_mode)
            stop_price = _round_price(float(stop), args.tick_size, args.round_mode) if pd.notna(stop) else np.nan

            qty = _compute_qty(entry_price, stop_price, args)
            if qty == 0:
                return

            parent_id = str(order_id)
            oca_id = parent_id
            action_entry = "BUY" if side_value > 0 else "SELL"
            action_exit = "SELL" if side_value > 0 else "BUY"

            order_row_entry = {
                "Date": trade_date,
                "TradeID": parent_id,
                "Strategy": strategy_label,
                "Side": side_value,
                "IsExit": 0,
                "OrderId": parent_id,
                "ParentId": "",
                "OcaId": "",
                "RTSym": symbol,
                "Symbol": symbol,
                "Expiry": "",
                "SecType": args.sec_type,
                "Currency": args.currency,
                "Exchange": args.exchange,
                "Action": action_entry,
                "Quantity": qty,
                "OrderType": "LMT",
                "TimeInForce": "GTD",
                "GoodAfterTime": "",
                "GoodTilDate": good_til_date,
                "AllHours": 0,
                "LmtPrice": float(entry_price),
                "AuxPrice": "",
                "Account": "",
                "FaGroup": "",
                "FaProfile": "",
                "FaMethod": "",
            }

            order_row_exit = {
                "Date": trade_date,
                "TradeID": parent_id,
                "Strategy": strategy_label,
                "Side": side_value,
                "IsExit": 1,
                "OrderId": "",
                "ParentId": parent_id,
                "OcaId": oca_id,
                "RTSym": symbol,
                "Symbol": symbol,
                "Expiry": "",
                "SecType": args.sec_type,
                "Currency": args.currency,
                "Exchange": args.exchange,
                "Action": action_exit,
                "Quantity": qty,
                "OrderType": "MOC",
                "TimeInForce": "DAY",
                "GoodAfterTime": "",
                "GoodTilDate": "",
                "AllHours": 0,
                "LmtPrice": "",
                "AuxPrice": "",
                "Account": "",
                "FaGroup": "",
                "FaProfile": "",
                "FaMethod": "",
            }

            orders.append(order_row_entry)
            orders.append(order_row_exit)
            order_id += 1

        add_rudometkin_orders("long_entry", "sl_long", 1)
        add_rudometkin_orders("short_entry", "sl_short", -1)

    columns = [
        "Date",
        "TradeID",
        "Strategy",
        "Side",
        "IsExit",
        "OrderId",
        "ParentId",
        "OcaId",
        "RTSym",
        "Symbol",
        "Expiry",
        "SecType",
        "Currency",
        "Exchange",
        "Action",
        "Quantity",
        "OrderType",
        "TimeInForce",
        "GoodAfterTime",
        "GoodTilDate",
        "AllHours",
        "LmtPrice",
        "AuxPrice",
        "Account",
        "FaGroup",
        "FaProfile",
        "FaMethod",
    ]

    if not orders:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(orders, columns=columns)


def _export_orders(orders_df: pd.DataFrame) -> Tuple[Path, pd.DataFrame]:
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    output = ORDERS_DIR / f"orders_{timestamp}.csv"
    orders_df.to_csv(output, index=False)
    orders_df.to_csv(ORDERS_DIR / "current_orders.csv", index=False)
    return output, orders_df


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"[WARN] Signals file missing: {source_path}")
        return 0

    ORDERS_DIR.mkdir(parents=True, exist_ok=True)

    signals = pd.read_csv(source_path)

    ts_col = "ts" if "ts" in signals.columns else "timestamp"
    if ts_col not in signals.columns:
        raise SystemExit("Signals CSV is missing 'ts' column")

    if signals.empty:
        sessions = _parse_sessions(args.sessions)
        if args.strategy.lower() == "rudometkin_moc":
            empty_df = _build_rudometkin_orders(signals, ts_col, sessions, args)
        else:
            empty_df = _build_inside_bar_orders(signals, ts_col, sessions, args)
        output, _ = _export_orders(empty_df)
        print(f"[OK] No signals found. Empty orders saved to {output}")
        return 0

    signals[ts_col] = _tz_to_local(signals[ts_col], args.tz)
    sessions = _parse_sessions(args.sessions)

    strategy_key = args.strategy.lower()
    if strategy_key == "rudometkin_moc":
        orders_df = _build_rudometkin_orders(signals, ts_col, sessions, args)
    else:
        orders_df = _build_inside_bar_orders(signals, ts_col, sessions, args)

    output, frame = _export_orders(orders_df)
    print(f"[OK] Orders → {output} (rows={len(frame)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
