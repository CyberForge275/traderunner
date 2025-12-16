"""
Tests for zoom and interaction configuration.
"""

import pytest
from trading_dashboard.layouts.charts_backtesting import create_charts_backtesting_layout


def test_ui_graph_config_zoom_enabled():
    """Test that graph configuration enables zoom and interaction."""
    layout = create_charts_backtesting_layout()
    
    # Convert layout to string to check for config presence
    layout_str = str(layout)
    
    # Verify zoom configuration is in layout
    assert 'scrollZoom' in layout_str, "scrollZoom should be in config"
    assert 'displaylogo' in layout_str, "displaylogo should be in config"
    assert 'displayModeBar' in layout_str, "displayModeBar should be in config"
    
    # Verify the chart ID exists
    assert 'bt-candlestick-chart' in layout_str, "Chart ID should be in layout"


def test_ui_graph_exists_in_layout():
    """Test that graph component exists in layout."""
    layout = create_charts_backtesting_layout()
    
    # Convert to string to check for component presence
    layout_str = str(layout)
    
    assert 'bt-candlestick-chart' in layout_str, "Chart ID should be in layout"


def test_window_dropdown_exists():
    """Test that window dropdown for D1 exists."""
    layout = create_charts_backtesting_layout()
    layout_str = str(layout)
    
    assert 'bt-window-selector' in layout_str, "Window dropdown should exist"
    assert '12M' in layout_str, "Default 12M window should be in layout"
