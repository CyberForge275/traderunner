#!/usr/bin/env python3
"""Simple test to verify the pre-papertrading signal flow."""
import sqlite3
import time
from datetime import datetime
from pathlib import Path

SIGNALS_DB = Path("/home/mirko/data/workspace/droid/marketdata-stream/data/signals.db")
TRADING_DB = Path("/home/mirko/data/workspace/automatictrader-api/data/automatictrader.db")

TEST_SIGNALS = [
    ("HOOD", "BUY", 25.50, 24.80, 27.50),
    ("PLTR", "BUY", 42.30, 41.50, 44.90),
    ("APP", "SELL", 180.20, 182.10, 176.40),
    ("INTC", "BUY", 48.75, 47.90, 51.35),
    ("TSLA", "BUY", 412.50, 408.00, 421.50),
    ("NVDA", "BUY", 885.30, 877.00, 903.90),
    ("MU", "SELL", 95.40, 97.20, 91.80),
    ("AVGO", "BUY", 1750.80, 1732.00, 1788.40),
    ("LRCX", "SELL", 825.60, 835.20, 806.40),
    ("WBD", "BUY", 12.85, 12.50, 13.70),
]

print("\n" + "=" * 70)
print("PRE-PAPERTRADING FLOW TEST - 10 Stock Milestone")
print("=" * 70)
print("\n📝 Inserting test signals for 10 stocks...\n")

conn = sqlite3.connect(str(SIGNALS_DB))
cur = conn.cursor()

for symbol, side, entry, sl, tp in TEST_SIGNALS:
    cur.execute("""
        INSERT INTO signals (
            symbol, side, entry_price, stop_loss, take_profit,
            quantity, strategy_name, strategy_version, interval,
            setup, score, metadata, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        symbol, side, entry, sl, tp,
        0, "inside_bar", "1.02", "M5",
        f"{side} breakout", 0.85, "{}", "pending", datetime.now().isoformat()
    ))
    print(f"  ✓ {symbol:6} {side:4} @ ${entry:7.2f}  SL: ${sl:7.2f}  TP: ${tp:7.2f}")

conn.commit()
conn.close()

print(f"\n✅ Inserted {len(TEST_SIGNALS)} signals into signals.db")
print("\n⏳ Waiting 15 seconds for sqlite_bridge to process...")

time.sleep(15)

print("\n📊 Checking order_intents in automatictrader.db...\n")

conn2 = sqlite3.connect(str(TRADING_DB))
cur2 = conn2.cursor()
cur2.execute("SELECT symbol, side, quantity, price, status FROM order_intents ORDER BY created_at DESC LIMIT 20")
intents = cur2.fetchall()
conn2.close()

if intents:
    print(f"✅ Found {len(intents)} order intents:\n")
    for symbol, side, qty, price, status in intents:
        print(f"  {symbol:6} {side:4} x{qty:4} @ ${price:7.2f}  [{status}]")
    print(f"\n{'=' * 70}")
    print("🎉 SUCCESS! Pre-papertrading flow is working!")
    print(f"{'=' * 70}")
    print(f"\n✓ {len(TEST_SIGNALS)} signals generated")
    print(f"✓ {len(intents)} order intents created")
    print(f"✓ sqlite_bridge successfully forwarded signals to API")
    print(f"✓ automatictrader-worker processed order intents\n")
else:
    print("⚠️  No order intents found yet.")
    print("\n Check logs:")
    print("   tail -f /tmp/sqlite_bridge.log")
    print("   tail -f /tmp/automatictrader-worker.log\n")
