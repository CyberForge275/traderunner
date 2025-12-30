#!/usr/bin/env python3
"""
Session Filter Validation Script (NO PANDAS!)

Validates that all orders fall within configured session windows.
Uses only csv, json, datetime modules - no user-site pandas.

Usage:
  python3 validate_session_orders.py <run_dir>

Example:
  python3 validate_session_orders.py /opt/trading/traderunner/artifacts/backtests/251219_HOOD_session_test
"""
import sys
import csv
import json
from pathlib import Path
from datetime import datetime, time


def parse_iso_timestamp(ts_str):
    """Parse ISO timestamp with timezone (e.g., '2025-12-10 09:30:00-05:00')."""
    # Python 3.7+ supports fromisoformat for ISO 8601
    return datetime.fromisoformat(ts_str)


def extract_local_time(dt):
    """Extract HH:MM from datetime object."""
    return dt.time()


def is_in_window(t, window_start, window_end):
    """Check if time t is within [start, end)."""
    return window_start <= t < window_end


def validate_run(run_dir):
    """
    Validate orders against session windows.

    Returns:
        dict with keys: orders_total, orders_outside, offending_orders, GO/NO-GO
    """
    run_path = Path(run_dir)

    # Load run_meta.json for session config
    meta_path = run_path / "run_meta.json"
    if not meta_path.exists():
        return {"error": f"run_meta.json not found in {run_dir}"}

    with open(meta_path) as f:
        meta = json.load(f)

    session_windows_str = meta.get("params", {}).get("session_filter", [])
    session_tz = meta.get("params", {}).get("session_timezone", "unknown")

    if not session_windows_str:
        return {"info": "No session filter configured - skipping validation"}

    # Parse session windows
    windows = []
    for win_str in session_windows_str:
        start_str, end_str = win_str.split("-")
        h1, m1 = map(int, start_str.split(":"))
        h2, m2 = map(int, end_str.split(":"))
        windows.append((time(h1, m1), time(h2, m2)))

    # Load orders.csv
    orders_path = run_path / "orders.csv"
    if not orders_path.exists():
        return {"error": f"orders.csv not found in {run_dir}"}

    orders_total = 0
    orders_outside = 0
    offending = []

    with open(orders_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            orders_total += 1

            # Parse valid_from timestamp
            valid_from_str = row.get("valid_from", "")
            if not valid_from_str:
                continue

            dt = parse_iso_timestamp(valid_from_str)
            local_time = extract_local_time(dt)

            # Check if in ANY session window
            in_session = any(
                is_in_window(local_time, start, end)
                for start, end in windows
            )

            if not in_session:
                orders_outside += 1
                offending.append({
                    "valid_from": valid_from_str,
                    "local_time": local_time.strftime("%H:%M"),
                    "symbol": row.get("symbol"),
                    "side": row.get("side"),
                    "NY_time": row.get("NY_time"),
                    "Berlin_time": row.get("Berlin_time"),
                })

    # Verdict
    go_no_go = "GO" if orders_outside == 0 else "NO-GO"

    return {
        "run_dir": str(run_dir),
        "session_timezone": session_tz,
        "session_windows": session_windows_str,
        "orders_total": orders_total,
        "orders_outside": orders_outside,
        "offending_orders": offending[:20],  # First 20
        "GO/NO-GO": go_no_go,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 validate_session_orders.py <run_dir>")
        sys.exit(1)

    run_dir = sys.argv[1]
    result = validate_run(run_dir)

    # Output
    print("\n" + "=" * 70)
    print("SESSION FILTER VALIDATION REPORT")
    print("=" * 70)

    if "error" in result:
        print(f"\n❌ ERROR: {result['error']}")
        sys.exit(1)

    if "info" in result:
        print(f"\nℹ️  INFO: {result['info']}")
        sys.exit(0)

    print(f"\nRun Directory: {result['run_dir']}")
    print(f"Session Timezone: {result['session_timezone']}")
    print(f"Session Windows: {', '.join(result['session_windows'])}")
    print(f"\nOrders Total: {result['orders_total']}")
    print(f"Orders Outside Session: {result['orders_outside']}")

    if result['orders_outside'] > 0:
        print(f"\n⚠️  OFFENDING ORDERS (first 20):")
        print(f"{'valid_from':<30} {'Local Time':<12} {'Symbol':<6} {'Side':<5} {'NY_time':<25} {'Berlin_time':<25}")
        print("-" * 140)
        for order in result['offending_orders']:
            print(
                f"{order['valid_from']:<30} {order['local_time']:<12} "
                f"{order['symbol']:<6} {order['side']:<5} "
                f"{order.get('NY_time', 'N/A'):<25} {order.get('Berlin_time', 'N/A'):<25}"
            )

    print(f"\n{'=' * 70}")
    print(f"VERDICT: {result['GO/NO-GO']}")
    print("=" * 70)

    sys.exit(0 if result['GO/NO-GO'] == "GO" else 1)
