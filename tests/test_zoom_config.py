"""
Tests for zoom and interaction configuration.
"""

import pytest
from trading_dashboard.layouts.charts_backtesting import create_charts_backtesting_layout


def test_ui_graph_config_zoom_enabled():
    """Test that graph configuration enables zoom and interaction."""
    layout = create_charts_backtesting_layout()
    
    # Layout is a Div, find the dcc.Graph component
    # Navigate: Div -> Row -> Col -> Card -> CardBody -> Graph
    # The graph should have id="bt-candlestick-chart"
    
    # Helper to recursively find component by id
    def find_component_by_id(component, target_id):
        if hasattr(component, 'id') and component.id == target_id:
            return component
        if hasattr(component, 'children'):
            children = component.children if not isinstance(component.children, str) else []
            if isinstance(children, list):
                for child in children:
                    result = find_component_by_id(child, target_id)
                    if result:
                        return result
            else:
                return find_component_by_id(children, target_id)
        return None
    
    graph = find_component_by_id(layout, 'bt-candlestick-chart')
    
    assert graph is not None, "Graph component not found"
    assert hasattr(graph, 'config'), "Graph should have config attribute"
    
    # Verify zoom configuration
    config = graph.config
    assert config['scrollZoom'] is True, "scrollZoom should be enabled"
    assert config['displaylogo'] is False, "Plotly logo should be hidden"
    assert config['displayModeBar'] is True, "Mode bar should be visible"


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
