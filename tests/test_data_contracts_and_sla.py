import pandas as pd
from datetime import datetime, timezone

from axiom_bt.contracts.data_contracts import DailyFrameSpec, IntradayFrameSpec
from axiom_bt.validators import DataQualitySLA, validate_ohlcv_dataframe


def _make_daily_frame() -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=3, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [101.0, 102.0, 103.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [100.5, 101.5, 102.5],
            "Volume": [1000, 1100, 1200],
        },
        index=idx,
    )


def _make_intraday_frame() -> pd.DataFrame:
    idx = pd.date_range("2025-01-01 14:30", periods=5, freq="5min", tz="UTC")
    return pd.DataFrame(
        {
            "Open": [100, 101, 102, 103, 104],
            "High": [101, 102, 103, 104, 105],
            "Low": [99, 100, 101, 102, 103],
            "Close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "Volume": [1000, 1000, 1000, 1000, 1000],
        },
        index=idx,
    )


def test_daily_frame_spec_valid():
    df = _make_daily_frame()
    is_valid, violations = DailyFrameSpec.validate(df, strict=False)
    assert is_valid
    assert violations == []


def test_intraday_frame_spec_valid():
    df = _make_intraday_frame()
    is_valid, violations = IntradayFrameSpec.validate(df, strict=False)
    assert is_valid
    assert violations == []


def test_validate_ohlcv_dataframe_contract_valid_without_sla():
    """Basic DailyFrame contract should pass without enforcing SLAs."""
    df = _make_daily_frame()
    is_valid, messages = validate_ohlcv_dataframe(df, enforce_sla=False, calendar=None)
    assert is_valid
    assert messages == []


def test_data_quality_sla_checks_all():
    df = _make_intraday_frame()
    # Sanity: check_all returns expected keys; completeness may fail on small test frame
    results = DataQualitySLA.check_all(
        df, calendar=None, reference_time=datetime.now(timezone.utc), skip_lateness=False
    )
    assert set(results.keys()) >= {"m5_completeness", "no_nan_ohlc", "no_dupe_index", "lateness"}

    # For a clean synthetic frame we expect no NaNs or duplicate timestamps
    assert results["no_nan_ohlc"].passed
    assert results["no_dupe_index"].passed

    # Completeness is allowed to fail here because the frame is intentionally tiny
    assert not DataQualitySLA.all_passed(results)
