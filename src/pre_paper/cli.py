"""
PrePaper CLI Entry Point

Minimal CLI for live smoke tests and replay runs.
Orchestrates: bars → signals → plan → manifest → artifacts
"""

import argparse
import sys
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
import asyncio

# Add marketdata-monorepo to path
_MONOREPO_PATH = Path(__file__).parent.parent.parent.parent / "marketdata-monorepo" / "src"
if _MONOREPO_PATH.exists() and str(_MONOREPO_PATH) not in sys.path:
    sys.path.insert(0, str(_MONOREPO_PATH))

from pre_paper.marketdata_port import PrePaperMarketDataPort
from pre_paper.plan_writer import PlanWriter
from pre_paper.manifest_writer import ManifestWriter

logger = logging.getLogger(__name__)


def get_service():
    """
    Get MarketDataService based on ENV.
    
    ENV:
        MARKETDATA_PROVIDER: "fake" (default) or "real"
        SIGNALS_DB_PATH: Path to signals.db (for real provider)
    
    Returns:
        MarketDataService instance
    """
    provider = os.getenv("MARKETDATA_PROVIDER", "fake")
    
    if provider == "real":
        from marketdata_service import RealMarketDataService
        signals_db_path = os.getenv("SIGNALS_DB_PATH")
        logger.info(f"Using RealMarketDataService (signals_db={signals_db_path})")
        return RealMarketDataService(signals_db_path=signals_db_path)
    else:
        from marketdata_service import FakeMarketDataService
        logger.info("Using FakeMarketDataService (default)")
        return FakeMarketDataService(emit_ticks=False, bars_count=100)


async def run_prepaper(
    backtest_run_id: str,
    run_id: str,
    artifacts_root: Path,
    marketdata_service
):
    """
    Run PrePaper: bars → signals → plan → manifest → artifacts.
    
    Args:
        backtest_run_id: Source backtest run ID
        run_id: PrePaper run ID
        artifacts_root: Root artifacts directory
        marketdata_service: MarketDataService instance
    """
    # Create output directory
    output_dir = artifacts_root / "prepaper" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"PrePaper Run: {run_id} (source: {backtest_run_id})")
    logger.info(f"Output: {output_dir}")
    
    # Create port
    port = PrePaperMarketDataPort(marketdata_service)
    
    # Get bars (replay mode)
    start = datetime(2025, 1, 1, 9, 30, tzinfo=timezone.utc)
    end = datetime(2025, 1, 1, 10, 30, tzinfo=timezone.utc)
    
    logger.info(f"Fetching bars: {start} → {end}")
    bars_response = await port.get_replay_bars(
        symbol="AAPL",
        start=start,
        end=end,
        timeframe="M1"
    )
    
    logger.info(f"Received {len(bars_response.bars)} bars (data_hash={bars_response.provenance.data_hash[:8]}...)")
    
    # Generate order intents (simple: 1 order per 10 bars)
    orders = []
    for i, bar in enumerate(bars_response.bars):
        if i % 10 == 0:
            order = {
                "ts": bar.ts.isoformat(),
                "symbol": bar.symbol,
                "side": "BUY",
                "strategy_key": "test_strategy",
                "entry_price": bar.close,
                "sl": bar.close - 1.0,
                "tp": bar.close + 2.0
            }
            
            # Deterministic idempotency_key
            import hashlib
            canonical = f"{order['ts']}|{order['symbol']}|{order['side']}|{order['strategy_key']}|{order['entry_price']}|{order['sl']}|{order['tp']}"
            order["idempotency_key"] = hashlib.sha256(canonical.encode()).hexdigest()[:16]
            
            orders.append(order)
    
    logger.info(f"Generated {len(orders)} order intents")
    
    # Write plan.json
    plan_writer = PlanWriter(output_dir)
    plan_hash = plan_writer.write_plan(orders)
    logger.info(f"plan.json written (hash={plan_hash[:16]}...)")
    
    # Write signals to DB (via port)
    logger.info(f"Writing {len(orders)} signals to db...")
    write_result = await port.write_signals(
        lab="PREPAPER",
        run_id=run_id,
        source_tag="prepaper_plan_intent",
        signals=orders
    )
    logger.info(f"Signals written: {write_result.written}, duplicates skipped: {write_result.duplicates_skipped}")
    
    # Query signals count
    signals = await port.query_signals(
        lab="PREPAPER",
        run_id=run_id
    )
    
    # Write manifest
    manifest_writer = ManifestWriter(output_dir)
    manifest = manifest_writer.write_manifest(
        run_id=run_id,
        lab="PREPAPER",
        mode="replay",
        source_backtest_run_id=backtest_run_id,
        backtest_manifest={"identity": {"run_id": backtest_run_id}},  # Minimal
        marketdata_data_hash=bars_response.provenance.data_hash,
        plan_hash=plan_hash,
        signals_count=len(signals),
        strategy={"key": "test_strategy", "version": "1.0"},
        params={"lookback": 50},
        data={"symbol": "AAPL", "tf": "M1"},
        git_commit="unknown"
    )
    
    logger.info(f"run_manifest.json written")
    
    # Write run_meta.json (human-readable summary)
    run_meta = {
        "run_id": run_id,
        "lab": "PREPAPER",
        "mode": "replay",
        "source_backtest_run_id": backtest_run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SUCCESS",
        "orders_count": len(orders),
        "signals_count": len(signals),
        "artifacts": {
            "plan_json": str(output_dir / "plan.json"),
            "run_manifest_json": str(output_dir / "run_manifest.json")
        }
    }
    
    import json
    (output_dir / "run_meta.json").write_text(
        json.dumps(run_meta, indent=2, sort_keys=True),
        encoding="utf-8"
    )
    logger.info(f"run_meta.json written")
    
    logger.info(f"✅ PrePaper run complete: {output_dir}")
    
    return manifest


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PrePaper Lab - Order Plan Generator (Replay Mode)"
    )
    parser.add_argument(
        "--backtest-run-id",
        required=True,
        help="Source backtest run ID (e.g., 251215_144939_HOOD_M5_100d)"
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="PrePaper run ID (for artifacts and signals namespace)"
    )
    parser.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Artifacts root directory (default: artifacts)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    # Get service
    service = get_service()
    
    # Run
    try:
        asyncio.run(run_prepaper(
            backtest_run_id=args.backtest_run_id,
            run_id=args.run_id,
            artifacts_root=Path(args.artifacts_root),
            marketdata_service=service
        ))
    except Exception as e:
        logger.error(f"PrePaper run failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
