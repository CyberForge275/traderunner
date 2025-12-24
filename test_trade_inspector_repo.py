#!/usr/bin/env python3
"""Test Trade Inspector repository and chart rendering."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from trading_dashboard.repositories.trade_repository import TradeRepository
from trading_dashboard.services.trade_detail_service import TradeDetailService

# Test loading bars
repo = TradeRepository(artifacts_root=Path("artifacts/backtests"))

print("="*60)
print("Testing Trade Inspector Data Loading")
print("="*60)

# Test the backfilled run
run_id = "251222_110818_IONQ_NEW1_IB_100d"

print(f"\n📂 Loading run: {run_id}")

# Load trades
trades = repo.load_trades(run_id)
print(f"  ✅ Trades: {len(trades) if trades is not None else 0} rows")

# Load evidence
evidence = repo.load_evidence(run_id)
print(f"  ✅ Evidence: {len(evidence) if evidence is not None else 0} rows")

# Load bars
bars_exec = repo.load_bars_exec(run_id)
print(f"  ✅ Exec bars: {bars_exec.shape if bars_exec is not None else 'None'}")

bars_signal = repo.load_bars_signal(run_id)
print(f"  ✅ Signal bars: {bars_signal.shape if bars_signal is not None else 'None'}")

if trades is not None and not trades.empty:
    print(f"\n🔍 Testing Trade Detail Service")
    service = TradeDetailService(repo)

    # Get first trade
    trade_id = 0
    detail = service.get_trade_detail(run_id, trade_id)

    if detail:
        print(f"  ✅ Trade {trade_id} loaded successfully")
        print(f"     - Symbol: {detail.trade_row.get('symbol')}")
        print(f"     - Side: {detail.trade_row.get('side')}")
        print(f"     - Entry: {detail.trade_row.get('entry_ts')}")
        print(f"     - Exit: {detail.trade_row.get('exit_ts')}")
        print(f"     - PnL: {detail.trade_row.get('pnl')}")
        print(f"     - Exec bars: {detail.exec_bars.shape if detail.exec_bars is not None else 'None'}")

        # Test chart building
        from trading_dashboard.plots.trade_inspector_plot import build_trade_chart

        fig = build_trade_chart(detail.trade_row, detail.exec_bars)
        print(f"  ✅ Chart generated successfully")
        print(f"     - Traces: {len(fig.data)}")
        print(f"     - Layout theme: {fig.layout.template}")
    else:
        print(f"  ❌ Failed to load trade detail")
else:
    print(f"\n⚠️  No trades to test")

print("\n" + "="*60)
print("Test Complete!")
print("="*60)
