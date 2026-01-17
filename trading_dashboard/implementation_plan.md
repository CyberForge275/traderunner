# Implementation Plan: Single Writer Policy for Refresh Interval

Establish a "Single Writer" architecture for the Dash Refresh Interval to resolve conflicts between Tab-switching and Job-polling.

## Proposed Changes

### 1. Centralized Coordination Store
Add a `dcc.Store` to provide a way for different modules to signal that they need the refresh interval enabled (e.g., during a backtest run).

#### [MODIFY] [app.py](file:///home/mirko/data/workspace/droid/traderunner/trading_dashboard/app.py)
- **Layout**: Add `dcc.Store(id="nav:refresh-policy", data={"bt_job_running": False})` inside the main layout.
- **Callback**: Update `control_refresh_interval` to:
    - Listen to `Nav.MAIN_TABS.active_tab` AND `nav:refresh-policy.data`.
    - Enable interval if `active_tab == "live-monitor"` OR `policy.get("bt_job_running") == True`.

### 2. Layout Cleanup
Remove the redundant Interval component that was creating the ID collision.

#### [MODIFY] [backtests.py](file:///home/mirko/data/workspace/droid/traderunner/trading_dashboard/layouts/backtests.py)
- **Layout**: [DELETE] the `dcc.Interval` with `id=Nav.REFRESH_INTERVAL` (lines 1053-1058).

### 3. Callback Refactoring
Update the backtest runner to signal its state via the store instead of trying to control the global interval directly.

#### [MODIFY] [run_backtest_callback.py](file:///home/mirko/data/workspace/droid/traderunner/trading_dashboard/callbacks/run_backtest_callback.py)
- **Callback `run_backtest`**: Update `Output` to target `"nav:refresh-policy", "data"` instead of `Nav.REFRESH_INTERVAL, "disabled"`.
- **Callback `check_job_status`**: Update `Output` to target `"nav:refresh-policy", "data"` instead of `Nav.REFRESH_INTERVAL, "disabled"`.

## Verification Plan

### Automated Guards
- **[NEW] [test_dash_no_duplicate_outputs.py](file:///home/mirko/data/workspace/droid/traderunner/tests/test_dash_no_duplicate_outputs.py)**:
    - Scans all files in `trading_dashboard` for `Output(Nav.REFRESH_INTERVAL, "disabled")`.
    - Fails if more than 1 occurrence is found repo-wide.

### Manual Verification
1. Start Dashboard on port 9001.
2. Confirm "Live Monitor" auto-refreshes.
3. Switch to "Backtests" (refresh should stop).
4. Start a Backtest (refresh should start automatically to poll status).
5. Wait for finish (refresh should stop).
