import pandas as pd

from apps.streamlit.app import (
    FetchConfig,
    collect_symbols,
    parse_yaml_config,
    validate_date_range,
)


def test_collect_symbols_merges_and_validates():
    symbols, errors = collect_symbols(["TSLA"], "AAPL, bad*sym\nMSFT")
    assert symbols == ["AAPL", "MSFT", "TSLA"]
    assert "Invalid symbol format: BAD*SYM" in errors[0]


def test_validate_date_range_detects_inversion():
    errors = validate_date_range("2025-01-10", "2025-01-01")
    assert any("after" in msg for msg in errors)


def test_parse_yaml_config_handles_missing(monkeypatch, tmp_path):
    path, payload, errors = parse_yaml_config("/non/existing.yml")
    assert payload is None
    assert any("not found" in msg for msg in errors)

    config = tmp_path / "config.yml"
    config.write_text("name: test\nengine: replay\n")
    path, payload, errors = parse_yaml_config(str(config))
    assert path == str(config.resolve())
    assert errors == []
    assert payload["name"] == "test"


def test_fetch_config_symbols_to_fetch(tmp_path):
    data_dir = tmp_path
    index = pd.date_range("2025-01-01", periods=10, freq="D", tz="America/New_York")
    df = pd.DataFrame({"Close": range(10)}, index=index)
    df.to_parquet(data_dir / "TSLA.parquet")

    cfg = FetchConfig(
        symbols=["TSLA"],
        timeframe="M5",
        start="2025-01-02",
        end="2025-01-08",
        use_sample=False,
        force_refresh=False,
        data_dir=data_dir,
    )
    assert cfg.symbols_to_fetch() == []

    cfg_missing = FetchConfig(
        symbols=["TSLA"],
        timeframe="M5",
        start="2024-12-01",
        end="2025-02-01",
        use_sample=False,
        force_refresh=False,
        data_dir=data_dir,
    )
    assert cfg_missing.symbols_to_fetch() == ["TSLA"]

    cfg_force = FetchConfig(
        symbols=["TSLA"],
        timeframe="M5",
        start=None,
        end=None,
        use_sample=False,
        force_refresh=True,
        data_dir=data_dir,
    )
    assert cfg_force.symbols_to_fetch() == ["TSLA"]
