"""NDX momentum rotation strategy package (skeleton)."""

from strategies.registry import register_strategy

from .plugin import NdxMomentumRotationPlugin
from .strategy import build_strategy

register_strategy(NdxMomentumRotationPlugin())

__all__ = ["NdxMomentumRotationPlugin", "build_strategy"]
