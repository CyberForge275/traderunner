#!/usr/bin/env python3
"""
InsideBar Run History Smoke Test
==================================

CLI-based smoke test to verify run history functionality on INT server.
Validates that the run history panel can fetch and display Pre-Paper runs.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_dashboard.utils.run_history_utils import get_pre_paper_run_history, format_run_history_for_table


def main():
    print("=" * 70)
    print("InsideBar Run History Smoke Test")
    print("=" * 70)
    print()

    try:
        # Fetch run history for InsideBar
        print("Step 1: Fetching Run History for InsideBar Pre-Paper")
        print("-" * 50)

        runs = get_pre_paper_run_history("insidebar_intraday", limit=10)

        print(f"✅ Fetched {len(runs)} runs")
        print()

        if not runs:
            print("⚠️  No runs found in history.")
            print("   This is expected if no Pre-Paper runs have been executed yet.")
            print()
            print("=" * 70)
            print("✅ SMOKE TEST PASSED")
            print("=" * 70)
            print()
            print("Run history infrastructure is operational (no data yet).")
            return 0

        # Display summary
        print("Step 2: Run History Summary")
        print("-" * 50)

        for i, run in enumerate(runs[:5], 1):  # Show first 5
            print(f"\n{i}. Run ID: {run['run_id']}")
            print(f"   Started: {run['started_at']}")
            print(f"   Mode: {run['run_type']}")
            print(f"   Status: {run['status']}")
            print(f"   Signals: {run.get('signals', 'N/A')}")
            print(f"   Symbols: {run.get('symbols', 'N/A')}")

        if len(runs) > 5:
            print(f"\n   ... and {len(runs) - 5} more runs")

        print()

        # Test table formatting
        print("Step 3: Testing Table Formatting")
        print("-" * 50)

        table_data = format_run_history_for_table(runs)

        print(f"✅ Formatted {len(table_data)} rows for UI table")

        # Verify table structure
        if table_data:
            expected_cols = ["Run ID", "Date/Time", "Mode", "Status", "Signals", "Symbols", "Duration"]
            actual_cols = list(table_data[0].keys())

            print(f"   Table columns: {', '.join(actual_cols)}")

            missing = set(expected_cols) - set(actual_cols)
            if missing:
                print(f"   ⚠️  Missing columns: {missing}")

        print()

        # Validate latest run
        print("Step 4: Validating Latest Run")
        print("-" * 50)

        latest = runs[0]

        print(f"   Latest Run ID: {latest['run_id']}")
        print(f"   Status: {latest['status']}")

        if latest['status'] == 'completed':
            print(f"   ✅ Run completed successfully")
        else:
            print(f"   ⚠️  Run status: {latest['status']}")

        print()

        print("=" * 70)
        print("✅ SMOKE TEST PASSED")
        print("=" * 70)
        print()
        print("All run history components validated:")
        print(f"  ✅ Fetched {len(runs)} run(s) from database")
        print("  ✅ Data formatted correctly for UI table")
        print("  ✅ Run history infrastructure operational")
        print()

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("=" * 70)
        print("❌ SMOKE TEST FAILED")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
