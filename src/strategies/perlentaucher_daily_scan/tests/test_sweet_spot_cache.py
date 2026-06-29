from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from strategies.perlentaucher_daily_scan.reference_set import build_reference_set
from strategies.perlentaucher_daily_scan.sweet_spot_cache import (
    DEFAULT_CACHE_PATH,
    DEFAULT_CONFIG_PATH,
    load_sweet_spot_cache,
    load_sweet_spot_config,
    reference_artifacts_from_cache_payload,
    save_sweet_spot_cache,
)


def _reference_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["ATAI", "ATAI", "ATAI"],
            "price_short": [0.18, 0.19, 0.20],
            "price_mid": [0.07, 0.08, 0.09],
            "price_l_long": [-0.01, -0.005, 0.0],
            "vol_short": [4_000_000.0, 4_200_000.0, 4_400_000.0],
            "vol_mid": [1_600_000.0, 1_700_000.0, 1_800_000.0],
            "vol_l_long": [11_000.0, 11_500.0, 12_000.0],
        }
    )


def test_load_sweet_spot_config_reads_default_json() -> None:
    config = load_sweet_spot_config()

    assert DEFAULT_CONFIG_PATH.exists()
    assert config["reference_set"] == "default"
    assert config["sweet_spot_pairs"] == [["AXTI", "2025-08-20"]]


def test_save_and_load_sweet_spot_cache_roundtrip(tmp_path: Path) -> None:
    cache_path = tmp_path / "sweet_spot_cache.json"
    config = {
        "reference_set": "default",
        "sweet_spot_pairs": [["ATAI", "2026-04-17"], ["ATAI", "2026-04-20"]],
    }
    artifacts = build_reference_set(_reference_features())

    save_sweet_spot_cache(
        config=config,
        reference_artifacts=artifacts,
        cache_path=cache_path,
    )

    assert cache_path.exists()
    loaded = load_sweet_spot_cache(config=config, cache_path=cache_path)

    assert loaded is not None
    assert loaded["config"]["reference_set"] == "default"
    assert loaded["native_ranges"]["price_short"] == {"lower": 0.18, "upper": 0.2}
    assert len(loaded["reference_frame"]) == 3


def test_load_sweet_spot_cache_returns_none_for_mismatched_config(tmp_path: Path) -> None:
    cache_path = tmp_path / "sweet_spot_cache.json"
    artifacts = build_reference_set(_reference_features())
    save_sweet_spot_cache(
        config={"reference_set": "default", "sweet_spot_pairs": [["ATAI", "2026-04-17"]]},
        reference_artifacts=artifacts,
        cache_path=cache_path,
    )

    loaded = load_sweet_spot_cache(
        config={"reference_set": "default", "sweet_spot_pairs": [["ATAI", "2026-04-18"]]},
        cache_path=cache_path,
    )

    assert loaded is None


def test_default_cache_file_is_json_object_if_present() -> None:
    if not DEFAULT_CACHE_PATH.exists():
        return
    data = json.loads(DEFAULT_CACHE_PATH.read_text())
    assert isinstance(data, dict)


def test_reference_artifacts_from_cache_payload_restores_ranges(tmp_path: Path) -> None:
    cache_path = tmp_path / "sweet_spot_cache.json"
    artifacts = build_reference_set(_reference_features())
    config = {"reference_set": "default", "sweet_spot_pairs": [["ATAI", "2026-04-17"], ["ATAI", "2026-04-20"]]}
    save_sweet_spot_cache(config=config, reference_artifacts=artifacts, cache_path=cache_path)
    payload = load_sweet_spot_cache(config=config, cache_path=cache_path)
    restored = reference_artifacts_from_cache_payload(payload)
    assert restored.native_ranges == artifacts.native_ranges
    assert restored.zscore_ranges == artifacts.zscore_ranges
    assert list(restored.reference_frame["symbol"]) == ["ATAI", "ATAI", "ATAI"]
