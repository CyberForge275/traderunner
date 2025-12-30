"""
Enhanced logging utilities for visualization layer with debug mode support.

Provides decorators and context managers for detailed performance tracking
and error reporting during chart building.
"""
import logging
import functools
import time
import os
from typing import Callable, Any, TypeVar
from contextlib import contextmanager

# Module logger
logger = logging.getLogger(__name__)

# Type variable for decorators
F = TypeVar('F', bound=Callable[..., Any])

# Debug mode flag (can be set via environment variable or runtime)
_DEBUG_MODE = os.getenv("DASHBOARD_DEBUG", "false").lower() in ("true", "1", "yes")


def set_debug_mode(enabled: bool) -> None:
    """
    Enable or disable debug mode at runtime for all visualization loggers.

    Args:
        enabled: True to enable debug logging, False for normal logging

    Examples:
        >>> from visualization.plotly.logging_utils import set_debug_mode
        >>> set_debug_mode(True)  # Enable verbose logging
        🔧 Visualization debug mode: ON
    """
    global _DEBUG_MODE
    _DEBUG_MODE = enabled

    # Set level for all visualization loggers
    level = logging.DEBUG if enabled else logging.INFO
    vis_logger = logging.getLogger("trading_dashboard.visualization")
    vis_logger.setLevel(level)

    # Also set for current module
    logger.setLevel(level)

    logger.info(f"🔧 Visualization debug mode: {'ON ✓' if enabled else 'OFF'}")


def is_debug_mode() -> bool:
    """Check if debug mode is currently enabled."""
    return _DEBUG_MODE


def log_chart_build(func: F) -> F:
    """
    Decorator to log chart building with performance metrics and error handling.

    Logs:
    - Start of chart building with config info
    - DataFrame shapes and columns (in debug mode)
    - Execution time in milliseconds
    - Number of traces in resulting figure
    - Detailed error information on failure

    Usage:
        @log_chart_build
        def build_price_chart(ohlcv, indicators, config):
            ...

    Args:
        func: Chart builder function to decorate

    Returns:
        Decorated function with logging
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        func_name = func.__name__

        # Extract config for logging if present (look for dataclass instances)
        config_info = ""
        config_obj = None
        for arg in args:
            if hasattr(arg, "__dataclass_fields__"):  # Is a dataclass
                config_info = f" config={arg.__class__.__name__}"
                config_obj = arg
                break

        logger.info(f"📊 Building chart: {func_name}{config_info}")

        if _DEBUG_MODE:
            # Log detailed input info
            logger.debug(f"  → Function: {func.__module__}.{func_name}")
            logger.debug(f"  → Args: {len(args)} positional, {len(kwargs)} keyword")

            # Log DataFrame info if present
            for i, arg in enumerate(args):
                if hasattr(arg, "shape") and hasattr(arg, "columns"):  # Likely pandas DataFrame
                    cols = list(arg.columns)[:10]  # Limit column list
                    cols_str = ', '.join(cols)
                    if len(arg.columns) > 10:
                        cols_str += f", ... ({len(arg.columns)} total)"
                    logger.debug(f"  → DataFrame arg[{i}]: shape={arg.shape}, cols=[{cols_str}]")

                    # Check for datetime index
                    if hasattr(arg.index, "dtype") and "datetime" in str(arg.index.dtype):
                        logger.debug(f"      Index: {arg.index[0]} to {arg.index[-1]}")

            # Log config details if present
            if config_obj:
                logger.debug(f"  → Config: {config_obj}")

        start_time = time.perf_counter()

        try:
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Log trace count if it's a Plotly figure
            trace_count = "?"
            if hasattr(result, "data"):
                trace_count = len(result.data)

            logger.info(
                f"✅ Chart built: {func_name} "
                f"({elapsed_ms:.1f}ms, {trace_count} traces)"
            )

            if _DEBUG_MODE and hasattr(result, "layout"):
                # Log figure structure details
                layout_dict = result.layout.to_plotly_json()
                layout_keys = list(layout_dict.keys())[:15]
                logger.debug(f"  → Figure layout keys: {layout_keys}")

                if hasattr(result, "data"):
                    trace_types = [trace.type for trace in result.data]
                    logger.debug(f"  → Trace types: {trace_types}")

            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"❌ Chart build failed: {func_name} "
                f"({elapsed_ms:.1f}ms, {type(e).__name__}: {e})"
            )

            if _DEBUG_MODE:
                logger.exception("  📋 Full traceback:")
            else:
                logger.error(f"  💡 Hint: Set DASHBOARD_DEBUG=true for full traceback")

            raise  # Re-raise to let caller handle

    return wrapper  # type: ignore


@contextmanager
def log_data_preparation(description: str):
    """
    Context manager for logging data preparation steps with timing.

    Usage:
        with log_data_preparation("Filtering market hours"):
            df = df[df.index.hour.between(9, 16)]

    Args:
        description: Human-readable description of the preparation step

    Yields:
        None

    Examples:
        >>> with log_data_preparation("Computing moving averages"):
        ...     df['ma_20'] = df['close'].rolling(20).mean()
        🔄 Computing moving averages...
          ✓ Computing moving averages (12.3ms)
    """
    start = time.perf_counter()

    if _DEBUG_MODE:
        logger.debug(f"🔄 {description}...")

    try:
        yield

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error(f"  ✗ {description} failed ({elapsed_ms:.1f}ms): {e}")
        raise

    else:
        elapsed_ms = (time.perf_counter() - start) * 1000

        if _DEBUG_MODE:
            logger.debug(f"  ✓ {description} ({elapsed_ms:.1f}ms)")


def log_data_info(df: Any, label: str = "DataFrame") -> None:
    """
    Log detailed information about a DataFrame (only in debug mode).

    Args:
        df: pandas DataFrame to inspect
        label: Label for the DataFrame in logs

    Examples:
        >>> log_data_info(ohlcv_df, "OHLCV Data")
        📋 OHLCV Data: shape=(390, 5), ...
    """
    if not _DEBUG_MODE:
        return

    if not hasattr(df, "shape"):
        logger.debug(f"📋 {label}: Not a DataFrame (type={type(df).__name__})")
        return

    info_parts = [f"shape={df.shape}"]

    if hasattr(df, "columns"):
        cols = list(df.columns)
        info_parts.append(f"cols={cols}")

    if hasattr(df, "index") and len(df) > 0:
        if hasattr(df.index, "dtype") and "datetime" in str(df.index.dtype):
            info_parts.append(f"time_range=[{df.index[0]} → {df.index[-1]}]")
        else:
            info_parts.append(f"index=[{df.index[0]} ... {df.index[-1]}]")

    # Check for null values
    if hasattr(df, "isnull"):
        null_count = df.isnull().sum().sum()
        if null_count > 0:
            info_parts.append(f"nulls={null_count}")

    logger.debug(f"📋 {label}: {', '.join(info_parts)}")
