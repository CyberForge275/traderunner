"""CLI for generating Rudometkin MOC strategy signals from parquet data."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from strategies import factory, registry


ROOT = Path(__file__).resolve().parents[1]
SIGNALS_DIR = Path("artifacts/signals")
DEFAULT_DATA_PATH = Path("artifacts/data_daily")
DEFAULT_UNIVERSE = Path("data/universe/rudometkin.parquet")
DEFAULT_TZ = "Europe/Berlin"


def _infer_symbols(data_path: Path) -> List[str]:
    return sorted({p.stem.upper() for p in data_path.glob("*.parquet")})


def _load_ohlcv(path: Path, target_tz: str) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if "timestamp" in frame.columns:
        ts = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
        frame = frame.drop(columns=["timestamp"])
        frame.index = ts
    elif not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError(f"{path} is missing a datetime index or 'timestamp' column")

    if frame.index.tz is None:
        frame.index = frame.index.tz_localize("UTC")

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [col for col in required if col not in frame.columns]
    if missing:
        raise ValueError(f"{path} missing OHLCV columns: {missing}")

    ordered = frame[required].sort_index()
    ordered.index.name = "timestamp"
    if ordered.index.tz is None:
        ordered.index = ordered.index.tz_localize("UTC")
    ordered = ordered.tz_convert(target_tz)
    ordered = ordered.rename(columns=lambda c: c.lower())
    return ordered.reset_index()


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Rudometkin MOC signals from parquet OHLCV data")
    parser.add_argument("--symbols", help="Comma-separated symbols; defaults to all files in --data-path")
    parser.add_argument("--data-path", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--tz", default=DEFAULT_TZ)
    parser.add_argument("--strategy", default="rudometkin_moc")
    parser.add_argument("--universe-path", default=str(DEFAULT_UNIVERSE))
    parser.add_argument("--entry-stretch1", type=float, default=0.035)
    parser.add_argument("--entry-stretch2", type=float, default=0.05)
    parser.add_argument(
        "--current-snapshot",
        default=str(SIGNALS_DIR / "current_signals_rudometkin.csv"),
        help="Path for latest snapshot CSV",
    )
    parser.add_argument("--output", default=None, help="Optional explicit output path")
    return parser.parse_args(argv)


def _build_config(args: argparse.Namespace) -> Dict[str, object]:
    return {
        "entry_stretch1": args.entry_stretch1,
        "entry_stretch2": args.entry_stretch2,
        "universe_path": args.universe_path,
    }


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)

    data_path = Path(args.data_path)
    data_path.mkdir(parents=True, exist_ok=True)

    if args.symbols:
        symbols = [sym.strip().upper() for sym in args.symbols.split(",") if sym.strip()]
    else:
        symbols = _infer_symbols(data_path)

    if not symbols:
        print("[WARN] No symbols discovered under", data_path)
        return 0

    registry.auto_discover("strategies")

    config = _build_config(args)
    strategy = factory.create_strategy(args.strategy, config)

    columns = [
        "ts",
        "Symbol",
        "long_entry",
        "short_entry",
        "sl_long",
        "sl_short",
        "tp_long",
        "tp_short",
        "setup",
        "score",
        "strategy",
        "strategy_version",
    ]
    rows: List[Dict[str, object]] = []

    for symbol in symbols:
        source = data_path / f"{symbol}.parquet"
        if not source.exists():
            print(f"[WARN] Missing parquet for {symbol}: {source}")
            continue

        try:
            ohlcv = _load_ohlcv(source, args.tz)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[WARN] Failed to load {symbol}: {exc}")
            continue

        signals = strategy.generate_signals(ohlcv.copy(), symbol, config)
        if not signals:
            continue

        for sig in signals:
            ts = pd.Timestamp(sig.timestamp)
            if ts.tzinfo is None:
                ts = ts.tz_localize(args.tz)
            
            # Convert to UTC for contract validation
            ts_utc = ts.tz_convert("UTC")
            
            # Determine entries based on signal type
            long_entry = None
            short_entry = None
            sl_long = None
            sl_short = None
            tp_long = None
            tp_short = None
            
            if sig.signal_type.upper() == "LONG":
                long_entry = sig.entry_price
                sl_long = sig.stop_loss
                tp_long = sig.take_profit
            elif sig.signal_type.upper() == "SHORT":
                short_entry = sig.entry_price
                sl_short = sig.stop_loss
                tp_short = sig.take_profit

            # Validate against SignalOutputSpec
            from axiom_bt.contracts.signal_schema import SignalOutputSpec
            from decimal import Decimal
            
            spec = SignalOutputSpec(
                symbol=symbol,
                timestamp=ts_utc,
                strategy=args.strategy,
                strategy_version="1.0.0",
                long_entry=Decimal(str(long_entry)) if long_entry is not None else None,
                short_entry=Decimal(str(short_entry)) if short_entry is not None else None,
                sl_long=Decimal(str(sl_long)) if sl_long is not None else None,
                sl_short=Decimal(str(sl_short)) if sl_short is not None else None,
                tp_long=Decimal(str(tp_long)) if tp_long is not None else None,
                tp_short=Decimal(str(tp_short)) if tp_short is not None else None,
                setup=sig.metadata.get("setup"),
                score=sig.metadata.get("score"),
                metadata=sig.metadata
            )

            # Map back to legacy columns for compatibility
            record: Dict[str, object] = {
                "ts": ts.isoformat(), # Keep original timezone in output for now if needed, or spec.timestamp.isoformat()
                "Symbol": spec.symbol,
                "long_entry": float(spec.long_entry) if spec.long_entry else np.nan,
                "short_entry": float(spec.short_entry) if spec.short_entry else np.nan,
                "sl_long": float(spec.sl_long) if spec.sl_long else np.nan,
                "sl_short": float(spec.sl_short) if spec.sl_short else np.nan,
                "tp_long": float(spec.tp_long) if spec.tp_long else np.nan,
                "tp_short": float(spec.tp_short) if spec.tp_short else np.nan,
                "setup": spec.setup,
                "score": spec.score,
                "strategy": spec.strategy,
                "strategy_version": spec.strategy_version
            }

            rows.append(record)

    result = pd.DataFrame(rows, columns=columns)
    if not result.empty:
        result.sort_values(["ts", "Symbol"], inplace=True)

    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    output = Path(args.output) if args.output else SIGNALS_DIR / f"signals_rudometkin_{timestamp}.csv"
    result.to_csv(output, index=False)

    current = Path(args.current_snapshot)
    current.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(current, index=False)

    print(f"[OK] Signals → {output} (rows={len(result)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
