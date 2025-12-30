# Time Machine - Pre-Execution Verification ✅

## Server Status Check

### ✅ All Paths Verified

```bash
/opt/trading/marketdata-stream/data/signals.db           ✅ EXISTS
/opt/trading/automatictrader-api/data/automatictrader.db ✅ EXISTS
/opt/trading/traderunner/artifacts/backtests/            ✅ EXISTS
/opt/trading/traderunner/src/replay/                     ✅ DEPLOYED
```

### ✅ Services Running

- **automatictrader-worker:** ✅ RUNNING (PID 10657)
- **sqlite_bridge:** ⚠️ Not as systemd service (manual or script)
- **Dashboard:** ✅ RUNNING (Port 9001)

### ✅ Backtest Data

**Run:** `run_20251127_120221_ui_m5_APP_360d_10k`
- ✅ Copied to server
- ✅ 435 signals found
- ✅ Date filter working (2 signals on 2024-12-04)

### ✅ Backup System

**Automatic backup created:**
```
/opt/trading/marketdata-stream/data/signals_backup_20251206_213009.db
```

**Rollback command ready:**
```bash
ssh mirko@192.168.178.55
cd /opt/trading/traderunner
source .venv/bin/activate
python src/replay/time_machine.py --rollback
```

## Safety Checklist

- [x] Server paths exist and accessible
- [x] Automatic backup created before injection
- [x] Duplicate detection implemented
- [x] Rollback mechanism tested and ready
- [x] No changes to Pre-Papertrading Lab code
- [x] Worker is running and will process signals
- [x] Dashboard available for monitoring

## Ready to Execute

### Analyze Mode (Safe - No Changes)

```bash
ssh mirko@192.168.178.55
cd /opt/trading/traderunner
source .venv/bin/activate

python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k \
  --date 2024-12-04 \
  --analyze
```

### Inject Mode (LIVE - Writes to DB)

```bash
python src/replay/time_machine.py \
  --run-id run_20251127_120221_ui_m5_APP_360d_10k \
  --date 2024-12-04
```

**What will happen:**
1. ✅ Backup created automatically
2. ✅ 2 signals injected to signals.db
3. ✅ sqlite_bridge detects them (if running)
4. ✅ automatictrader-worker creates order intents
5. ✅ Dashboard shows activity
6. ✅ Can rollback anytime with `--rollback`

## Monitoring Commands

```bash
# Check signals in DB
ssh mirko@192.168.178.55 \
  "sqlite3 /opt/trading/marketdata-stream/data/signals.db 'SELECT COUNT(*) FROM signals'"

# Watch order intents being created
ssh mirko@192.168.178.55 \
  "watch -n 1 'sqlite3 /opt/trading/automatictrader-api/data/automatictrader.db \"SELECT COUNT(*) FROM order_intents WHERE status=\\\"planned\\\"\"'"

# View dashboard
open http://192.168.178.55:9001
```

## Rollback Procedure

If anything goes wrong:

```bash
ssh mirko@192.168.178.55
cd /opt/trading/traderunner
source .venv/bin/activate
python src/replay/time_machine.py --rollback
```

Restores from: `signals_backup_20251206_213009.db`

---

**All systems GO!** 🚀 Ready for injection whenever you are.
