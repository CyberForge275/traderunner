"""
Data Availability Service

Business logic for checking data availability across timeframes.
Follows service layer pattern - keeps callbacks thin.
"""

import logging
from typing import Dict, Any
from dataclasses import dataclass

from trading_dashboard.catalog.data_catalog import BacktestingDataCatalog
from trading_dashboard.utils.availability_cache import get_cached, set_cached

logger = logging.getLogger(__name__)


@dataclass
class AvailabilityResult:
    """
    Result DTO for data availability check.
    
    Attributes:
        symbol: Stock symbol
        timeframes: Dict of timeframe -> availability info
        cached: Whether result came from cache
    """
    symbol: str
    timeframes: Dict[str, Dict[str, Any]]
    cached: bool = False


def get_availability(symbol: str, force_refresh: bool = False) -> AvailabilityResult:
    """
    Get data availability for all timeframes for a symbol.
    
    Service layer method - coordinates catalog + cache.
    
    Args:
        symbol: Stock symbol
        force_refresh: If True, bypass cache
    
    Returns:
        AvailabilityResult with availability info per timeframe
    """
    logger.debug(f"Getting availability for {symbol} (force_refresh={force_refresh})")
    
    # Check cache first
    if not force_refresh:
        cached = get_cached(symbol)
        if cached is not None:
            logger.debug(f"Cache hit for {symbol}")
            return AvailabilityResult(
                symbol=symbol,
                timeframes=cached,
                cached=True
            )
    
    # Fetch from catalog
    logger.debug(f"Fetching availability from catalog for {symbol}")
    catalog = BacktestingDataCatalog()
    info = catalog.get_symbol_info(symbol)
    
    # Format for UI
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
    
    # Cache result
    set_cached(symbol, result)
    
    logger.debug(f"Availability for {symbol}: {len([k for k, v in result.items() if v['available']])} timeframes available")
    
    return AvailabilityResult(
        symbol=symbol,
        timeframes=result,
        cached=False
    )


def format_availability_for_ui(result: AvailabilityResult) -> list:
    """
    Format availability result for Dash UI display.
    
    Separates business logic from presentation logic.
    Returns list of html.Div components.
    
    Args:
        result: AvailabilityResult from get_availability()
    
    Returns:
        List of Dash html components
    """
    from dash import html
    from datetime import datetime
    
    children = []
    
    for tf in ['D1', 'M1', 'M5', 'M15', 'H1']:
        info = result.timeframes.get(tf, {})
        
        if info.get('available'):
            # Available or derivable
            icon = "🔄" if info.get('derivable') else "✅"
            
            # Format date range
            if info.get('first_date') and info.get('last_date'):
                date_range = f"{info['first_date']} → {info['last_date']}"
            else:
                date_range = "unknown"
            
            # Format row count
            rows = info.get('rows', 0)
            if rows > 0:
                unit = "days" if tf == "D1" else "bars"
                rows_str = f"({rows:,} {unit})"
            else:
                rows_str = ""
            
            # Combine
            text = f"{tf}: {icon} {date_range} {rows_str}"
            
            # Add warnings highlight
            style = {"marginBottom": "3px", "lineHeight": "1.2"}
            if info.get('warnings'):
                style["color"] = "orange"
            
            children.append(html.Div(text, style=style))
            
            # Show warnings inline if present
            if info.get('warnings'):
                warnings_text = "⚠️ " + ", ".join(info['warnings'])
                children.append(html.Div(
                    warnings_text,
                    style={"fontSize": "0.65rem", "color": "orange", "marginLeft": "15px", "marginBottom": "4px"}
                ))
        else:
            # Not available
            children.append(html.Div(
                f"{tf}: ❌ Not available",
                className="text-muted",
                style={"marginBottom": "3px", "lineHeight": "1.2"}
            ))
    
    # Add timestamp
    cache_indicator = " (cached)" if result.cached else ""
    children.append(html.Div(
        f"Updated: {datetime.now().strftime('%H:%M:%S')}{cache_indicator}",
        className="text-muted",
        style={"marginTop": "8px", "fontSize": "0.6rem", "textAlign": "center"}
    ))
    
    return children
