"""Trading Dashboard package.

The Dash application object lives in ``trading_dashboard.app``.
Importing this package should not require the Dash runtime, so we
only expose basic configuration here.
"""

from .config import PORT, HOST, DEBUG  # noqa: F401

__version__ = "0.1.0"
__all__ = ["PORT", "HOST", "DEBUG"]
