import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import pytz
import aiohttp

from trading_dashboard.data_loading.loaders.eodhd_backfill import EODHDBackfill


class TestEODHDBackfill:
    """Unit tests for EODHD backfill."""

    @pytest.fixture
    def backfill(self):
        """Create EODHDBackfill instance."""
        return EODHDBackfill(api_key='test_key')

    @pytest.fixture
    def mock_eodhd_data(self):
        """Mock EODHD response with mixed sessions."""
        et_tz = pytz.timezone('America/New_York')

        # Generate mixed session data
        base_date = datetime(2025, 12, 11)
        timestamps = []

        # Pre-market: 8:00-9:30
        for hour in range(8, 10):
            for minute in range(0, 60, 5):
                if hour == 9 and minute >= 30:
                    break
                timestamps.append(et_tz.localize(
                    base_date.replace(hour=hour, minute=minute)
                ))

        # RTH: 9:30-16:00
        for hour in range(9, 16):
            for minute in range(0, 60, 5):
                if hour == 9 and minute < 30:
                    continue
                timestamps.append(et_tz.localize(
                    base_date.replace(hour=hour, minute=minute)
                ))

        # After-hours: 16:00-20:00
        for hour in range(16, 20):
            for minute in range(0, 60, 5):
                timestamps.append(et_tz.localize(
                    base_date.replace(hour=hour, minute=minute)
                ))

        return pd.DataFrame({
            'timestamp': timestamps,
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000
        })

    @pytest.mark.asyncio
    async def test_fetch_rth_candles_filters_correctly(
        self,
        backfill,
        mock_eodhd_data
    ):
        """Should filter EODHD data to RTH only."""
        with patch.object(
            backfill,
            '_fetch_from_api',
            new=AsyncMock(return_value=mock_eodhd_data)
        ):
            result = await backfill.fetch_rth_candles(
                symbol='APP',
                start=datetime(2025, 12, 11, 0, 0),
                end=datetime(2025, 12, 11, 23, 59)
            )

        # Should only have RTH candles (9:30-16:00 = 78 candles for M5)
        assert len(result) == 78

        # Verify all timestamps are RTH
        et_tz = pytz.timezone('America/New_York')
        from datetime import time as time_class
        for ts in result['timestamp']:
            ts_et = pd.to_datetime(ts).tz_convert(et_tz)
            t = ts_et.time()
            assert time_class(9, 30) <= t < time_class(16, 0)

    @pytest.mark.asyncio
    async def test_fetch_rth_candles_invalid_range(self, backfill):
        """Should raise ValueError if start >= end."""
        with pytest.raises(ValueError, match="must be before"):
            await backfill.fetch_rth_candles(
                symbol='APP',
                start=datetime(2025, 12, 12),
                end=datetime(2025, 12, 11)  # Before start!
            )

    @pytest.mark.asyncio
    async def test_fetch_rth_candles_empty_response(self, backfill):
        """Should handle empty EODHD response."""
        empty_df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        with patch.object(
            backfill,
            '_fetch_from_api',
            new=AsyncMock(return_value=empty_df)
        ):
            result = await backfill.fetch_rth_candles(
                symbol='APP',
                start=datetime(2025, 12, 11),
                end=datetime(2025, 12, 12)
            )

        assert len(result) == 0
        assert result.columns.tolist() == empty_df.columns.tolist()

    def test_estimate_candle_count(self, backfill):
        """Should estimate RTH candle count correctly."""
        # 1 business day, M5 interval
        # RTH = 390 min / 5 min = 78 candles
        count = backfill.estimate_candle_count(
            start=datetime(2025, 12, 11),  # Wednesday
            end=datetime(2025, 12, 11),
            interval_minutes=5
        )

        assert count == 78

        # 5 business days (Mon-Fri)
        # Dec 9-13, 2025 = Mon-Fri = 5 business days
        # But pd.bdate_range counts from start to end (4 business days, not 5)
        count_week = backfill.estimate_candle_count(
            start=datetime(2025, 12, 8),   # Monday
            end=datetime(2025, 12, 12),    # Friday
            interval_minutes=5
        )

        # 5 business days = 78 * 5 = 390 candles
        assert count_week == 78 * 5

    @pytest.mark.asyncio
    async def test_fetch_from_api_success(self, backfill):
        """Test successful API call."""
        # Mock aiohttp response
        mock_data = [
            {
                'timestamp': '2025-12-11 14:30:00',
                'open': 100.0,
                'high': 101.0,
                'low': 99.0,
                'close': 100.5,
                'volume': 1000
            }
        ]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_data)

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.get = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock()

        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await backfill._fetch_from_api(
                symbol='APP',
                interval='5m',
                start=datetime(2025, 12, 11, 9, 0),
                end=datetime(2025, 12, 11, 17, 0)
            )

        assert not result.empty
        assert 'timestamp' in result.columns
        assert len(result) == 1


    def test_missing_api_key(self):
        """Should raise ValueError if no API key provided."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="EODHD_API_KEY"):
                EODHDBackfill()
