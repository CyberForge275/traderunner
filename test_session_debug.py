#!/usr/bin/env python3
"""
Quick local test to capture session filter debug logs.
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from strategies.inside_bar.config import InsideBarConfig
from strategies.inside_bar.core import InsideBarCore

# Tracer to capture debug events
debug_events = []

def tracer(event):
    debug_events.append(event)
    if event['event'] in ['session_filter_config', 'bar_rejected_outside_session', 'final_filter_apply', 'final_filter_result']:
        print(f"[{event['event']}] {event}")

# Setup config with tight session windows
config = InsideBarConfig(
    session_timezone="America/New_York",
    session_windows=["10:00-11:00", "14:00-15:00"],
    atr_period=14,
    min_mother_bar_size=0.0,  # Disable for test
    risk_reward_ratio=2.0,
)

core = InsideBarCore(config)

# Create data spanning 09:00-11:00 (some outside, some inside session)
df = pd.DataFrame({
    'timestamp': pd.date_range('2025-12-17 09:00:00', periods=25, freq='5min', tz='America/New_York'),
    'open':  [120.0] * 25,
    'high':  [121.0, 120.5, 120.3] * 8 + [121.0],  # Pattern at various times
    'low':   [119.0, 119.8, 119.9] * 8 + [119.0],
    'close': [120.5] * 25,
})

print("=" * 70)
print("LOCAL DEBUG TEST - Session Filter Tracing")
print("=" * 70)
print(f"Config: session_tz={config.session_timezone}")
print(f"Config: session_windows={config.session_windows}")
print(f"Data: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(f"Data: {len(df)} bars from {df['timestamp'].dt.strftime('%H:%M').min()} to {df['timestamp'].dt.strftime('%H:%M').max()}")
print("=" * 70)

# Process
signals = core.process_data(df, symbol='TEST', tracer=tracer)

print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)
print(f"Signals Generated: {len(signals)}")

# Analyze events
session_config = [e for e in debug_events if e['event'] == 'session_filter_config']
gate_checks = [e for e in debug_events if e['event'] == 'session_gate_check']
rejections = [e for e in debug_events if e['event'] == 'bar_rejected_outside_session']
final_filter = [e for e in debug_events if e['event'] == 'final_filter_check']

print(f"\nDebug Events:")
print(f"  - session_filter_config: {len(session_config)}")
if session_config:
    print(f"    Config: {session_config[0]}")

print(f"  - session_gate_check: {len(gate_checks)}")
print(f"  - bar_rejected_outside_session: {len(rejections)}")

if rejections:
    print(f"\n  Rejections (first 5):")
    for r in rejections[:5]:
        print(f"    - {r.get('ts_local', 'N/A')}: {r.get('ts', 'N/A')}")

print(f"  - final_filter_check: {len(final_filter)}")
if final_filter:
    print(f"\n  Final Filter (first 5):")
    for f in final_filter[:5]:
        print(f"    - {f.get('ts_local', 'N/A')}: in_session={f.get('in_session', 'N/A')} side={f.get('side', 'N/A')}")

print(f"\nSignals timestamps:")
for sig in signals:
    ts = pd.to_datetime(sig.timestamp).tz_convert('America/New_York')
    print(f"  - {ts.strftime('%H:%M')}: {sig.side} @ {sig.entry_price}")

print("\n" + "=" * 70)
