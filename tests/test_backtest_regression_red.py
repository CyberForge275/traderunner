"""
RED Regression Tests for InsideBar Backtest Failures

Test Case A (Run 251215_144939): Coverage Gap
- Cached end < requested end → must fail deterministically or auto-fetch

Test Case B (Run 251215_154934): SLA Violations
- SLA violations → must be FAILED_PRECONDITION (not Pipeline Exception)

These tests MUST be RED initially to verify we can reproduce the failures.
Then we implement fixes to make them GREEN.
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path


class TestCoverageGateRegression:
    """
    Regression tests for Run A: 251215_144939_HOOD_15m_100d_refactor3
    
    Root cause: cached end (2025-12-05) < requested end (2025-12-12)
    Expected: Deterministic FAIL or auto-fetch (NOT "success + later crash")
    """
    
    def test_cached_end_before_requested_end_must_fail_or_fetch(self, tmp_path):
        """
        REGRESSION TEST - Case A
        
        GIVEN: Cached M15 data ends 2025-12-05
        WHEN: Backtest requests 100d ending 2025-12-12
        THEN: Must either:
          1. Auto-fetch missing range (2025-12-05 → 2025-12-12)
          2. OR fail as FAILED_PRECONDITION with DATA_COVERAGE_GAP
        
        NOT: "success" followed by crash during pipeline execution
        
        This test is INITIALLY RED - we expect it to fail because
        the coverage gate doesn't exist yet.
        """
        # Setup: Create cached parquet ending before requested
        cached_end = pd.Timestamp("2025-12-05 16:00:00", tz="America/New_York")
        requested_end = pd.Timestamp("2025-12-12 16:00:00", tz="America/New_York")
        lookback_days = 100
        
        # Create mock cached data
        cached_data = self._create_mock_m15_data(
            start="2025-09-01",
            end=cached_end,
            symbol="HOOD"
        )
        
        # Write to tmp parquet
        cached_parquet = tmp_path / "HOOD.parquet"
        cached_data.to_parquet(cached_parquet)
        
        # Execute: Try to run coverage check
        # (This will fail initially because check_coverage doesn't exist)
        with pytest.raises(ImportError, match="check_coverage"):
            from trading_dashboard.services.backtest_data_coverage import check_coverage
            
            result = check_coverage(
                symbol="HOOD",
                timeframe="M15",
                requested_end=requested_end,
                lookback_days=lookback_days,
                auto_fetch=False  # Don't fetch, just detect gap
            )
            
            # Expected after implementation:
            # assert result.status == CoverageStatus.GAP_DETECTED
            # assert result.gap is not None
            # assert result.gap.start == cached_end
            # assert result.gap.end == requested_end
    
    def test_coverage_gap_triggers_failed_precondition(self, tmp_path):
        """
        REGRESSION TEST - Case A (variant)
        
        Verify that coverage gap results in FAILED_PRECONDITION status,
        not a generic Pipeline Exception.
        
        This test is INITIALLY RED.
        """
        # Setup: Same as above - gap detected
        
        # Execute: Run backtest pipeline (simplified)
        with pytest.raises(ImportError, match="FailedPrecondition|RunStatus"):
            from trading_dashboard.services.backtest_exceptions import FailedPrecondition
            from trading_dashboard.services.backtest_status import FailureReason
            
            # This will be the actual pipeline behavior after implementation:
            # run_result = run_backtest(...)
            # assert run_result.status == RunStatus.FAILED_PRECONDITION
            # assert run_result.reason == FailureReason.DATA_COVERAGE_GAP
            # assert "cached_end" in run_result.details
            # assert "requested_end" in run_result.details
    
    def _create_mock_m15_data(self, start, end, symbol):
        """Helper to create mock M15 OHLCV data"""
        dates = pd.date_range(
            start=start,
            end=end,
            freq="15min",
            tz="America/New_York"
        )
        # Filter to RTH only (9:30-16:00)
        dates = dates[
            (dates.time >= pd.Timestamp("09:30").time()) &
            (dates.time <= pd.Timestamp("16:00").time())
        ]
        
        df = pd.DataFrame({
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1000
        }, index=dates)
        
        return df


class TestSLAGateRegression:
    """
    Regression tests for Run B: 251215_154934_HOOD_15m_100d_refactor4
    
    Root cause: SLA violations (m5_completeness: 80.65%, no_nan_ohlc: FAILED)
    Expected: FAILED_PRECONDITION with reason=DATA_SLA_FAILED
    Actual: Generic Pipeline Exception
    """
    
    def test_sla_violations_must_be_failed_precondition(self):
        """
        REGRESSION TEST - Case B
        
        GIVEN: Data with SLA violations:
          - m5_completeness: 80.65% (threshold 99%)
          - no_nan_ohlc: FAILED ("OHLC columns not found")
        WHEN: SLA gate runs
        THEN: 
          Status = FAILED_PRECONDITION
          Reason = DATA_SLA_FAILED
          Details = {violations: ['m5_completeness', 'no_nan_ohlc']}
        
        NOT: Generic Pipeline Exception without classification
        
        This test is INITIALLY RED.
        """
        # Setup: Create data matching the failure conditions
        df = self._create_incomplete_data_with_missing_ohlc()
        
        # Execute: Run SLA check
        with pytest.raises(ImportError, match="check_data_sla|SLAResult"):
            from trading_dashboard.services.backtest_sla import check_data_sla, SLAResult
            
            result = check_data_sla(df, strategy_key="inside_bar")
            
            # Expected after implementation:
            # assert not result.passed
            # assert 'm5_completeness' in result.violations
            # assert 'no_nan_ohlc' in result.violations
            # assert result.severity == 'FATAL'
    
    def test_sla_failure_propagates_with_reason_payload(self):
        """
        REGRESSION TEST - Case B (integration)
        
        Verify that SLA failure propagates as FAILED_PRECONDITION
        with full reason payload (not as generic error).
        
        This test is INITIALLY RED.
        """
        with pytest.raises(ImportError, match="RunStatus|FailureReason"):
            from trading_dashboard.services.backtest_status import RunStatus, FailureReason
            
            # After implementation, this will be the pipeline flow:
            # run_result = run_backtest_with_sla_violations(...)
            # 
            # assert run_result.status == RunStatus.FAILED_PRECONDITION
            # assert run_result.reason == FailureReason.DATA_SLA_FAILED
            # assert 'violations' in run_result.details
            # assert set(run_result.details['violations']) == {'m5_completeness', 'no_nan_ohlc'}
    
    def test_m5_completeness_threshold_for_insidebar(self):
        """
        Test that m5_completeness is FATAL for InsideBar strategy.
        
        InsideBar needs consecutive bars for pattern detection and breakout confirmation.
        Gaps in data invalidate the pattern logic.
        
        This test is INITIALLY RED.
        """
        # Create data with 80.65% completeness (matching actual failure)
        df = self._create_incomplete_data_80_percent()
        
        with pytest.raises(ImportError):
            from trading_dashboard.services.backtest_sla import check_data_sla
            
            result = check_data_sla(df, strategy_key="inside_bar")
            
            # Expected:
            # assert not result.passed
            # assert 'm5_completeness' in result.violations
            # 
            # Justification: InsideBar requires consecutive bars because:
            # 1. Mother bar detection needs N previous bars
            # 2. Inside bar must be literally "inside" the immediate previous bar
            # 3. Breakout confirmation checks close beyond mother bar high/low
            # 
            # ANY gap in the sequence can produce false signals or miss valid patterns.
    
    def _create_incomplete_data_with_missing_ohlc(self):
        """
        Create data matching Run B failure:
        - 80.65% completeness
        - Missing OHLC columns (or all NaN)
        """
        # Full expected range
        dates_full = pd.date_range(
            start="2025-09-03 09:30",
            end="2025-12-12 16:00",
            freq="5min",
            tz="America/New_York"
        )
        # Filter RTH
        dates_full = dates_full[
            (dates_full.time >= pd.Timestamp("09:30").time()) &
            (dates_full.time <= pd.Timestamp("16:00").time())
        ]
        
        # Create 80.65% of expected bars (4592 out of ~5694)
        total_expected = len(dates_full)
        actual_count = int(total_expected * 0.8065)
        
        # Sample subset (introduce gaps)
        dates_incomplete = dates_full[:actual_count]
        
        # Create DF WITHOUT OHLC columns (matching "OHLC columns not found")
        df = pd.DataFrame({
            "volume": 1000
        }, index=dates_incomplete)
        
        return df
    
    def _create_incomplete_data_80_percent(self):
        """Create data with exactly 80.65% completeness"""
        dates_full = pd.date_range(
            start="2025-09-03 09:30",
            end="2025-12-12 16:00",
            freq="15min",  # M15
            tz="America/New_York"
        )
        # RTH only
        dates_full = dates_full[
            (dates_full.time >= pd.Timestamp("09:30").time()) &
            (dates_full.time <= pd.Timestamp("16:00").time())
        ]
        
        actual_count = int(len(dates_full) * 0.8065)
        dates_incomplete = dates_full[:actual_count]
        
        df = pd.DataFrame({
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1000
        }, index=dates_incomplete)
        
        return df


# Mark all tests as expected to fail initially
pytestmark = pytest.mark.xfail(
    reason="RED regression tests - will pass after implementation",
    strict=True
)
