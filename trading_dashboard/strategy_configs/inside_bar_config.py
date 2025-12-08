"""
InsideBar Strategy Configuration Plugin

Provides version management UI for InsideBar strategy.
"""
import re
from typing import List, Callable, Dict, Any
from dash import html, dcc, Input, Output, State

from . import StrategyConfigPlugin


class InsideBarConfigPlugin(StrategyConfigPlugin):
    """InsideBar strategy configuration with version management."""
    
    @property
    def strategy_id(self) -> str:
        return "insidebar_intraday"
    
    @property
    def display_name(self) -> str:
        return "Inside Bar"
    
    def render_config_ui(self) -> List:
        """Render version management UI for InsideBar."""
        return [
            # Version selection dropdown
            html.Label(
                "Version",
                style={"fontWeight": "bold", "marginTop": "12px"}
            ),
            dcc.Dropdown(
                id="insidebar-version-dropdown",
                options=[],  # Will be populated by callback
                placeholder="Loading versions...",
                clearable=False,
                style={"color": "#000", "marginBottom": "8px"},
            ),
            
            # Configuration Parameters Section (collapsible)
            html.Details([
                html.Summary(
                    "⚙️ Configuration Parameters",
                    style={
                        "fontWeight": "bold",
                        "marginTop": "12px",
                        "cursor": "pointer",
                        "fontSize": "1.0em"
                    }
                ),
                html.Div([
                    # Version Control subsection
                    html.H6(
                        "📦 Version Control",
                        style={"marginTop": "12px", "marginBottom": "8px", "fontSize": "0.9em"}
                    ),
                    html.Label(
                        "New version (optional)",
                        style={"fontWeight": "normal", "fontSize": "0.9em"}
                    ),
                    dcc.Input(
                        id="insidebar-new-version",
                        type="text",
                        placeholder="e.g., v1.01 or v2.00",
                        style={"width": "100%", "marginBottom": "4px"},
                    ),
                    html.Div(
                        id="insidebar-version-hint",
                        children="Pattern: v#.## (e.g., v1.01, v2.00)",
                        style={"fontSize": "0.75em", "color": "#888", "marginBottom": "8px"}
                    ),
                ], style={"marginLeft": "15px", "marginTop": "8px"}),
            ], open=True),  # Expanded by default
        ]
    
    def get_callbacks(self) -> List[Callable]:
        """Register version management callbacks."""
        return [
            self._register_version_loader,
            self._register_version_validator,
        ]
    
    def _register_version_loader(self, app):
        """Callback to load available versions from registry."""
        @app.callback(
            Output("insidebar-version-dropdown", "options"),
            Output("insidebar-version-dropdown", "value"),
            Input("backtests-new-strategy", "value")
        )
        def load_insidebar_versions(strategy):
            """Load versions when InsideBar is selected."""
            if strategy != self.strategy_id:
                return [], None
            
            try:
                from trading_dashboard.utils.version_loader import get_strategy_versions
                versions = get_strategy_versions(strategy)
                if versions:
                    # Simplify labels to just version number
                    simplified = [{"label": f"v{v['value']}", "value": v["value"]} for v in versions]
                    # Return options and default to first (latest)
                    return simplified, simplified[0]["value"]
            except Exception as e:
                print(f"Error loading versions: {e}")
            
            return [], None
    
    def _register_version_validator(self, app):
        """Callback to validate new version input pattern."""
        @app.callback(
            Output("insidebar-version-hint", "children"),
            Output("insidebar-version-hint", "style"),
            Input("insidebar-new-version", "value")
        )
        def validate_version_pattern(new_version):
            """Validate version format in real-time."""
            base_style = {"fontSize": "0.75em", "marginBottom": "8px"}
            
            if not new_version or not new_version.strip():
                return (
                    "Pattern: v#.## (e.g., v1.01, v2.00)",
                    {**base_style, "color": "#888"}
                )
            
            # Pattern: v + number + dot + two-digit number
            pattern = r'^v\d+\.\d{2}$'
            if re.match(pattern, new_version.strip()):
                return (
                    "✓ Valid version format",
                    {**base_style, "color": "green"}
                )
            else:
                return (
                    "❌ Invalid format. Use: v#.## (e.g., v1.01, v2.00)",
                    {**base_style, "color": "red"}
                )
    
    def extract_config_from_inputs(
        self,
        selected_version: str = None,
        new_version: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Extract version configuration from UI inputs."""
        # Use new version if provided and valid, otherwise selected version
        version_to_use = None
        is_new = False
        
        if new_version and new_version.strip():
            # Validate pattern
            if re.match(r'^v\d+\.\d{2}$', new_version.strip()):
                version_to_use = new_version.strip()
                is_new = True
        
        if not version_to_use:
            version_to_use = selected_version
        
        return {
            "strategy_version": version_to_use,
            "is_new_version": is_new
        }
