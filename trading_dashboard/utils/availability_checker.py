"""
Data availability checker for backtesting charts.

Uses BacktestingDataCatalog to get availability info,
formats it for UI display.
"""

from typing import Dict, Any
import logging

from trading_dashboard.catalog.data_catalog import BacktestingDataCatalog

logger = logging.getLogger(__name__)


def get_availability(symbol: str) -> Dict[str, Any]:
    """
    Get data availability for all timeframes for a symbol.
    
    Args:
        symbol: Stock symbol
    
    Returns:
        Dict with availability info per timeframe:
        {
            'D1': {
                'available': True,
                'derivable': False,
                'rows': 695,
                'first_date': '2023-03-01',
                'last_date': '2025-12-12',
                'warnings': []
            },
            'M5': {...},
            ...
        }
    """
    logger.debug(f"Checking availability for {symbol}")
    
    catalog = BacktestingDataCatalog()
    info = catalog.get_symbol_info(symbol)
    
    # Format for UI display
    result = {}
    for tf, tf_info in info.items():
        if tf_info.exists or tf_info.derivable:
            result[tf] = {
                'available': True,
                'derivable': tf_info.derivable,
                'rows': tf_info.rows,
                'first_date': tf_info.first_date.strftime('%Y-%m-%d') if tf_info.first_date else None,
                'last_date': tf_info.last_date.strftime('%Y-%m-%d') if tf_info.last_date else None,
                'warnings': tf_info.warnings or []
            }
        else:
            result[tf] = {
                'available': False,
                'derivable': False,
                'rows': 0,
                'first_date': None,
                'last_date': None,
                'warnings': []
            }
    
    logger.debug(f"Availability for {symbol}: {len([k for k, v in result.items() if v['available']])} timeframes available")
    
    return result
