from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def build_trade_chart(trade_row: pd.Series, exec_bars: pd.DataFrame | None) -> go.Figure:
    fig = go.Figure()
    if exec_bars is None or exec_bars.empty:
        fig.update_layout(title="No bars available for proof", template="plotly_dark")
        return fig

    df = exec_bars.copy()
    if "timestamp" in df.columns:
        df.index = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.sort_index()

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="Price",
            showlegend=False,
        )
    )

    entry_ts = pd.to_datetime(trade_row.get("entry_ts"), utc=True, errors="coerce")
    exit_ts = pd.to_datetime(trade_row.get("exit_ts"), utc=True, errors="coerce")
    entry_price = trade_row.get("entry_price")
    exit_price = trade_row.get("exit_price")

    if entry_ts is not None and not pd.isna(entry_ts):
        fig.add_trace(
            go.Scatter(
                x=[entry_ts], y=[entry_price], mode="markers",
                marker=dict(color="blue", size=9, symbol="triangle-up"),
                name="Entry",
            )
        )
    if exit_ts is not None and not pd.isna(exit_ts):
        fig.add_trace(
            go.Scatter(
                x=[exit_ts], y=[exit_price], mode="markers",
                marker=dict(color="red", size=9, symbol="triangle-down"),
                name="Exit",
            )
        )

    if "stop_loss" in trade_row.index and not pd.isna(trade_row.get("stop_loss")):
        fig.add_hline(y=float(trade_row.get("stop_loss")), line=dict(color="red", dash="dot"), name="SL")
    if "take_profit" in trade_row.index and not pd.isna(trade_row.get("take_profit")):
        fig.add_hline(y=float(trade_row.get("take_profit")), line=dict(color="green", dash="dot"), name="TP")

    # Calculate appropriate y-axis range
    y_min = df["low"].min()
    y_max = df["high"].max()
    y_padding = (y_max - y_min) * 0.1  # 10% padding

    fig.update_layout(
        template="plotly_dark",
        margin=dict(l=60, r=40, t=40, b=60),
        autosize=True,  # Enable responsive sizing
        height=600,  # Set default height, but allow width to be responsive
        uirevision="constant",  # CRITICAL: Prevents resize loops by maintaining UI state
        xaxis=dict(
            fixedrange=False,  # Enable zoom/pan on x-axis
            rangeslider=dict(visible=False),
            autorange=True,
            rangebreaks=[
                dict(bounds=["sat", "mon"]),  # Hide weekends
                dict(bounds=[16, 9.5], pattern="hour"),  # Hide non-RTH (4pm-9:30am ET)
            ],
        ),
        yaxis=dict(
            fixedrange=False,  # Enable zoom/pan on y-axis too
            range=[y_min - y_padding, y_max + y_padding],
            autorange=False,
        ),
        dragmode="zoom",
        hovermode="closest",
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(0,0,0,0.5)",
        ),
        transition={"duration": 0},
        updatemenus=[],
    )

    return fig
