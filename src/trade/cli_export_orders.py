from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from trade.position_sizing import qty_fixed, qty_pct_of_equity, qty_risk_based


ARTIFACTS = Path("artifacts")
SIGNALS_DIR = ARTIFACTS / "signals"
ORDERS_DIR = ARTIFACTS / "orders"
BERLIN_TZ = "Europe/Berlin"


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
    parser = argparse.ArgumentParser(description="Export OCO orders from inside-bar signals")
    parser.add_argument("--source", default=str(SIGNALS_DIR / "current_signals_ib.csv"))
    parser.add_argument("--sessions", default="15:00-16:00,16:00-17:00")
    parser.add_argument("--tick-size", type=float, default=0.01)
    parser.add_argument("--round-mode", choices=["nearest", "floor", "ceil"], default="nearest")
    parser.add_argument("--tif", default="DAY")
    parser.add_argument("--expire-policy", choices=["session_end", "good_till_cancel"], default="session_end")

    parser.add_argument("--sizing", choices=["fixed", "pct_of_equity", "risk"], default="fixed")
    parser.add_argument("--qty", type=float, default=1.0)
    parser.add_argument("--equity", type=float, default=10000.0)
    parser.add_argument("--pos-pct", type=float, default=10.0)
    parser.add_argument("--risk-pct", type=float, default=1.0)
    parser.add_argument("--min-qty", type=int, default=1)
    parser.add_argument("--tz", default=BERLIN_TZ)
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"[WARN] Signals file missing: {source_path}")
        return 0

    ORDERS_DIR.mkdir(parents=True, exist_ok=True)

    signals = pd.read_csv(source_path)
    if signals.empty:
        output = ORDERS_DIR / f"orders_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
        empty_cols = [
            "valid_from",
            "valid_to",
            "symbol",
            "side",
            "order_type",
            "price",
            "stop_loss",
            "take_profit",
            "qty",
            "tif",
            "oco_group",
            "source",
        ]
        pd.DataFrame(columns=empty_cols).to_csv(output, index=False)
        print(f"[OK] No signals found. Empty orders saved to {output}")
        return 0

    ts_col = "ts" if "ts" in signals.columns else "timestamp"
    if ts_col not in signals.columns:
        raise SystemExit("Signals CSV is missing 'ts' column")

    signals[ts_col] = _tz_to_local(signals[ts_col], args.tz)
    sessions = _parse_sessions(args.sessions)

    orders: List[dict] = []

    for _, row in signals.iterrows():
        ts_value = row[ts_col]
        ts = ts_value if isinstance(ts_value, pd.Timestamp) else pd.Timestamp(ts_value)
        if ts.tzinfo is None:
            ts = ts.tz_localize(args.tz)
        else:
            ts = ts.tz_convert(args.tz)
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

        def add_order(side: str, entry_col: str, sl_col: str, tp_col: str, source_tag: str):
            entry = row.get(entry_col)
            if pd.isna(entry):
                return
            stop = row.get(sl_col)
            target = row.get(tp_col)

            price = _round_price(float(entry), args.tick_size, args.round_mode)
            stop_price = _round_price(float(stop), args.tick_size, args.round_mode) if pd.notna(stop) else np.nan
            take_profit = _round_price(float(target), args.tick_size, args.round_mode) if pd.notna(target) else np.nan

            qty = args.qty
            sizing = args.sizing
            min_qty = max(args.min_qty, 1)

            if sizing == "fixed":
                qty = qty_fixed(qty, min_qty=min_qty)
            elif sizing == "pct_of_equity":
                qty = qty_pct_of_equity(args.equity, args.pos_pct, price, min_qty=min_qty)
            else:
                qty = qty_risk_based(
                    entry_price=price,
                    stop_price=stop_price,
                    equity=args.equity,
                    risk_pct=args.risk_pct,
                    tick_size=args.tick_size,
                    round_mode=args.round_mode,
                    min_qty=min_qty,
                )
            qty = max(int(qty), 0)

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
                    "tif": args.tif,
                    "oco_group": oco,
                    "source": source_tag,
                }
            )

        add_order("BUY", "long_entry", "sl_long", "tp_long", "IB_LONG")
        add_order("SELL", "short_entry", "sl_short", "tp_short", "IB_SHORT")

    orders_df = pd.DataFrame(orders)
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
        "tif",
        "oco_group",
        "source",
    ]
    if orders_df.empty:
        orders_df = pd.DataFrame(columns=order_columns)
    else:
        orders_df = orders_df[order_columns]

    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    output = ORDERS_DIR / f"orders_{timestamp}.csv"
    orders_df.to_csv(output, index=False)
    orders_df.to_csv(ORDERS_DIR / "current_orders.csv", index=False)
    print(f"[OK] Orders → {output} (rows={len(orders_df)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
