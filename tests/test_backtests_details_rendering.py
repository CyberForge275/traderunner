"""
Regression tests for backtests details rendering.

These tests ensure that the UI can handle various data formats without crashing,
particularly around the steps serialization boundary.
"""

import pytest
from dataclasses import dataclass
from datetime import datetime
from trading_dashboard.layouts.backtests import create_backtest_detail


@dataclass
class MockRunStep:
    """Mock RunStep dataclass to simulate service response."""
    step_index: int
    step_name: str
    status: str
    timestamp: datetime = None
    duration_seconds: float = None
    details: str = None


def test_steps_render_accepts_runstep_objects_without_500():
    """
    Regression test: Ensure layout can handle RunStep dataclass objects
    without crashing (via normalization in callback).
    
    This test simulates the case where BacktestDetailsService.load_steps()
    returns dataclass objects instead of dicts. The callback should normalize
    these to dicts before passing to layout.
    """
    # Simulate what callback should do: normalize dataclass to dict
    from dataclasses import asdict
    
    # Create mock RunStep objects (what service returns)
    raw_steps = [
        MockRunStep(
            step_index=0,
            step_name="create_run_dir",
            status="completed",
            timestamp=datetime(2024, 12, 17, 10, 0, 0),
            duration_seconds=0.05,
            details="Created directory"
        ),
        MockRunStep(
            step_index=1,
            step_name="execute_strategy",
            status="completed",
            timestamp=datetime(2024, 12, 17, 10, 0, 5),
            duration_seconds=2.45,
            details="Strategy executed"
        ),
    ]
    
    # Normalize to dicts (what callback should do)
    normalized_steps = []
    for s in raw_steps:
        d = asdict(s)
        # Convert datetime to ISO string
        if d.get('timestamp'):
            d['timestamp'] = d['timestamp'].isoformat()
        # Rename duration_seconds to duration_s
        if 'duration_seconds' in d:
            d['duration_s'] = d.pop('duration_seconds')
        normalized_steps.append(d)
    
    # Create summary with normalized steps
    summary = {
        "run_name": "test_run",
        "status": "success",
        "strategy": "inside_bar",
        "timeframe": "M5",
        "symbols": ["HOOD"],
        "started_at": "2024-12-17T10:00:00",
        "finished_at": "2024-12-17T10:05:00",
        "failure_reason": None,
        "steps": normalized_steps,  # List[dict], not List[RunStep]
    }
    
    # Create mock empty dataframes
    import pandas as pd
    log_df = pd.DataFrame()
    
    # This should NOT crash - layout expects List[dict]
    try:
        result = create_backtest_detail(
            run_name="test_run",
            log_df=log_df,
            metrics={},
            summary=summary,
            equity_df=None,
            orders_df=None,
            fills_df=None,
            trades_df=None,
            rk_df=None,
        )
        
        # Verify we got a Div component back
        assert result is not None
        assert hasattr(result, 'children')  # Should be a Dash component
        
    except Exception as e:
        pytest.fail(f"Layout crashed with normalized steps: {e}")


def test_steps_render_with_missing_duration():
    """
    Test that layout handles steps without duration gracefully.
    """
    import pandas as pd
    
    summary = {
        "run_name": "test_run",
        "status": "success",
        "strategy": "inside_bar",
        "steps": [
            {
                "step_index": 0,
                "step_name": "create_run_dir",
                "status": "completed",
                "duration_s": None,  # Missing duration
                "details": "Created directory"
            }
        ]
    }
    
    log_df = pd.DataFrame()
    
    # Should not crash
    result = create_backtest_detail(
        run_name="test_run",
        log_df=log_df,
        metrics={},
        summary=summary,
    )
    
    assert result is not None


def test_steps_render_with_empty_steps():
    """
    Test that layout handles empty steps list gracefully.
    """
    import pandas as pd
    
    summary = {
        "run_name": "test_run",
        "status": "success",
        "strategy": "inside_bar",
        "steps": []  # Empty steps
    }
    
    log_df = pd.DataFrame()
    
    # Should not crash
    result = create_backtest_detail(
        run_name="test_run",
        log_df=log_df,
        metrics={},
        summary=summary,
    )
    
    assert result is not None
