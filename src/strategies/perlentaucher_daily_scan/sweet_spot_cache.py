"""Config and JSON cache helpers for Perlentaucher sweet-spot references."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .reference_set import ReferenceSetArtifacts

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_CONFIG_PATH = DATA_DIR / "sweet_spot_config.json"
DEFAULT_CACHE_PATH = DATA_DIR / "sweet_spot_cache.json"


def _normalize_pairs(pairs: list[Any]) -> list[list[str]]:
    out: list[list[str]] = []
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("sweet_spot_pairs must contain [symbol, as_of_date] pairs")
        symbol, as_of_date = pair
        out.append([str(symbol).strip().upper(), str(as_of_date)[:10]])
    return out


def normalize_sweet_spot_config(config: dict[str, Any]) -> dict[str, Any]:
    if "reference_set" not in config:
        raise ValueError("sweet spot config missing required key: reference_set")
    if "sweet_spot_pairs" not in config:
        raise ValueError("sweet spot config missing required key: sweet_spot_pairs")

    normalized = {
        "reference_set": str(config["reference_set"]).strip(),
        "sweet_spot_pairs": _normalize_pairs(list(config["sweet_spot_pairs"])),
    }
    if not normalized["sweet_spot_pairs"]:
        raise ValueError("sweet_spot_pairs cannot be empty")
    return normalized


def load_sweet_spot_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or DEFAULT_CONFIG_PATH
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("sweet spot config must be a JSON object")
    return normalize_sweet_spot_config(payload)


def save_sweet_spot_cache(
    *,
    config: dict[str, Any],
    reference_artifacts: ReferenceSetArtifacts,
    cache_path: Path | None = None,
) -> Path:
    path = cache_path or DEFAULT_CACHE_PATH
    normalized_config = normalize_sweet_spot_config(config)
    payload = {
        "config": normalized_config,
        "reference_frame": reference_artifacts.reference_frame.to_dict(orient="records"),
        "native_ranges": reference_artifacts.native_ranges,
        "zscore_ranges": reference_artifacts.zscore_ranges,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


def load_sweet_spot_cache(
    *,
    config: dict[str, Any],
    cache_path: Path | None = None,
) -> dict[str, Any] | None:
    path = cache_path or DEFAULT_CACHE_PATH
    if not path.exists():
        return None

    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("sweet spot cache must be a JSON object")
    if "config" not in payload or "reference_frame" not in payload:
        return None
    cached_config = normalize_sweet_spot_config(dict(payload.get("config", {})))
    expected_config = normalize_sweet_spot_config(config)
    if cached_config != expected_config:
        return None
    return payload


def reference_artifacts_from_cache_payload(payload: dict[str, Any]) -> ReferenceSetArtifacts:
    if not isinstance(payload, dict):
        raise ValueError("sweet spot cache payload must be a JSON object")
    return ReferenceSetArtifacts(
        reference_frame=pd.DataFrame(payload["reference_frame"]),
        native_ranges=dict(payload["native_ranges"]),
        zscore_ranges=dict(payload["zscore_ranges"]),
    )


__all__ = [
    "DEFAULT_CACHE_PATH",
    "DEFAULT_CONFIG_PATH",
    "load_sweet_spot_cache",
    "load_sweet_spot_config",
    "normalize_sweet_spot_config",
    "reference_artifacts_from_cache_payload",
    "save_sweet_spot_cache",
]
