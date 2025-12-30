# Deployment Sanity Check

Comprehensive script to verify deployment integrity and readiness.

## Usage

### On Debian Server

After deployment, run:

```bash
ssh mirko@192.168.178.55
cd /opt/trading/traderunner/scripts
./sanity_check.sh
```

### From Local Machine

```bash
ssh mirko@192.168.178.55 'bash -s' < /home/mirko/data/workspace/droid/traderunner/scripts/sanity_check.sh
```

## What It Checks

The script performs **12 comprehensive tests**:

### 1. **Directory Structure**
- ✅ `/opt/trading` exists
- ✅ `/opt/trading/automatictrader-api` exists
- ✅ `/opt/trading/traderunner` exists

### 2. **Virtual Environments**
- ✅ API `.venv` directory exists
- ✅ TradeRunner `.venv` directory exists

### 3. **Required Files**
- ✅ API files: `app.py`, `worker.py`, `storage.py`, `requirements.txt`
- ✅ TradeRunner files: `requirements.txt`, `README.md`

### 4. **Configuration Safety**
- ✅ `.env` file exists
- ⚠️ `AT_WORKER_MODE` setting (warns if `paper-send`)
- ⚠️ `ENV_ALLOW_SEND` setting (warns if enabled)

### 5. **Data Directories**
- ✅ API `data/` directory
- ✅ TradeRunner `artifacts/` directory
- 🔧 Auto-creates missing directories

### 6. **API Dependencies**
- ✅ FastAPI installed
- ✅ Uvicorn installed
- ✅ Pydantic installed
- ✅ SQLite3 available

### 7. **TradeRunner Dependencies**
- ✅ Pandas installed
- ✅ NumPy installed
- ✅ Streamlit installed

### 8. **Database**
- ✅ Database file exists
- ✅ Database has tables
- ⚠️ Warns if not initialized (OK for first run)

### 9. **Port Availability**
- ✅ Port 8080 available for API
- ⚠️ Warns if port in use

### 10. **API Startup Test**
- ✅ API app imports without errors
- ✅ No critical import failures

### 11. **Worker Startup Test**
- ✅ Worker imports without errors
- ✅ No critical import failures

### 12. **Signal Generation Test**
- ✅ Signal CLI modules import
- ⚠️ May warn about missing data (OK if not testing yet)

## Output

The script provides:
- ✅ **Green checkmarks** for passed tests
- ⚠️ **Yellow warnings** for non-critical issues
- ✗ **Red X** for failed tests
- **Summary** with counts of each

### Exit Codes
- `0` - All tests passed (warnings OK)
- `1` - One or more tests failed

## Example Output

```
========================================
  Trading System Deployment Sanity Check
========================================

[1/12] Checking directory structure...
✓ Deployment directory exists: /opt/trading
✓ API directory exists: /opt/trading/automatictrader-api
✓ TradeRunner directory exists: /opt/trading/traderunner

[2/12] Checking Python virtual environments...
✓ API virtual environment exists
✓ TradeRunner virtual environment exists

...

========================================
  Summary
========================================
Passed:   28
Warnings: 2
Failed:   0

✓ Deployment sanity check PASSED!

Next steps:
1. Start the API...
2. Start the worker...
3. Generate signals...
```

## Use Cases

### 1. After Initial Deployment
Verify everything was deployed correctly

### 2. After Updates
Confirm updates didn't break anything

### 3. Before Going Live
Final check before enabling paper trading

### 4. Troubleshooting
Quickly identify what's missing or misconfigured

### 5. CI/CD Integration
Add to deployment pipeline for automatic verification

## Integration with deploy_to_debian.sh

You can enhance the deployment script to automatically run sanity check:

```bash
# At the end of deploy_to_debian.sh
echo "Running sanity check..."
ssh ${SERVER} "cd /opt/trading/traderunner/scripts && ./sanity_check.sh"
```

## Customization

Edit the script to add custom checks:
- Additional dependencies
- Custom configuration validation
- Service-specific tests
- Performance benchmarks

## Notes

- Script assumes deployment to `/opt/trading`
- Requires `bash`, `sqlite3`, and `lsof` on server
- Safe to run multiple times
- Non-destructive (doesn't modify anything except creating missing data directories)
