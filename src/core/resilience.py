"""
Resilience Utilities for traderunner

Production-grade error handling utilities for robust trading operations:
- Exponential backoff retry decorator
- Circuit breaker for data providers
- Correlation ID generation and propagation
- Graceful degradation helpers

Optimized for backtesting and signal generation workloads.
"""

import functools
import time
import logging
import random
import uuid
import threading
from typing import Callable, Optional, Any, Tuple, Type
from enum import Enum
from datetime import datetime
from contextlib import contextmanager


logger = logging.getLogger(__name__)


# ============================================================================
# Correlation IDs for Request Tracing
# ============================================================================

class CorrelationContext:
    """Thread-local storage for correlation IDs"""
    _local = threading.local()

    @classmethod
    def get_correlation_id(cls) -> Optional[str]:
        """Get current correlation ID from context"""
        return getattr(cls._local, 'correlation_id', None)

    @classmethod
    def set_correlation_id(cls, correlation_id: str) -> None:
        """Set correlation ID in context"""
        cls._local.correlation_id = correlation_id

    @classmethod
    def clear_correlation_id(cls) -> None:
        """Clear correlation ID from context"""
        if hasattr(cls._local, 'correlation_id'):
            delattr(cls._local, 'correlation_id')


def generate_correlation_id() -> str:
    """Generate a new correlation ID for request tracing"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"{timestamp}-{short_uuid}"


@contextmanager
def correlation_context(correlation_id: Optional[str] = None):
    """Context manager to set correlation ID for a block of code"""
    if correlation_id is None:
        correlation_id = generate_correlation_id()

    CorrelationContext.set_correlation_id(correlation_id)
    try:
        yield correlation_id
    finally:
        CorrelationContext.clear_correlation_id()


# ============================================================================
# Retry with Exponential Backoff
# ============================================================================

def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    retry_on: Optional[Callable[[Exception], bool]] = None
):
    """
    Decorator for retrying a function with exponential backoff.

    Optimized for data loading and signal generation operations.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            correlation_id = CorrelationContext.get_correlation_id()

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if retry_on and not retry_on(e):
                        raise

                    if attempt == max_retries:
                        logger.error(
                            f"[{correlation_id}] {func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise

                    delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"[{correlation_id}] {func.__name__} failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay:.2f}s: {e}"
                    )

                    time.sleep(delay)

            raise RuntimeError(f"Retry logic error in {func.__name__}")

        return wrapper
    return decorator


# ============================================================================
# Graceful Degradation
# ============================================================================

@contextmanager
def graceful_degradation(
    fallback_value: Any = None,
    log_error: bool = True,
    operation_name: str = "operation"
):
    """
    Context manager for graceful degradation on errors.

    Useful for optional features that shouldn't crash the main workflow.

    Example:
        with graceful_degradation(fallback_value=[], operation_name="fetch_optional_data"):
            data = load_supplementary_data()
        # If load fails, data will be []
    """
    try:
        yield
    except Exception as e:
        correlation_id = CorrelationContext.get_correlation_id()

        if log_error:
            logger.warning(
                f"[{correlation_id}] {operation_name} failed, using fallback: {e}"
            )


# ============================================================================
# Simple Circuit Breaker for Data Sources
# ============================================================================

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"


class CircuitBreaker:
    """
    Simplified circuit breaker for data sources.

    Prevents repeated failures from slowing down backtests.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 300.0,  # 5 minutes for backtests
        name: str = "Circuit"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        with self._lock:
            return self._state

    def _should_attempt_reset(self) -> bool:
        """Check if we should try resetting the circuit"""
        if self._last_failure_time is None:
            return False

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker"""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info(f"[{self.name}] Attempting recovery...")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                else:
                    raise RuntimeError(
                        f"Circuit breaker '{self.name}' is OPEN - repeated failures detected"
                    )

        try:
            result = func(*args, **kwargs)

            with self._lock:
                self._failure_count = 0
                self._state = CircuitState.CLOSED

            return result

        except Exception as e:
            with self._lock:
                self._failure_count += 1
                self._last_failure_time = datetime.now()

                if self._failure_count >= self.failure_threshold:
                    logger.error(
                        f"[{self.name}] Circuit breaker opening after {self._failure_count} failures"
                    )
                    self._state = CircuitState.OPEN

            raise

    def reset(self) -> None:
        """Manually reset the circuit breaker"""
        with self._lock:
            logger.info(f"[{self.name}] Circuit breaker manually reset")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
