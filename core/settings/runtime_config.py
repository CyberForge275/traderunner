from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml


DEFAULT_CONFIG_PATHS = (
    Path("/etc/trading/trading.yaml"),
    Path.home() / ".config" / "trading" / "trading.yaml",
    Path.cwd() / "config" / "trading.yaml",
)


class RuntimeConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimePaths:
    marketdata_data_root: Path | None
    trading_artifacts_root: Path | None


@dataclass(frozen=True)
class RuntimeServices:
    marketdata_stream_url: str | None


@dataclass(frozen=True)
class RuntimeFlags:
    pipeline_consumer_only: bool | None
    pipeline_auto_ensure_bars: bool | None


@dataclass(frozen=True)
class RuntimeConfig:
    config_path: Path | None
    paths: RuntimePaths
    services: RuntimeServices
    runtime: RuntimeFlags


def _to_abs_path(raw: str | None, key: str) -> Path | None:
    if raw is None or str(raw).strip() == "":
        return None
    p = Path(str(raw)).expanduser()
    if not p.is_absolute():
        raise RuntimeConfigError(f"{key} must be absolute path, got: {raw}")
    return p


def _as_bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def _first_existing(paths: Iterable[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def load_runtime_config(
    *,
    config_path: str | Path | None = None,
    search_paths: Iterable[Path] | None = None,
    strict: bool = False,
) -> RuntimeConfig:
    explicit = Path(config_path).expanduser() if config_path else None
    candidate = explicit
    if candidate is None:
        env_cfg = os.getenv("TRADING_CONFIG", "").strip()
        if env_cfg:
            candidate = Path(env_cfg).expanduser()
    if candidate is None:
        candidate = _first_existing(tuple(search_paths) if search_paths is not None else DEFAULT_CONFIG_PATHS)

    data = {}
    used_path = None
    if candidate is not None:
        if not candidate.exists():
            raise RuntimeConfigError(f"runtime config file not found: {candidate}")
        used_path = candidate
        loaded = yaml.safe_load(candidate.read_text())
        data = loaded or {}

    paths_cfg = data.get("paths") or {}
    services_cfg = data.get("services") or {}
    runtime_cfg = data.get("runtime") or {}

    md_root_raw = (
        paths_cfg.get("marketdata_data_root")
        or os.getenv("MARKETDATA_DATA_ROOT")
    )
    art_root_raw = (
        paths_cfg.get("trading_artifacts_root")
        or os.getenv("TRADING_ARTIFACTS_ROOT")
        or os.getenv("TRADERUNNER_ARTIFACTS_ROOT")
    )

    md_root = _to_abs_path(md_root_raw, "paths.marketdata_data_root")
    art_root = _to_abs_path(art_root_raw, "paths.trading_artifacts_root")

    if strict:
        if md_root is None:
            raise RuntimeConfigError(
                "missing paths.marketdata_data_root (config) and MARKETDATA_DATA_ROOT (env fallback)"
            )
        if art_root is None:
            raise RuntimeConfigError(
                "missing paths.trading_artifacts_root (config) and TRADING_ARTIFACTS_ROOT/TRADERUNNER_ARTIFACTS_ROOT (env fallback)"
            )

    stream_url = services_cfg.get("marketdata_stream_url") or os.getenv("MARKETDATA_STREAM_URL")

    return RuntimeConfig(
        config_path=used_path,
        paths=RuntimePaths(
            marketdata_data_root=md_root,
            trading_artifacts_root=art_root,
        ),
        services=RuntimeServices(marketdata_stream_url=(str(stream_url).strip() if stream_url else None)),
        runtime=RuntimeFlags(
            pipeline_consumer_only=_as_bool(runtime_cfg.get("pipeline_consumer_only")),
            pipeline_auto_ensure_bars=_as_bool(runtime_cfg.get("pipeline_auto_ensure_bars")),
        ),
    )


_RUNTIME_CONFIG: RuntimeConfig | None = None


def initialize_runtime_config(config_path: str | Path | None = None) -> RuntimeConfig:
    global _RUNTIME_CONFIG
    _RUNTIME_CONFIG = load_runtime_config(config_path=config_path, strict=True)
    return _RUNTIME_CONFIG


def get_runtime_config() -> RuntimeConfig:
    global _RUNTIME_CONFIG
    if _RUNTIME_CONFIG is None:
        _RUNTIME_CONFIG = load_runtime_config()
    return _RUNTIME_CONFIG


def reset_runtime_config_for_tests() -> None:
    global _RUNTIME_CONFIG
    _RUNTIME_CONFIG = None


def get_marketdata_data_root() -> Path:
    path = get_runtime_config().paths.marketdata_data_root
    if path is None:
        raise RuntimeConfigError(
            "missing paths.marketdata_data_root (config) and MARKETDATA_DATA_ROOT (env fallback)"
        )
    return path


def get_trading_artifacts_root() -> Path:
    path = get_runtime_config().paths.trading_artifacts_root
    if path is None:
        raise RuntimeConfigError(
            "missing paths.trading_artifacts_root (config) and TRADING_ARTIFACTS_ROOT/TRADERUNNER_ARTIFACTS_ROOT (env fallback)"
        )
    return path
