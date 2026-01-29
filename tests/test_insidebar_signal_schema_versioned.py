import pytest

from strategies.inside_bar.signal_schema import get_signal_frame_schema, schema_fingerprint


def test_schema_exists_and_base_columns():
    schema = get_signal_frame_schema("1.0.0")
    cols = {c.name for c in schema.all_columns()}
    for base in ["timestamp", "symbol", "open", "high", "low", "close", "volume"]:
        assert base in cols


def test_schema_fingerprint_stable():
    schema = get_signal_frame_schema("1.0.0")
    fp1 = schema_fingerprint(schema)
    fp2 = schema_fingerprint(schema)
    assert fp1 == fp2


def test_unknown_version_fails():
    with pytest.raises(ValueError):
        get_signal_frame_schema("9.9.9")
