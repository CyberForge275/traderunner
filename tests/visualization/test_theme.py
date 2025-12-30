"""
Unit tests for visualization theme system.
"""
import pytest
from visualization.plotly.theme import (
    ChartTheme,
    DARK_THEME,
    LIGHT_THEME,
    get_default_theme,
)


class TestChartTheme:
    """Tests for ChartTheme dataclass."""

    def test_theme_immutability(self):
        """Test that themes are immutable."""
        theme = DARK_THEME

        with pytest.raises(Exception):  # FrozenInstanceError
            theme.bg_color = "#000000"  # type: ignore

    def test_dark_theme_colors(self):
        """Test dark theme has expected dark colors."""
        theme = DARK_THEME

        # Background should be dark
        assert theme.bg_color == "#1a1a1a"
        assert theme.paper_color == "#2b2b2b"

        # Font should be light
        assert theme.font_color == "#e0e0e0"

        # Candles
        assert theme.candle_up_color == "#00d26a"
        assert theme.candle_down_color == "#ff4d4d"

    def test_light_theme_colors(self):
        """Test light theme has expected light colors."""
        theme = LIGHT_THEME

        # Background should be light
        assert theme.bg_color == "#ffffff"
        assert theme.paper_color == "#f8f9fa"

        # Font should be dark
        assert theme.font_color == "#333333"

        # Candles
        assert theme.candle_up_color == "#26a69a"
        assert theme.candle_down_color == "#ef5350"

    def test_font_family_default(self):
        """Test default font family."""
        assert "Inter" in DARK_THEME.font_family
        assert "sans-serif" in DARK_THEME.font_family


class TestGetDefaultTheme:
    """Tests for get_default_theme function."""

    def test_get_dark_theme(self):
        """Test getting dark theme."""
        theme = get_default_theme("dark")
        assert theme == DARK_THEME

    def test_get_light_theme(self):
        """Test getting light theme."""
        theme = get_default_theme("light")
        assert theme == LIGHT_THEME

    def test_default_is_dark(self):
        """Test default mode is dark."""
        theme = get_default_theme()
        assert theme == DARK_THEME

    def test_invalid_mode(self):
        """Test invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid theme mode"):
            get_default_theme("invalid")  # type: ignore
