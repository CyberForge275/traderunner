import json
from pathlib import Path

import pandas as pd

from axiom_bt.pipeline.cli import main as pipeline_main


def _make_bars(tmpdir: Path) -> Path:
    ts = pd.date_range("2025-01-01", periods=6, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100, 101, 102, 103, 104, 105],
            "high": [101, 102, 103, 104, 105, 106],
            "low": [99, 100, 101, 102, 103, 104],
            "close": [100, 102, 101, 104, 103, 106],
            "volume": [1000] * len(ts),
        }
    )
    path = tmpdir / "bars.csv"
    df.to_csv(path, index=False)
    return path


def test_pipeline_manifest_contains_config_audit_block(tmp_path: Path):
    out = tmp_path / "run"
    bars = _make_bars(tmp_path)
    argv = [
        "--run-id",
        "run_manifest_cfg",
        "--out-dir",
        str(out),
        "--bars-path",
        str(bars),
        "--strategy-id",
        "insidebar_intraday",
        "--strategy-version",
        "1.0.0",
        "--symbol",
        "TEST",
        "--timeframe",
        "M5",
        "--requested-end",
        "2025-01-05",
        "--lookback-days",
        "5",
        "--initial-cash",
        "10000",
        "--fees-bps",
        "2.0",
        "--slippage-bps",
        "1.0",
    ]
    pipeline_main(argv)

    manifest = json.loads((out / "run_manifest.json").read_text())
    assert "config" in manifest
    config = manifest["config"]
    assert "resolved" in config and "sources" in config and "overrides" in config
    assert config["resolved"]["costs"]["commission_bps"] == 2.0
    assert config["resolved"]["costs"]["fees_bps"] == 2.0
    assert config["resolved"]["costs"]["slippage_bps"] == 1.0
    assert config["sources"]["costs.commission_bps"] == "cli"
    assert manifest["params"]["commission_bps"] == 2.0
    assert manifest["params"]["fees_bps"] == 2.0
    assert manifest["params"]["slippage_bps"] == 1.0


def test_pipeline_manifest_includes_base_config_metadata_when_provided(tmp_path: Path):
    out = tmp_path / "run_with_base"
    bars = _make_bars(tmp_path)
    base_config = tmp_path / "base_config.yaml"
    base_config.write_text(
        "\n".join(
            [
                "backtest:",
                "  initial_cash: 7500",
                "costs:",
                "  commission_bps: 1.5",
                "  slippage_bps: 0.5",
            ]
        )
    )
    argv = [
        "--run-id",
        "run_manifest_cfg_base",
        "--out-dir",
        str(out),
        "--bars-path",
        str(bars),
        "--strategy-id",
        "insidebar_intraday",
        "--strategy-version",
        "1.0.0",
        "--symbol",
        "TEST",
        "--timeframe",
        "M5",
        "--requested-end",
        "2025-01-05",
        "--lookback-days",
        "5",
        "--base-config",
        str(base_config),
    ]
    pipeline_main(argv)

    manifest = json.loads((out / "run_manifest.json").read_text())
    config = manifest["config"]
    assert config["base_config_path"] == str(base_config)
    assert isinstance(config["base_config_sha256"], str) and len(config["base_config_sha256"]) == 64
