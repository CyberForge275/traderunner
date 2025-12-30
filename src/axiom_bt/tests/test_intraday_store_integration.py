"""Integration tests for IntradayStore."""

import pytest

from axiom_bt.intraday import IntradayStore, Timeframe


class TestIntradayStoreIntegration:
    """Integration tests for IntradayStore data quality."""

    @pytest.mark.skipif(
        not (IntradayStore().has_symbol("AAPL", timeframe=Timeframe.M1)),
        reason="AAPL M1 data not available"
    )
    def test_aapl_m1_low_nan_percentage(self):
        """AAPL M1 data should have <5% NaN rows after fix."""
        store = IntradayStore()
        df = store.load("AAPL", timeframe=Timeframe.M1, tz="America/New_York")

        # Check for NaN rows
        nan_mask = df[['open', 'high', 'low', 'close']].isna().any(axis=1)
        nan_count = nan_mask.sum()
        nan_pct = (nan_count / len(df)) * 100 if len(df) > 0 else 0

        assert nan_pct < 5.0, (f"Too many NaN rows in AAPL M1: {nan_pct:.1f}% "
                               f"({nan_count}/{len(df)}). Expected <5%.")

    @pytest.mark.skipif(
        not (IntradayStore().has_symbol("HOOD", timeframe=Timeframe.M1)),
        reason="HOOD M1 data not available"
    )
    def test_hood_m1_low_nan_percentage(self):
        """HOOD M1 data should have <5% NaN rows after fix."""
        store = IntradayStore()
        df = store.load("HOOD", timeframe=Timeframe.M1, tz="America/New_York")

        nan_mask = df[['open', 'high', 'low', 'close']].isna().any(axis=1)
        nan_count = nan_mask.sum()
        nan_pct = (nan_count / len(df)) * 100 if len(df) > 0 else 0

        assert nan_pct < 5.0, (f"Too many NaN rows in HOOD M1: {nan_pct:.1f}% "
                               f"({nan_count}/{len(df)}). Expected <5%.")

    @pytest.mark.skipif(
        not (IntradayStore().has_symbol("AAPL", timeframe=Timeframe.M5)),
        reason="AAPL M5 data not available"
    )
    def test_aapl_m5_low_nan_percentage(self):
        """AAPL M5 data should have <5% NaN rows."""
        store = IntradayStore()
        df = store.load("AAPL", timeframe=Timeframe.M5, tz="America/New_York")

        nan_mask = df[['open', 'high', 'low', 'close']].isna().any(axis=1)
        nan_count = nan_mask.sum()
        nan_pct = (nan_count / len(df)) * 100 if len(df) > 0 else 0

        assert nan_pct < 5.0, (f"Too many NaN rows in AAPL M5: {nan_pct:.1f}% "
                               f"({nan_count}/{len(df)}). Expected <5%.")

    @pytest.mark.skipif(
        not (IntradayStore().has_symbol("AAPL", timeframe=Timeframe.M1)),
        reason="AAPL M1 data not available"
    )
    def test_aapl_m1_has_extended_hours(self):
        """AAPL M1 should include extended hours (pre/after market)."""
        store = IntradayStore()
        df = store.load("AAPL", timeframe=Timeframe.M1, tz="America/New_York")

        # Check if we have bars outside RTH (09:30-16:00)
        # Extended hours: 04:00-09:30 (pre) and 16:00-20:00 (after)

        hours = df.index.hour
        minutes = df.index.minute

        # Pre-market: before 09:30
        pre_market = ((hours < 9) | ((hours == 9) & (minutes < 30))).sum()

        # After-hours: after 16:00
        after_hours = (hours >= 16).sum()

        # Should have some extended hours data
        extended_total = pre_market + after_hours

        # If we have recent data, expect some extended hours
        # (Not all days may have it, but recent ones should)
        if len(df) > 1000:  # Only check if we have substantial data
            assert extended_total > 0, (
                f"Expected some extended hours bars in AAPL M1. "
                f"Pre-market: {pre_market}, After-hours: {after_hours}"
            )
