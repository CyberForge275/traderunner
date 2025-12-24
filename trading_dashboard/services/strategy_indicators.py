"""
Strategy indicator wrapper - compute indicators defined in trading strategies.

This service provides a clean interface to compute technical indicators
used by trading strategies, without coupling the dashboard to strategy internals.
"""
from typing import Dict, List
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def get_available_indicators(strategy_name: str) -> List[str]:
    """
    Get list of indicators available for a strategy.

    Args:
        strategy_name: Name of strategy (e.g., "inside_bar", "ma_crossover")

    Returns:
        List of indicator names (e.g., ["ema_20", "sma_50", "rsi_14"])

    Example:
        >>> indicators = get_available_indicators("ma_crossover")
        >>> print(indicators)
        ['ema_20', 'sma_50', 'rsi_14']
    """
    # Map strategy names to their technical indicators
    # This can be extended or made dynamic by inspecting strategy modules
    strategy_indicators = {
        "inside_bar": [
            "ema_20",
            "sma_50",
            "rsi_14",
        ],
        "ma_crossover": [
            "ema_12",
            "ema_26",
            "sma_200",
        ],
        # Add more strategies here as they are developed
    }

    return strategy_indicators.get(strategy_name, [])


def compute_strategy_indicators(
    strategy_name: str,
    ohlcv: pd.DataFrame,
    indicators_to_compute: List[str]
) -> Dict[str, pd.Series]:
    """
    Compute requested indicators for a strategy.

    Args:
        strategy_name: Name of strategy
        ohlcv: OHLCV DataFrame with datetime index
        indicators_to_compute: List of indicator names to compute

    Returns:
        Dict of {indicator_name: pd.Series} aligned to ohlcv index

    Example:
        >>> ohlcv = pd.DataFrame(...)  # with close column
        >>> indicators = compute_strategy_indicators(
        ...     "inside_bar",
        ...     ohlcv,
        ...     ["ema_20", "rsi_14"]
        ... )
        >>> indicators.keys()
        dict_keys(['ema_20', 'rsi_14'])
    """
    if ohlcv.empty:
        logger.warning("Empty OHLCV data, returning empty indicators")
        return {}

    result = {}

    for indicator_name in indicators_to_compute:
        try:
            # Parse indicator name (e.g., "ema_20" -> type="ema", period=20)
            if "_" in indicator_name:
                ind_type, period_str = indicator_name.rsplit("_", 1)
                try:
                    period = int(period_str)
                except ValueError:
                    logger.warning(f"Invalid period in '{indicator_name}', using 20")
                    period = 20
            else:
                ind_type = indicator_name
                period = 20

            # Compute based on type
            if ind_type == "ema":
                result[indicator_name] = ohlcv["close"].ewm(span=period, adjust=False).mean()

            elif ind_type == "sma":
                result[indicator_name] = ohlcv["close"].rolling(period).mean()

            elif ind_type == "rsi":
                result[indicator_name] = _compute_rsi(ohlcv["close"], period)

            else:
                logger.warning(f"Unknown indicator type '{ind_type}', skipping")
                continue

            logger.debug(f"Computed {indicator_name}: {result[indicator_name].notna().sum()} valid values")

        except Exception as e:
            logger.error(f"Error computing {indicator_name}: {e}")
            continue

    return result


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Compute RSI (Relative Strength Index) indicator.

    Args:
        series: Price series (typically close prices)
        period: RSI period (default: 14)

    Returns:
        RSI values between 0 and 100
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()

    # Avoid division by zero
    rs = gain / loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))

    return rsi
