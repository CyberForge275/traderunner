"""
Interactive Candlestick Chart Component
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


def create_candlestick_chart(
    df: pd.DataFrame,
    symbol: str = "AAPL",
    patterns: pd.DataFrame = None,
    entry_price: float = None,
    stop_loss: float = None,
    take_profit: float = None,
    df_live: pd.DataFrame = None
):
    """
    Create an interactive candlestick chart with TradingView-style features.
    
    Args:
        df: DataFrame with columns: timestamp, open, high, low, close, volume
        symbol: Symbol name for title
        patterns: DataFrame with Inside Bar patterns
        entry_price, stop_loss, take_profit: Order levels to display
    """
    if df.empty:
        # Empty chart placeholder with correct symbol
        fig = go.Figure()
        fig.add_annotation(
            text=f"📊 No stock data available for {symbol}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="#8b949e")
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='#0d1117',
            plot_bgcolor='#0d1117',
            title=f"{symbol} - No Data Available",
            font=dict(color='#f0f6fc')
        )
        return fig
    
    # Create subplot with volume
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f"{symbol} - M5", "Volume")
    )
    
    # Main candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df['timestamp'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name="OHLC",
            increasing=dict(line=dict(color='#3fb950'), fillcolor='#3fb950'),
            decreasing=dict(line=dict(color='#f85149'), fillcolor='#f85149')
        ),
        row=1, col=1
    )
    
    # Overlay live data if available
    if df_live is not None and not df_live.empty:
        fig.add_trace(
            go.Candlestick(
                x=df_live['timestamp'],
                open=df_live['open'],
                high=df_live['high'],
                low=df_live['low'],
                close=df_live['close'],
                name="Live Data",
                increasing=dict(line=dict(color='#00ff00', width=2), fillcolor='#00ff00'),
                decreasing=dict(line=dict(color='#ff0000', width=2), fillcolor='#ff0000'),
                opacity=0.8,
                showlegend=True
            ),
            row=1, col=1
        )
    
    # Volume bars
    colors = ['#3fb950' if close >= open else '#f85149' 
              for close, open in zip(df['close'], df['open'])]
    
    fig.add_trace(
        go.Bar(
            x=df['timestamp'],
            y=df['volume'],
            name="Volume",
            marker_color=colors,
            opacity=0.5
        ),
        row=2, col=1
    )
    
    # Add Inside Bar pattern overlays
    if patterns is not None and not patterns.empty:
        for _, pattern in patterns.iterrows():
            # Highlight Inside Bar with yellow rectangle
            # Pattern markers (rectangles)
            pattern_timestamp = pd.to_datetime(pattern.get('detected_at', pattern.get('created_at')))
            
            fig.add_shape(
                type="rect",
                xref="x", yref="y",
                x0=pattern.get('master_start', pattern_timestamp),
                x1=pattern.get('master_end', pattern_timestamp),
                y0=pattern.get('master_low', 0),
                y1=pattern.get('master_high', 0),
                line=dict(color='#d29922', width=2),
                fillcolor='rgba(210, 153, 34, 0.1)',
                row=1, col=1
            )
    
    # Add entry/SL/TP lines
    if entry_price:
        fig.add_hline(
            y=entry_price, line=dict(color='#3fb950', dash='dash', width=2),
            annotation_text=f"Entry: ${entry_price:.2f}",
            row=1, col=1
        )
    
    if stop_loss:
        fig.add_hline(
            y=stop_loss, line=dict(color='#f85149', dash='dash', width=2),
            annotation_text=f"SL: ${stop_loss:.2f}",
            row=1, col=1
        )
    
    if take_profit:
        fig.add_hline(
            y=take_profit, line=dict(color='#58a6ff', dash='dash', width=2),
            annotation_text=f"TP: ${take_profit:.2f}",
            row=1, col=1
        )
    
    # Update layout with dark theme and TradingView-style interactions
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='#0d1117',
        plot_bgcolor='#0d1117',
        font=dict(color='#f0f6fc'),
        hovermode='x unified',
        xaxis=dict(
            rangeslider=dict(visible=False),
            gridcolor='#30363d',
            showgrid=True
        ),
        xaxis2=dict(
            gridcolor='#30363d',
            showgrid=True
        ),
        yaxis=dict(
            gridcolor='#30363d',
            showgrid=True
        ),
        yaxis2=dict(
            gridcolor='#30363d',
            showgrid=True
        ),
        margin=dict(l=50, r=50, t=50, b=50),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig


def get_chart_config():
    """Get Plotly config for interactive features."""
    return {
        'scrollZoom': True,           # Mouse wheel zoom
        'displayModeBar': True,        # Show toolbar
        'displaylogo': False,          # Hide Plotly logo
        'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'eraseshape'],
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'toImageButtonOptions': {
            'format': 'png',
            'filename': 'trading_chart',
            'height': 1080,
            'width': 1920,
            'scale': 1
        }
    }
