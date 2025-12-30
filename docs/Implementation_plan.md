Implementation Plan: Automatic Trading Factory Dashboard
Goal Description
Build a new Automatic Trading Factory dashboard using Plotly Dash 3.x on port 9001, based on the requirements extracted from the existing TradeRunner Backtest Dashboard (Streamlit) running at http://127.0.0.1:8501/.

The new dashboard will provide:

Strategy configuration interface with symbol, interval, and period selection
Real-time backtest execution
Performance metrics display (Total Return, Sharpe Ratio, Max Drawdown, Win Rate, Total Trades, Avg Trade)
Interactive visualizations (Equity Curve, Drawdown Chart, Trade Distribution)
Detailed trade log with sortable, filterable table
Modern, responsive UI using dash-bootstrap-components
User Review Required
IMPORTANT

Technology Stack Confirmation

Using Plotly Dash 3.x with Flask backend
dash-bootstrap-components for styling (Bootstrap theme)
Port 9001 for the new dashboard
Fresh implementation (not modifying existing Streamlit app)
IMPORTANT

Data Source Clarification Needed The plan assumes we'll create a mock backtest engine for demonstration purposes. If you have an existing backtest engine/API that should be integrated, please provide:

API endpoint or module path
Expected input/output format
Authentication requirements (if any)
Proposed Changes
Project Structure
/home/mirko/.gemini/antigravity/playground/holographic-oort/
├── app.py                          # Main Dash application
├── requirements.txt                # Python dependencies
├── config/
│   └── settings.py                 # Application configuration
├── layouts/
│   ├── __init__.py
│   ├── sidebar.py                  # Configuration sidebar layout
│   └── main_content.py             # Main results area layout
├── components/
│   ├── __init__.py
│   ├── metrics_cards.py            # Performance metrics cards
│   ├── charts.py                   # Plotly charts (equity, drawdown, distribution)
│   └── trade_table.py              # Trade log DataTable
├── callbacks/
│   ├── __init__.py
│   └── backtest_callbacks.py       # Callback functions for interactivity
├── utils/
│   ├── __init__.py
│   ├── data_processing.py          # Data transformation utilities
│   └── backtest_engine.py          # Mock backtest engine (or API client)
├── assets/
│   ├── styles.css                  # Custom CSS styling
│   └── favicon.ico                 # Dashboard favicon
└── tests/
    ├── test_components.py          # Unit tests for components
    └── test_callbacks.py           # Integration tests for callbacks
Core Application
[NEW]

app.py
Main Dash application entry point that:

Initializes Dash app with Bootstrap theme
Registers all layouts (sidebar + main content)
Imports and registers callbacks
Configures server to run on port 9001
Sets up error handling
Key Features:

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)
app.layout = dbc.Container([
    # Header
    # Sidebar + Main Content Row
], fluid=True)
if __name__ == '__main__':
    app.run_server(debug=True, host='127.0.0.1', port=9001)
Configuration Layer
[NEW]

config/settings.py
Application-wide configuration including:

Available strategies list
Symbol options
Interval choices (1m, 5m, 15m, 30m, 1h, 1d)
Period choices (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
Port configuration
Color scheme constants
Layout Components
[NEW]

layouts/sidebar.py
Creates the left sidebar containing:

Dashboard title/header
Strategy dropdown (dcc.Dropdown)
Symbol text input (dbc.Input)
Interval dropdown (dcc.Dropdown)
Period dropdown (dcc.Dropdown)
"Run Backtest" button (dbc.Button with primary color)
Layout Structure:

sidebar = dbc.Col([
    html.H2("Configuration"),
    dbc.Label("Strategy"),
    dcc.Dropdown(id='strategy-dropdown', ...),
    dbc.Label("Symbol"),
    dbc.Input(id='symbol-input', value='DAX', ...),
    dbc.Label("Interval"),
    dcc.Dropdown(id='interval-dropdown', value='5m', ...),
    dbc.Label("Period"),
    dcc.Dropdown(id='period-dropdown', value='6mo', ...),
    dbc.Button("Run Backtest", id='run-button', ...)
], width=3)
[NEW]

layouts/main_content.py
Main content area layout containing:

Metrics cards row (calls metrics_cards component)
Charts section with tabs or stacked layout:
Equity curve chart
Drawdown chart
Trade distribution chart
Trade log table section
Loading spinner overlay
UI Components
[NEW]

components/metrics_cards.py
Creates 6 metric cards using dbc.Card:

Total Return (%)
Sharpe Ratio
Max Drawdown (%)
Win Rate (%)
Total Trades
Average Trade (%)
Each card contains:

Label (card header)
Value (large, bold text)
Color coding (green for positive, red for negative where applicable)
Example:

def create_metric_card(label, value, color="primary"):
    return dbc.Card([
        dbc.CardHeader(label),
        dbc.CardBody([
            html.H2(value, className="text-center")
        ])
    ], color=color, outline=True)
[NEW]

components/charts.py
Chart creation functions using plotly.graph_objects:

create_equity_curve(df)

Line chart with timestamp on x-axis, equity on y-axis
Hover tooltips showing date and value
Responsive layout
create_drawdown_chart(df)

Area chart showing drawdown percentage
Red fill for negative values
Hover tooltips
create_trade_distribution(df)

Histogram of trade returns
Color-coded bins (green for wins, red for losses)
Count on y-axis
[NEW]

components/trade_table.py
Creates dash_table.DataTable for trade log:

Columns: Timestamp, Symbol, Side, Entry Price, Exit Price, P&L, Return %
Features:
Sortable columns
Filterable columns
Pagination (50 rows per page)
Export to CSV
Conditional formatting (green for profits, red for losses)
Backend Logic
[NEW]

callbacks/backtest_callbacks.py
Dash callback functions:

Main Callback:

@app.callback(
    Output('metrics-row', 'children'),
    Output('equity-chart', 'figure'),
    Output('drawdown-chart', 'figure'),
    Output('distribution-chart', 'figure'),
    Output('trade-table', 'data'),
    Input('run-button', 'n_clicks'),
    State('strategy-dropdown', 'value'),
    State('symbol-input', 'value'),
    State('interval-dropdown', 'value'),
    State('period-dropdown', 'value'),
    prevent_initial_call=True
)
def run_backtest(n_clicks, strategy, symbol, interval, period):
    # Execute backtest
    # Process results
    # Return updated components
[NEW]

utils/backtest_engine.py
Mock backtest engine that:

Accepts configuration (strategy, symbol, interval, period)
Generates synthetic backtest results for demonstration
Returns structured data:
Metrics dictionary
Equity curve DataFrame
Drawdown DataFrame
Trades DataFrame
Alternative: If integrating with existing engine, this would be an API client module.

[NEW]

utils/data_processing.py
Data transformation utilities:

Format numbers for display (e.g., percentage formatting)
Calculate derived metrics
Transform DataFrames for chart consumption
Validation functions
Styling
[NEW]

assets/styles.css
Custom CSS for:

Dashboard-wide color scheme
Card styling enhancements
Typography (fonts, sizes, weights)
Spacing and margins
Responsive breakpoints
Chart container styling
Button hover effects
Color Palette:

Primary: #1e3a8a (dark blue)
Success: #10b981 (green)
Danger: #ef4444 (red)
Background: #f3f4f6 (light gray)
Text: #1f2937 (dark gray)
Dependencies
[NEW]

requirements.txt
dash==3.0.0
dash-bootstrap-components==1.6.0
plotly==5.24.0
pandas==2.2.0
flask==3.0.0
Verification Plan
Automated Tests
Test 1: Component Rendering
File: tests/test_components.py Command: pytest tests/test_components.py -v What it tests:

Metric cards render with correct structure
Charts are created with valid plotly figures
Trade table generates correct columns
Test 2: Callback Functionality
File: tests/test_callbacks.py Command: pytest tests/test_callbacks.py -v What it tests:

Backtest callback executes without errors
All outputs are properly updated
Input validation works correctly
Note: These tests will be written as part of the implementation.

Manual Verification
Test 3: Dashboard Launch
Navigate to project directory: cd /home/mirko/.gemini/antigravity/playground/holographic-oort
Activate virtual environment (if using): source venv/bin/activate
Install dependencies: pip install -r requirements.txt
Run the dashboard: python app.py
Expected: Server starts on http://127.0.0.1:9001 without errors
Open browser and navigate to http://127.0.0.1:9001
Expected: Dashboard loads with sidebar visible on left, main content area on right
Test 4: Interactive Backtest
In the sidebar, select:
Strategy: "Inside Bar"
Symbol: "DAX"
Interval: "5m"
Period: "6mo"
Click "Run Backtest" button
Expected:
Loading spinner appears briefly
Metrics cards populate with values (e.g., Total Return: X%, Sharpe Ratio: X.XX)
Equity curve chart displays line graph
Drawdown chart displays area chart
Trade distribution chart displays histogram
Trade table populates with rows
Test 5: Responsive Design
With dashboard open, resize browser window to mobile width (~400px)
Expected:
Sidebar stacks above main content
Charts remain readable
Table becomes scrollable horizontally
Test 6: Chart Interactivity
Hover over equity curve chart
Expected: Tooltip shows date and equity value
Zoom into a section of the chart (click and drag)
Expected: Chart zooms smoothly
Double-click chart
Expected: Chart resets to original view
Test 7: Table Features
Click on a table column header (e.g., "Return %")
Expected: Table sorts by that column
Click again
Expected: Sort direction reverses
Use the table filter (if implemented)
Expected: Rows filter based on input
Browser Testing
File: Will use browser_subagent for automated UI testing Steps:

Navigate to http://127.0.0.1:9001
Verify page title contains "Automatic Trading Factory"
Click "Run Backtest" button
Wait for results to load
Capture screenshot for visual verification
Notes
The mock backtest engine will generate realistic-looking synthetic data for demonstration
If you have an existing backtest API/module, please provide integration details
All charts use plotly's interactive features (zoom, pan, hover, download)
Dashboard is designed to be extended with additional strategies and features
Responsive design ensures usability on desktop, tablet, and mobile devices
