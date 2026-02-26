from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd

from axiom_bt.pipeline.marketdata_stream_client import EnsureBarsRequest, MarketdataStreamClient
from core.settings.runtime_config import get_marketdata_data_root, get_runtime_config
from strategies.config.managers.harami_break_manager import HaramiBreakConfigManager


def _parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def normalize_date_window(
    *,
    start_date: dt.date,
    end_date: dt.date,
    today: dt.date | None = None,
) -> tuple[dt.date, dt.date]:
    """Clamp requested end date to yesterday to avoid incomplete current-day coverage."""
    now = today or dt.date.today()
    max_end = now - dt.timedelta(days=1)
    clamped_end = min(end_date, max_end)
    if clamped_end < start_date:
        raise ValueError(
            f"invalid date range after clamping current day: start={start_date} end={clamped_end}"
        )
    return start_date, clamped_end


def build_ensure_request(
    *,
    symbol: str,
    start_date: dt.date,
    end_date: dt.date,
    core: dict,
    data_root: Path,
) -> EnsureBarsRequest:
    missing = [
        key
        for key in ("timeframe_minutes", "session_timezone", "session_mode")
        if key not in core
    ]
    if missing:
        raise ValueError(f"missing required core keys for loader: {', '.join(missing)}")

    return EnsureBarsRequest(
        symbol=symbol.upper(),
        timeframe_minutes=int(core["timeframe_minutes"]),
        start_date=start_date,
        end_date=end_date,
        session_timezone=str(core["session_timezone"]),
        session_mode=str(core["session_mode"]),
        data_root=str(data_root),
    )


def load_local_dataframe(*, symbol: str, timeframe_minutes: int, data_root: Path) -> pd.DataFrame:
    path = data_root / "derived" / f"tf_m{int(timeframe_minutes)}" / f"{symbol.upper()}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"derived parquet not found: {path}")
    df = pd.read_parquet(path)
    if "ts" in df.columns and "timestamp" not in df.columns:
        df["timestamp"] = pd.to_datetime(df["ts"], unit="s", utc=True, errors="coerce")
    elif "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local harami_break data loader via marketdata-stream")
    p.add_argument("--symbol", required=True)
    p.add_argument("--start-date", required=True, type=_parse_date)
    p.add_argument("--end-date", required=True, type=_parse_date)
    p.add_argument("--strategy-version", default="1.0.0")
    p.add_argument("--print-head", type=int, default=5)
    return p


def main() -> int:
    args = _build_parser().parse_args()
    manager = HaramiBreakConfigManager()
    version_node = manager.get(args.strategy_version)
    core = version_node["core"]

    runtime_cfg = get_runtime_config()
    data_root = get_marketdata_data_root()
    client = MarketdataStreamClient(
        base_url=runtime_cfg.services.marketdata_stream_url,
        enabled=True,
    )

    start_date, end_date = normalize_date_window(
        start_date=args.start_date,
        end_date=args.end_date,
    )

    req = build_ensure_request(
        symbol=args.symbol,
        start_date=start_date,
        end_date=end_date,
        core=core,
        data_root=data_root,
    )
    ensure_resp = client.ensure_bars(req)
    df = load_local_dataframe(
        symbol=args.symbol,
        timeframe_minutes=req.timeframe_minutes,
        data_root=data_root,
    )

    print(
        f"loaded symbol={args.symbol.upper()} tf_m{req.timeframe_minutes} "
        f"rows={len(df)} range={start_date}..{end_date}"
    )
    print(f"ensure_status={ensure_resp.get('status')} gaps_after={ensure_resp.get('gaps_after')}")
    if args.print_head > 0 and not df.empty:
        print(df.head(args.print_head).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
