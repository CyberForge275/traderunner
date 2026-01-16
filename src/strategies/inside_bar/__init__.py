"""InsideBar strategy package - Unified implementation."""

from __future__ import annotations

from .core import InsideBarCore, InsideBarConfig, RawSignal
from .config import load_config, get_default_config_path, load_default_config

from strategies.registry import register_strategy
from .signal_frame_builder import extend_insidebar_signal_frame
from .signal_schema import get_signal_frame_schema

class InsideBarPlugin:
    strategy_id = "insidebar_intraday"
    
    @staticmethod
    def get_schema(version: str):
        return get_signal_frame_schema(version)
    
    @staticmethod
    def extend_signal_frame(bars, params: dict):
        # We resolve the schema here to keep the framework-side simple
        version = params.get("strategy_version", "1.0.0")
        schema = get_signal_frame_schema(version)
        return extend_insidebar_signal_frame(
            bars=bars,
            schema=schema,
            strategy_id="insidebar_intraday",
            strategy_tag=schema.strategy_tag,
            params=params
        )


register_strategy(InsideBarPlugin())

__version__ = "2.0.0"

__all__ = [
    "InsideBarCore",
    "InsideBarConfig",
    "RawSignal",
    "load_config",
    "get_default_config_path",
    "load_default_config",
]
