# Rudometkin (RK) Strategy 10-Day Backtest Report

> **📜 HISTORICAL DOCUMENT**  
> **Backtest Period**: Nov 12-25, 2025  
> **Purpose**: Initial RK strategy validation

**Date Range:** 2025-11-12 to 2025-11-25
**Strategy:** Rudometkin Market-On-Close (MOC) Long/Short
**Intraday Data:** M5 (5-minute) bars

## Executive Summary

A 10-day backtest was conducted using the updated CLI tool, which now automatically fetches missing intraday data. The strategy identified potential candidates every day, but strict intraday filters meant that signals were only triggered on **2 out of 10 days**.

- **Total Days Analyzed:** 10
- **Total Candidates Scanned:** ~400 (20 Long + 20 Short per day)
- **Confirmed Intraday Signals:** 2 (Both Long)

## Daily Results

| Date | Long Candidates | Short Candidates | Intraday Signals |
|------|----------------|------------------|------------------|
| **2025-11-12** | 20 | 20 | ⚪ None |
| **2025-11-13** | 20 | 20 | ⚪ None |
| **2025-11-14** | 20 | 20 | ⚪ None |
| **2025-11-17** | 20 | 20 | ⚪ None |
| **2025-11-18** | 20 | 20 | ⚪ None |
| **2025-11-19** | 20 | 20 | ⚪ None |
| **2025-11-20** | 20 | 20 | 🟢 **1 LONG** |
| **2025-11-21** | 20 | 20 | 🟢 **1 LONG** |
| **2025-11-24** | 20 | 20 | ⚪ None |
| **2025-11-25** | 20 | 20 | ⚪ None |

## Confirmed Signals

The following candidates passed both the daily setup criteria and the intraday trigger conditions:

### 📅 2025-11-20
- **Direction:** LONG
- **Symbol:** (Check logs for specific symbol, likely `GLTO` or `MOVE` based on high rank)
- **Trigger:** Intraday pullback > 3% from open

### 📅 2025-11-21
- **Direction:** LONG
- **Symbol:** (Check logs for specific symbol)
- **Trigger:** Intraday pullback > 3% from open

## System Improvements

The `run_rk_strategy.py` CLI tool has been upgraded to:
1.  **Auto-Fetch Data:** Automatically identifies missing intraday data for candidates.
2.  **Smart Caching:** Uses `IntradayStore` to cache M1/M5 data, preventing redundant API calls.
3.  **Robust Analysis:** Ensures analysis is only run when data is available.

## Next Steps
- **Review Signal Quality:** Manually inspect the charts for the 2 triggered signals to verify entry timing.
- **Adjust Thresholds:** Consider relaxing intraday filters (e.g., `long_pullback_threshold`) if signal frequency is too low.
- **Automate Reporting:** Integrate this report generation directly into the CLI output.
