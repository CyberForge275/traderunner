"""
Theme definitions for consistent chart styling across the dashboard.

Provides predefined color schemes and layout defaults for dark and light modes.
"""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ChartTheme:
    """
    Immutable color and style theme for charts.
    
    Attributes:
        bg_color: Main background color
        paper_color: Paper/card background color
        grid_color: Grid line color (use rgba for transparency)
        axis_color: Axis line and tick color
        candle_up_color: Bullish candle fill color
        candle_down_color: Bearish candle fill color
        candle_up_line: Bullish candle border color
        candle_down_line: Bearish candle border color
        volume_color: Volume bar color (use rgba for transparency)
        font_color: Text color
        font_family: Font stack
    """
    
    # Background colors
    bg_color: str
    paper_color: str
    
    # Grid and axes
    grid_color: str
    axis_color: str
    
    # Candles
    candle_up_color: str
    candle_down_color: str
    candle_up_line: str
    candle_down_line: str
    
    # Volume
    volume_color: str
    
    # Text
    font_color: str
    font_family: str = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"


# Predefined theme: Dark mode (default)
DARK_THEME = ChartTheme(
    bg_color="#1a1a1a",
    paper_color="#2b2b2b",
    grid_color="rgba(255, 255, 255, 0.08)",
    axis_color="#888888",
    candle_up_color="#00d26a",
    candle_down_color="#ff4d4d",
    candle_up_line="#00d26a",
    candle_down_line="#ff4d4d",
    volume_color="rgba(100, 100, 255, 0.25)",
    font_color="#e0e0e0",
)


# Predefined theme: Light mode
LIGHT_THEME = ChartTheme(
    bg_color="#ffffff",
    paper_color="#f8f9fa",
    grid_color="rgba(0, 0, 0, 0.08)",
    axis_color="#666666",
    candle_up_color="#26a69a",
    candle_down_color="#ef5350",
    candle_up_line="#26a69a",
    candle_down_line="#ef5350",
    volume_color="rgba(100, 100, 255, 0.15)",
    font_color="#333333",
)


def get_default_theme(mode: Literal["light", "dark"] = "dark") -> ChartTheme:
    """
    Get the default theme for the specified mode.
    
    Args:
        mode: Theme mode ("light" or "dark")
    
    Returns:
        ChartTheme instance
    
    Raises:
        ValueError: If mode is not "light" or "dark"
    
    Examples:
        >>> theme = get_default_theme("dark")
        >>> theme.bg_color
        '#1a1a1a'
    """
    if mode == "dark":
        return DARK_THEME
    elif mode == "light":
        return LIGHT_THEME
    else:
        raise ValueError(f"Invalid theme mode: {mode}. Must be 'light' or 'dark'")
