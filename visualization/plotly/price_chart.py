"""
Price chart builder with OHLCV candlesticks, volume, and indicators.

This module is the core chart builder for the trading dashboard.
It takes domain data (DataFrames) and configuration, and produces
Plotly figures with no knowledge of the dashboard framework (Dash).
"""
import logging
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import PriceChartConfig, SessionMode
from .theme import get_default_theme, ChartTheme
from .logging_utils import log_chart_build, log_data_preparation, is_debug_mode

logger = logging.getLogger(__name__)


def _filter_session(df: pd.DataFrame, mode: SessionMode) -> pd.DataFrame:
    """
    Filter DataFrame by trading session mode.

    CRITICAL: Session filtering ALWAYS uses NY time (market hours),
    regardless of what timezone the data is displayed in.

    Args:
        df: OHLCV DataFrame with datetime index (timezone-aware)
        mode: Session filtering mode (all/rth/premarket_rth/all_extended)

    Returns:
        Filtered DataFrame

    Raises:
        None (warns if index is not DatetimeIndex)
    """
    with log_data_preparation(f"Filtering session mode: {mode}"):
        if mode == "all":
            # No filtering
            return df

        if df.empty:
            logger.warning("⚠️  Empty DataFrame, skipping session filter")
            return df

        if not isinstance(df.index, pd.DatetimeIndex):
            logger.warning(
                f"⚠️  Index is not DatetimeIndex (type={type(df.index).__name__}), "
                "cannot filter sessions. Returning unfiltered data."
            )
            return df

        # CRITICAL FIX: Convert to NY time for session filtering
        # Market hours are defined in ET/NY timezone, so we must filter in that timezone
        import pytz
        ny_tz = pytz.timezone('America/New_York')

        # Convert index to NY time temporarily for filtering
        df_ny = df.copy()
        if df_ny.index.tz is None:
            logger.warning("⚠️  Index has no timezone, assuming UTC")
            df_ny.index = df_ny.index.tz_localize('UTC')

        df_ny.index = df_ny.index.tz_convert(ny_tz)

        hour = df_ny.index.hour
        minute = df_ny.index.minute if hasattr(df_ny.index, 'minute') else None

        if mode == "rth":  # Regular Trading Hours (9:30-16:00 ET)
            if minute is not None:
                # More precise: 9:30-16:00
                mask = (
                    ((hour == 9) & (minute >= 30)) |
                    ((hour >= 10) & (hour < 16))
                )
            else:
                # Less precise: 9:00-16:00 (for hourly+ data)
                mask = (hour >= 9) & (hour < 16)

        elif mode == "premarket_rth":  # Pre-market + RTH (4:00-16:00 ET)
            mask = (hour >= 4) & (hour < 16)

        elif mode == "rth_afterhours":  # RTH + After-Hours (9:30-20:00 ET)
            if minute is not None:
                # More precise: 9:30-20:00
                mask = (
                    ((hour == 9) & (minute >= 30)) |
                    ((hour >= 10) & (hour < 20))
                )
            else:
                # Less precise: 9:00-20:00 (for hourly+ data)
                mask = (hour >= 9) & (hour < 20)

        elif mode == "all_extended":  # All extended hours (4:00-20:00 ET)
            mask = (hour >= 4) & (hour < 20)

        else:
            # Fallback: return all
            logger.warning(f"⚠️  Unknown session mode '{mode}', returning all data")
            return df

        # Apply mask to ORIGINAL dataframe (preserves original timezone)
        filtered = df[mask]

        if is_debug_mode():
            logger.debug(
                f"  → Rows before: {len(df)}, after: {len(filtered)} "
                f"({100 * len(filtered) / len(df):.1f}% kept)"
            )
            logger.debug(f"  → Filtering done in NY time, data remains in {df.index.tz}")

        return filtered



def _add_candlestick_trace(
    fig: go.Figure,
    df: pd.DataFrame,
    theme: ChartTheme,
    row: int = 1,
) -> None:
    """
    Add candlestick trace to figure.

    Args:
        fig: Plotly figure to add trace to
        df: OHLCV DataFrame
        theme: Chart theme for colors
        row: Subplot row number
    """
    with log_data_preparation("Adding candlestick trace"):
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="Price",
                increasing_line_color=theme.candle_up_line,
                decreasing_line_color=theme.candle_down_line,
                increasing_fillcolor=theme.candle_up_color,
                decreasing_fillcolor=theme.candle_down_color,
                showlegend=False,  # Candles don't need legend
            ),
            row=row,
            col=1,
        )


def _add_volume_trace(
    fig: go.Figure,
    df: pd.DataFrame,
    theme: ChartTheme,
    row: int = 2,
) -> None:
    """
    Add volume bar trace to figure.

    Volume bars are colored green (up) or red (down) based on price direction.

    Args:
        fig: Plotly figure to add trace to
        df: OHLCV DataFrame
        theme: Chart theme for colors
        row: Subplot row number
    """
    with log_data_preparation("Adding volume trace"):
        # Color volume bars based on price direction
        colors = [
            theme.candle_up_color if df["close"].iloc[i] >= df["open"].iloc[i]
            else theme.candle_down_color
            for i in range(len(df))
        ]

        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["volume"],
                name="Volume",
                marker_color=colors,
                opacity=0.4,
                showlegend=False,
            ),
            row=row,
            col=1,
        )


