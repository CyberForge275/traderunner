"""
Type-safe configuration models for Plotly charts.

All chart configurations use frozen dataclasses for immutability and type safety.
"""
from dataclasses import dataclass, field
from typing import Literal, Optional

# Type aliases for better readability
SessionMode = Literal["all", "rth", "premarket_rth", "rth_afterhours", "all_extended"]
ThemeMode = Literal["light", "dark"]


@dataclass(frozen=True)
class PriceChartConfig:
    """
    Configuration for OHLCV price charts with indicators.

    Attributes:
        show_volume: Display volume subplot
        show_grid: Display grid lines
        show_rangeslider: Display range slider below chart
        session_mode: Trading session filtering mode
        indicator_configs: Dict of indicator configs {name: params}
        theme_mode: Light or dark theme
        title: Chart title (None for auto-generated)
        height: Chart height in pixels
        show_patterns: Overlay pattern markers (e.g., InsideBar)
        pattern_data: Optional pattern data to overlay
    """

    # Display options
    show_volume: bool = True
    show_grid: bool = True
    show_rangeslider: bool = False

    # Session filtering
    session_mode: SessionMode = "rth"

    # Indicators (empty dict = no indicators)
    # Example: {"ma_20": {"period": 20, "color": "blue"}}
    indicator_configs: dict[str, dict] = field(default_factory=dict)

    # Styling
    theme_mode: ThemeMode = "dark"
    title: Optional[str] = None
    height: int = 600

    # Pattern overlays
    show_patterns: bool = False
    pattern_data: Optional[dict] = None

    def __post_init__(self):
        """Validate configuration values."""
        if self.height < 100:
            raise ValueError(f"Chart height must be >= 100px, got {self.height}")

        if self.height > 5000:
            raise ValueError(f"Chart height must be <= 5000px, got {self.height}")

        # Validate session mode
        valid_sessions: tuple[SessionMode, ...] = ("all", "rth", "premarket_rth", "rth_afterhours", "all_extended")
        if self.session_mode not in valid_sessions:
            raise ValueError(
                f"Invalid session_mode '{self.session_mode}', "
                f"must be one of {valid_sessions}"
            )


@dataclass(frozen=True)
class VolumeProfileConfig:
    """
    Configuration for volume profile charts.

    Volume profile shows volume distribution across price levels,
    useful for identifying support/resistance zones.

    Attributes:
        bins: Number of price bins for volume aggregation
        show_poc: Show Point of Control (highest volume price)
        show_value_area: Show value area (70% volume concentration)
        theme_mode: Light or dark theme
    """

    bins: int = 50
    show_poc: bool = True
    show_value_area: bool = True
    theme_mode: ThemeMode = "dark"

    def __post_init__(self):
        """Validate configuration values."""
        if self.bins < 10:
            raise ValueError(f"Volume profile bins must be >= 10, got {self.bins}")

        if self.bins > 200:
            raise ValueError(f"Volume profile bins must be <= 200, got {self.bins}")
