"""Compatibility shim for core.settings.

This top-level package exists to support legacy imports like
``from core.settings import DEFAULT_INITIAL_CASH`` when the canonical
implementation lives under ``src.core.settings``.

Do not add new logic here. All real settings and constants are defined
in ``src.core.settings`` and re-exported so that both import paths
resolve to the same source of truth.
"""

from __future__ import annotations

from src.core.settings import *  # noqa: F401,F403