def _add_indicator_traces(
    fig: go.Figure,
    indicators: dict[str, pd.Series],
    row: int = 1,
) -> None:
    """
    Add indicator traces (e.g., moving averages, RSI).

    Args:
        fig: Plotly figure to add traces to
        indicators: Dict of {name: Series} aligned to main df index
        row: Subplot row number
    """
    if not indicators:
        return

    with log_data_preparation(f"Adding {len(indicators)} indicator(s)"):
        # Default color palette for common indicators
        color_map = {
            "ma_20": "#ffa500",      # Orange
            "ma_50": "#00bfff",      # Deep sky blue
            "ma_200": "#ff69b4",     # Hot pink
            "ema_12": "#32cd32",     # Lime green
            "ema_26": "#ff8c00",     # Dark orange
            "rsi": "#9370db",        # Medium purple
            "macd": "#00ced1",       # Dark turquoise
            "signal": "#ff1493",     # Deep pink
        }

        for name, series in indicators.items():
            if is_debug_mode():
                non_null = series.notna().sum()
                total = len(series)
                logger.debug(
                    f"  → Indicator '{name}': {non_null}/{total} non-null values"
                )

            # Determine color
            color = color_map.get(name, "#888888")

            # Display name (prettify)
            display_name = name.replace("_", " ").upper()

            fig.add_trace(
                go.Scatter(
                    x=series.index,
                    y=series.values,
                    name=display_name,
                    line=dict(color=color, width=1.5),
                    mode="lines",
                ),
                row=row,
                col=1,
            )


@log_chart_build
def build_price_chart(
    ohlcv: pd.DataFrame,
    indicators: dict[str, pd.Series],
    config: PriceChartConfig,
) -> go.Figure:
    """
    Build interactive price chart with candlesticks, volume, and indicators.

    This is the main chart builder for OHLCV price data. It creates a
    multi-subplot figure with candlesticks and optional volume subplot.

    Args:
        ohlcv: DataFrame with columns [open, high, low, close, volume]
              and DatetimeIndex. Index should be timezone-aware if possible.
        indicators: Dict of indicator name -> pd.Series (aligned to ohlcv index).
                   Example: {"ma_20": df.close.rolling(20).mean()}
        config: Chart configuration (PriceChartConfig instance)

    Returns:
        Plotly Figure object ready to render in Dash (dcc.Graph)

    Raises:
        ValueError: If required columns are missing or data is invalid

    Examples:
        >>> config = PriceChartConfig(show_volume=True, session_mode="rth")
        >>> indicators = {"ma_20": df["close"].rolling(20).mean()}
        >>> fig = build_price_chart(df, indicators, config)
        >>> # In Dash callback:
        >>> return fig
    """
    # Input validation
    required_cols = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required_cols if c not in ohlcv.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in OHLCV DataFrame: {missing}. "
            f"Expected columns: {required_cols}"
        )

    if ohlcv.empty:
        logger.warning("⚠️  Empty DataFrame provided, returning blank chart")
        return go.Figure().update_layout(
            title="No data available",
            template="plotly_dark" if config.theme_mode == "dark" else "plotly_white",
        )

    if is_debug_mode():
        logger.debug(
            f"Input OHLCV: {len(ohlcv)} rows, "
            f"date range: {ohlcv.index[0]} to {ohlcv.index[-1]}"
        )

    # Get theme
    theme = get_default_theme(config.theme_mode)

    # Filter by session mode
    df = _filter_session(ohlcv, config.session_mode)

    if df.empty:
        logger.warning(
            f"⚠️  DataFrame empty after session filter (mode={config.session_mode})"
        )
        return go.Figure().update_layout(
            title=f"No data for session mode: {config.session_mode}",
            template="plotly_dark" if config.theme_mode == "dark" else "plotly_white",
        )

    # Create subplots
    rows = 2 if config.show_volume else 1
    row_heights = [0.7, 0.3] if config.show_volume else [1.0]

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=None,  # We'll use main title
    )

    # Add traces
    _add_candlestick_trace(fig, df, theme, row=1)
    _add_indicator_traces(fig, indicators, row=1)

    if config.show_volume:
        _add_volume_trace(fig, df, theme, row=2)

    # Layout configuration
    title_text = config.title or "Price Chart"

    fig.update_layout(
        title=dict(
            text=title_text,
            font=dict(size=16, color=theme.font_color),
        ),
        xaxis_rangeslider_visible=config.show_rangeslider,
        height=config.height,
        template="plotly_dark" if config.theme_mode == "dark" else "plotly_white",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10),
        ),
        hovermode="x unified",
        plot_bgcolor=theme.bg_color,
        paper_bgcolor=theme.paper_color,
        font=dict(color=theme.font_color, family=theme.font_family),
        margin=dict(l=60, r=30, t=50, b=40),
    )

    # Grid configuration
    if config.show_grid:
        fig.update_xaxes(showgrid=True, gridcolor=theme.grid_color)
        fig.update_yaxes(showgrid=True, gridcolor=theme.grid_color)
    else:
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=False)

    # Axis styling
    fig.update_xaxes(
        showline=True,
        linecolor=theme.axis_color,
        linewidth=1,
    )
    fig.update_yaxes(
        showline=True,
        linecolor=theme.axis_color,
        linewidth=1,
    )

    # Volume subplot specific styling
    if config.show_volume:
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig
