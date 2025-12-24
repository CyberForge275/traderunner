Streamlit Dashboard Analysis - Requirements Extraction
Executive Summary
Analysis of the existing TradeRunner Backtest Dashboard running at http://127.0.0.1:8501/ to extract requirements for building a new Plotly Dash dashboard on port 9001.

Current Dashboard Structure (Streamlit)
Visual Components Identified
Current Streamlit Dashboard
Review
Current Streamlit Dashboard

Page Layout
The dashboard consists of the following major sections:

1. Header Section
Title: "TradeRunner Backtest Dashboard"
Branding/Title prominently displayed
2. Configuration Sidebar (Left Panel)
Strategy Selection

Dropdown menu for strategy selection
Options visible:
"Inside Bar" (appears to be selected)
Other strategy options available
Data Configuration

Symbol input field
Default/example: "DAX"
Text input for ticker symbol
Interval dropdown
Options: 1m, 5m, 15m, 30m, 1h, 1d
Currently selected: "5m"
Period dropdown
Options: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max
Currently selected: "6mo"
Action Buttons

"Run Backtest" button (primary action)
Prominent call-to-action button
3. Results Display Area (Main Panel)
Performance Metrics Cards

Total Return: 5.2%
Sharpe Ratio: 1.34
Max Drawdown: -8.5%
Win Rate: 58%
Total Trades: 142
Avg Trade: 0.87%
Visualizations

Equity Curve Chart

Line chart showing portfolio equity over time
X-axis: Time/Date
Y-axis: Portfolio value
Shows cumulative performance
Drawdown Chart

Area/line chart showing drawdown percentage over time
X-axis: Time/Date
Y-axis: Drawdown percentage
Visualizes risk exposure over time
Trade Distribution

Bar chart or histogram
Shows distribution of trade outcomes
Trade Log Table

Tabular display of individual trades
Columns visible:
Date/Time
Symbol
Side (Buy/Sell)
Entry Price
Exit Price
P&L
Return %
4. Layout Characteristics
Responsive design
Clean, modern interface
Sidebar for configuration
Main content area for results
Clear visual hierarchy
Data-focused presentation
Requirements for New Dash Dashboard
Technology Stack
Framework: Plotly Dash 3.x
Backend: Flask
UI Components: dash-bootstrap-components
Data Visualization:
dash_table.DataTable for tabular data
dcc.Graph with plotly.graph_objects for charts
Port: 9001
Name: "Automatic Trading Factory"
Functional Requirements
FR1: Strategy Configuration
Strategy selector (dropdown)
Symbol input (text field with validation)
Timeframe selector (interval dropdown)
Period selector (lookback period dropdown)
Execute button to trigger backtest
FR2: Performance Metrics Display
Key metrics cards displaying:
Total Return (%)
Sharpe Ratio
Maximum Drawdown (%)
Win Rate (%)
Total Trades (count)
Average Trade (%)
Real-time update on backtest completion
FR3: Data Visualization
Equity Curve

Interactive line chart using plotly
Zoom, pan, and hover capabilities
Time series on x-axis, portfolio value on y-axis
Drawdown Chart

Area chart showing drawdown over time
Visual indication of risk periods
Interactive tooltips
Trade Distribution

Histogram or bar chart
Distribution of P&L or returns
Win/loss visualization
FR4: Trade Log
Scrollable, sortable table using dash_table.DataTable
Columns:
Timestamp
Symbol
Side (Buy/Sell)
Entry Price
Exit Price
P&L (absolute)
Return (%)
Export functionality (CSV/Excel)
Filtering and searching capabilities
FR5: Layout & Responsiveness
Two-column layout:
Left sidebar: Configuration panel (30% width)
Main area: Results display (70% width)
Mobile-responsive using Bootstrap grid
Consistent styling using dash-bootstrap-components theme
Non-Functional Requirements
NFR1: Performance
Dashboard should load in < 2 seconds
Backtest execution feedback (progress indicator)
Efficient data handling for large datasets
NFR2: User Experience
Intuitive navigation
Clear visual feedback for user actions
Consistent color scheme and typography
Error handling with user-friendly messages
NFR3: Compatibility
Modern browser support (Chrome, Firefox, Safari, Edge)
Python 3.8+ compatibility
Cross-platform (Linux, Windows, macOS)
NFR4: Extensibility
Modular component structure
Easy to add new strategies
Configurable via external config files
Plugin architecture for future enhancements
Data Flow Architecture
User Input
Dash Frontend
Callback Functions
Backtest Engine
Data Processing
Results
Plotly Charts
DataTable
Metrics Cards
Component Breakdown
Components to Implement
app.py - Main Dash application
layouts/sidebar.py - Configuration sidebar
layouts/main.py - Main results area
components/metrics.py - Metric cards component
components/charts.py - Chart components (equity, drawdown, distribution)
components/trade_table.py - Trade log table
callbacks/backtest.py - Backtest execution callbacks
utils/data_processing.py - Data transformation utilities
config/settings.py - Application configuration
assets/styles.css - Custom CSS styling
Styling Guidelines
Color Scheme: Professional trading theme

Primary: Dark blue (#1e3a8a)
Secondary: Green for profits (#10b981), Red for losses (#ef4444)
Background: Light gray (#f3f4f6) or white
Text: Dark gray (#1f2937)
Typography:

Headers: Bold, sans-serif (e.g., Inter, Roboto)
Body: Regular, readable font
Monospace for numbers and prices
Layout:

Consistent padding and margins
Card-based design for metrics
Clear section separation
Responsive breakpoints
Initial Data Model
# Configuration
{
    "strategy": str,  # Selected strategy name
    "symbol": str,    # Trading symbol (e.g., "DAX")
    "interval": str,  # Time interval (e.g., "5m")
    "period": str     # Lookback period (e.g., "6mo")
}
# Backtest Results
{
    "metrics": {
        "total_return": float,
        "sharpe_ratio": float,
        "max_drawdown": float,
        "win_rate": float,
        "total_trades": int,
        "avg_trade": float
    },
    "equity_curve": pd.DataFrame,  # Columns: timestamp, equity
    "drawdown": pd.DataFrame,      # Columns: timestamp, drawdown
    "trades": pd.DataFrame         # Columns: timestamp, symbol, side, entry, exit, pnl, return
}
Migration Considerations
From Streamlit to Dash
Advantages of Dash:

More control over layout and styling
Better performance for complex applications
Production-ready with Flask integration
Advanced interactivity with callbacks
Better component reusability
Migration Effort:

Low: Data processing logic (reusable)
Medium: Chart creation (similar plotly API)
High: Layout and callbacks (different paradigm)
Integration Points
If integrating with existing systems:

API endpoints for backtest engine
Database connections for historical data
Real-time data feeds
User authentication (if required)
Logging and monitoring
Next Steps
✅ Extract requirements (this document)
⏳ Create implementation plan
⏳ Set up project structure
⏳ Implement core layout with dash-bootstrap-components
⏳ Create metric cards component
⏳ Implement charts (equity, drawdown, distribution)
⏳ Build trade log table
⏳ Implement backtest callback logic
⏳ Add styling and responsive design
⏳ Test and verify functionality
⏳ Deploy on port 9001
References
Screenshot: 

streamlit_dashboard_1765125323816.png
Recording: 

streamlit_dashboard_capture_1765125268752.webp
