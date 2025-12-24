# Time Machine - User Guide

## Overview

**Time Machine** replays successful backtest signals into the Pre-Papertrading Lab to test the signal → order intent pipeline without code changes.

## Quick Start

### 1. Analyze Backtest Run

See what signals are available:

```bash
cd ~/data/workspace/droid/traderunner
source .venv/bin/activate

python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k \
  --analyze
```

**Output:**
- Total signals found
- Date range
- BUY/SELL breakdown
- Sample signals

### 2. Test with Single Day (Recommended First Step)

```bash
python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k \
  --date 2024-12-04 \
  --analyze
```

Shows only signals from Dec 4, 2024.

### 3. Inject Signals (BATCH MODE)

**⚠️ This modifies signals.db - Backup is automatic!**

```bash
python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k \
  --date 2024-12-04
```

**What happens:**
1. ✅ Automatic backup created: `signals_backup_TIMESTAMP.db`
2. ✅ Signals injected into `signals.db`
3. ✅ `sqlite_bridge.py` picks them up
4. ✅ `automatictrader-worker` creates order intents
5. ✅ Dashboard shows activity

### 4. Monitor Pre-Papertrading Lab

Watch the pipeline work:

```bash
# On Debian server
ssh mirko@192.168.178.55

# Check signals inserted
sqlite3 /opt/trading/marketdata-stream/data/signals.db "SELECT COUNT(*) FROM signals"

# Watch order intents being created
watch -n 1 "sqlite3 /opt/trading/automatictrader-api/data/automatictrader.db 'SELECT COUNT(*) FROM order_intents WHERE status=\"planned\"'"

# View dashboard
# http://192.168.178.55:9001
```

### 5. Rollback if Needed

If something goes wrong:

```bash
python src/replay/time_machine.py --rollback
```

Restores from latest backup.

## Advanced Usage

### Inject Multiple Days

```bash
# Inject all signals from the run (435 signals!)
python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k
```

### Skip Backup (Not Recommended)

```bash
python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k \
  --date 2024-12-04 \
  --no-backup
```

### Custom Database Path

```bash
python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k \
  --signals-db /custom/path/to/signals.db
```

## Safety Features

1. **Automatic Backup:** Before every injection
2. **Duplicate Detection:** Skips already-existing signals
3. **Rollback:** One-command restore
4. **No Code Changes:** Pre-Papertrading Lab untouched
5. **Analyze Mode:** Preview before injecting

## Troubleshooting

### No signals found

**Check:**
- Run ID exists in `artifacts/backtests/`
- orders.csv contains data
- Date filter matches available data

### Signals not appearing in dashboard

**Check:**
- `sqlite_bridge.py` is running
- `automatictrader-worker` is running
- Database permissions correct

### Want to clear all test signals

```bash
# Backup first!
python src/replay/time_machine.py --rollback

# Or manually:
sqlite3 /opt/trading/marketdata-stream/data/signals.db "DELETE FROM signals WHERE strategy='InsideBar'"
```

## Example Workflow

```bash
# 1. Preview what's available
python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k \
  --analyze

# 2. Test one day
python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k \
  --date 2024-12-04

# 3. Check dashboard: http://192.168.178.55:9001

# 4. If good, inject more days or rollback
python src/replay/time_machine.py --rollback  # Undo
```

## Success Criteria

✅ **Signals appear in signals.db**
✅ **sqlite_bridge detects them**
✅ **Order intents created in trading.db**
✅ **Dashboard shows activity**
✅ **Worker logs show processing**

## Tips

- Start with 1 day to test pipeline
- Use analyze mode liberally
- Keep backups in case of issues
- Monitor logs during injection
- Dashboard updates every 5 seconds

Viel Erfolg! 🚀
