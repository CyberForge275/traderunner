"""
Data freshness callback - shows M1/M5 data age with colored status indicators.
"""
from dash import Input, Output
import logging

logger = logging.getLogger(__name__)


def register_freshness_callback(app):
    """Register callback to update data freshness indicators."""

    @app.callback(
        [
            Output("m1-freshness-text", "children"),
            Output("m1-freshness-badge", "children"),
            Output("m1-freshness-badge", "style"),
            Output("m5-freshness-text", "children"),
            Output("m5-freshness-badge", "children"),
            Output("m5-freshness-badge", "style"),
        ],
        [
            Input("chart-symbol-selector", "value"),
            Input("chart-refresh-btn", "n_clicks"),
        ]
    )
    def update_data_freshness(symbol, refresh_clicks):
        """Update freshness indicators for M1 and M5 data.

        Returns:
            Tuple of (m1_text, m1_badge, m1_style, m5_text, m5_badge, m5_style)
        """
        from datetime import datetime, timezone
        import pandas as pd
        from ..repositories.candles import get_candle_data
        from core.settings.intraday_paths import get_intraday_parquet_path

        def check_freshness(timeframe):
            """Check freshness of data for a timeframe.

            Returns:
                (text, badge, style) tuple
            """
            try:
                # Get file path
                file_path = get_intraday_parquet_path(symbol, timeframe)

                if not file_path.exists():
                    return (
                        "No file",
                        "🔴",
                        {"fontSize": "1rem", "marginLeft": "5px"}
                    )

                # Load data to get last timestamp
                df = pd.read_parquet(file_path)

                if df.empty:
                    return (
                        "Empty file",
                        "🔴",
                        {"fontSize": "1rem", "marginLeft": "5px"}
                    )

                # Get last timestamp
                last_ts = df.index[-1]

                # Calculate age
                now = pd.Timestamp.now(tz=last_ts.tz if hasattr(last_ts, 'tz') and last_ts.tz else None)
                age = now - last_ts
                age_minutes = age.total_seconds() / 60

                # Format timestamp
                ts_str = last_ts.strftime("%H:%M")

                # Determine status
                if age_minutes < 5:
                    badge = "🟢"
                    color = "#00d26a"
                elif age_minutes < 30:
                    badge = "🟡"
                    color = "#ffa500"
                else:
                    badge = "🔴"
                    color = "#ff4444"

                # Format age
                if age_minutes < 60:
                    age_str = f"{int(age_minutes)}m ago"
                elif age_minutes < 1440:
                    age_str = f"{int(age_minutes/60)}h ago"
                else:
                    age_str = f"{int(age_minutes/1440)}d ago"

                text = f"{ts_str} ({age_str})"
                style = {"fontSize": "1rem", "marginLeft": "5px"}

                return (text, badge, style)

            except Exception as e:
                logger.error(f"Error checking freshness for {symbol} {timeframe}: {e}")
                return (
                    "Error",
                    "⚠️",
                    {"fontSize": "1rem", "marginLeft": "5px"}
                )

        # Check M1 and M5
        m1_text, m1_badge, m1_style = check_freshness("M1")
        m5_text, m5_badge, m5_style = check_freshness("M5")

        return (m1_text, m1_badge, m1_style, m5_text, m5_badge, m5_style)
