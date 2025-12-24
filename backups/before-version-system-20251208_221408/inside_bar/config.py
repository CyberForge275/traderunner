"""Configuration management for InsideBar strategy."""
import yaml
from pathlib import Path
from typing import Optional

from .core import InsideBarConfig


def load_config(config_path: Path) -> InsideBarConfig:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to YAML config file

    Returns:
        InsideBarConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Empty config file: {config_path}")

    params = data.get('parameters', {})

    # Create and validate config
    config = InsideBarConfig(**params)
    return config


def get_default_config_path() -> Path:
    """
    Get path to default config file.

    Searches in order:
    1. ~/data/workspace/droid/traderunner/config/inside_bar.yaml
    2. /opt/trading/traderunner/config/inside_bar.yaml
    3. ~/.trading/config/inside_bar.yaml

    Returns:
        Path to first config file found

    Raises:
        FileNotFoundError: If no config file found
    """
    candidates = [
        Path.home() / 'data' / 'workspace' / 'droid' / 'traderunner' / 'config' / 'inside_bar.yaml',
        Path('/opt/trading/traderunner/config/inside_bar.yaml'),
        Path.home() / '.trading' / 'config' / 'inside_bar.yaml',
    ]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        f"Config file not found. Searched in:\n" +
        "\n".join(f"  - {p}" for p in candidates)
    )


def load_default_config() -> InsideBarConfig:
    """
    Load config from default location.

    Returns:
        InsideBarConfig instance
    """
    config_path = get_default_config_path()
    return load_config(config_path)
