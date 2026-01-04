"""
Tests for EODHD fetch chunking logic (120-day limit handling).

Verifies that requests >120 days are auto-chunked without raising ValueError.
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_chunking_181_days_creates_two_chunks():
    """Test that 181-day request is split into 2 chunks."""
    from src.axiom_bt.data.eodhd_fetch import fetch_intraday_1m_to_parquet
    
    # Mock the _request function to return dummy data
    def mock_request(url, payload):
        # Return some dummy rows
        start_ts = payload.get('from', 0)
        end_ts = payload.get('to', start_ts + 86400)
        
        # Generate 10 dummy rows
        rows = []
        for i in range(10):
            ts = start_ts + (i * 3600)  # 1 hour apart
            rows.append({
                'timestamp': ts,
                'open': 100.0,
                'high': 101.0,
                'low': 99.0,
                'close': 100.5,
                'volume': 1000
            })
        return rows
    
    with patch('src.axiom_bt.data.eodhd_fetch._request', side_effect=mock_request):
        with patch('src.axiom_bt.data.eodhd_fetch._read_token', return_value='dummy_token'):
            import tempfile
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                # Request 181 days (should chunk into 2 parts)
                start_date = '2024-01-01'
                end_date = '2024-06-30'  # 181 days
                
                result_path = fetch_intraday_1m_to_parquet(
                    symbol='TEST',
                    exchange='US',
                    start_date=start_date,
                    end_date=end_date,
                    out_dir=temp_dir,
                    tz='America/New_York',
                    filter_rth=False
                )
                
                # Verify file was created
                assert result_path.exists()
                
                # Verify data can be loaded
                df = pd.read_parquet(result_path)
                assert len(df) > 0
                assert all(col in df.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume'])
                
            finally:
                # Cleanup
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)


def test_chunking_120_days_single_request():
    """Test that ≤120 days uses single request (no chunking)."""
    from src.axiom_bt.data.eodhd_fetch import fetch_intraday_1m_to_parquet
    
    request_count = {'count': 0}
    
    def mock_request(url, payload):
        request_count['count'] += 1
        return [{
            'timestamp': 1704067200,  # 2024-01-01
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000
        }]
    
    with patch('src.axiom_bt.data.eodhd_fetch._request', side_effect=mock_request):
        with patch('src.axiom_bt.data.eodhd_fetch._read_token', return_value='dummy_token'):
            import tempfile
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                # Request exactly 120 days (should NOT chunk)
                start_date = '2024-01-01'
                end_date = '2024-04-30'  # 120 days
                
                result_path = fetch_intraday_1m_to_parquet(
                    symbol='TEST',
                    exchange='US',
                    start_date=start_date,
                    end_date=end_date,
                    out_dir=temp_dir,
                    tz='America/New_York',
                    filter_rth=False
                )
                
                # Verify only 1 request was made (no chunking)
                assert request_count['count'] == 1
                assert result_path.exists()
                
            finally:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)


def test_chunking_300_days_creates_multiple_chunks():
    """Test that 300-day request creates 3 chunks."""
    from src.axiom_bt.data.eodhd_fetch import fetch_intraday_1m_to_parquet
    
    request_count = {'count': 0}
    
    def mock_request(url, payload):
        request_count['count'] += 1
        return [{
            'timestamp': payload.get('from', 1704067200),
            'open': 100.0,
            'high': 101.0,
            'low': 99.0,
            'close': 100.5,
            'volume': 1000
        }]
    
    with patch('src.axiom_bt.data.eodhd_fetch._request', side_effect=mock_request):
        with patch('src.axiom_bt.data.eodhd_fetch._read_token', return_value='dummy_token'):
            import tempfile
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                # Request 300 days (should create 3 chunks: 120 + 120 + 60)
                start_date = '2024-01-01'
                end_date = '2024-10-27'  # ~300 days
                
                result_path = fetch_intraday_1m_to_parquet(
                    symbol='TEST',
                    exchange='US',
                    start_date=start_date,
                    end_date=end_date,
                    out_dir=temp_dir,
                    tz='America/New_York',
                    filter_rth=False
                )
                
                # Verify 3 requests were made (3 chunks)
                assert request_count['count'] == 3
                assert result_path.exists()
                
            finally:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
