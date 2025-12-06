# Trading Dashboard - User Guide

## Overview
The Trading Dashboard provides real-time monitoring of your trading system with four main tabs:
- **Live Monitor** - Real-time watchlist, pattern detection, and order flow
- **Portfolio** - Current positions and account value
- **Charts** - Interactive candlestick charts with pattern overlays
- **History** - Historical events and data export

---

## Getting Started

### Accessing the Dashboard
- **Local**: http://localhost:9001
- **Production**: http://192.168.178.55:9001
- **Credentials**: admin / admin

### Navigation
Click tabs at the top to switch between views. Each tab updates automatically (except Charts tab which requires manual refresh).

---

## Live Monitor Tab

### Features
- **Watchlist**: Currently monitored symbols from `strategy_params.yaml`
- **Pattern Detection**: Real-time Inside Bar pattern alerts
- **Order Flow**: Pipeline showing signal → order intent → execution
- **System Status**: Market hours and service health
- **Portfolio Value**: Current account balance (starts at $10,000)

### Auto-Refresh
Updates every 5 seconds automatically.

---

## Charts Tab

### Viewing Charts
1. Select symbol from dropdown (default: first symbol in watchlist)
2. Choose timeframe: M1, M5, M15, or H1
3. Toggle timezone: NY Time or Berlin Time
4. Chart shows last 24 hours of data

### Interacting with Charts
- **Pan**: Click and drag on chart
- **Zoom**: Mouse scroll wheel
- **Reset**: Double-click chart
- **Export**: Camera icon in toolbar

### Pattern Overlays
-Yellow rectangles highlight Inside Bar patterns
- Green/Red/Blue lines show Entry/Stop Loss/Take Profit levels

### Manual Refresh
Click "🔄 Refresh Chart" button to update data. Chart does NOT auto-refresh to prevent flickering.

### Timezone Switcher
- **🕐 NY Time**: Shows EST/EDT (America/New_York)
- **🕐 Berlin Time**: Shows CET/CEST (Europe/Berlin) - Default

---

## Portfolio Tab

### Account Summary
- **Total Value**: Current portfolio value
- **Cash**: Available buying power
- **Positions**: Market value of open positions
- **Daily P&L**: Today's profit/loss with percentage

### Positions Table
Shows all open positions with:
- Symbol and quantity
- Average entry price
- Current market price
- Unrealized P&L (green=profit, red=loss)

---

## History Tab

### Date Range Selection
1. Click calendar icon next to "Date Range"
2. Select start and end dates
3. Timeline updates automatically

### Filtering Events
- **Symbol Filter**: Show events for specific symbol or all
- **Status Filter**: Filter by pending/triggered/filled/rejected

### Event Types
- **Pattern Detected** (Yellow): Inside Bar pattern identified
- **Order Intent** (Blue): Trade signal created
- **Order Executed** (varies): Trade filled/rejected

### Daily Statistics
Four cards show:
- Total patterns detected
- Patterns that triggered
- Orders created
- Orders filled

### Exporting Data
1. Apply desired filters
2. Click "📥 Download CSV"
3. File downloads as `trading_events_START_END.csv`

**Export Limit**: 500 most recent events

---

## Keyboard Shortcuts

None currently implemented.

---

## Troubleshooting

### Dashboard won't load
- Check service status: `sudo systemctl status trading-dashboard-v2`
- View logs: `sudo journalctl -u trading-dashboard-v2 -f`
- Restart: `sudo systemctl restart trading-dashboard-v2`

### Chart not showing data
- If "No data available": Mock data should always generate
- If chart changes on refresh: Report bug (should be deterministic)

### History tab shows no events
- Check date range (default: yesterday to today)
- Verify signals.db and trading.db exist
- Events only show if patterns/orders were created in date range

### CSV export not working
- Check browser download settings
- Try different date range
- Verify events exist for selected filters

---

## Data Sources

| Component | Source | Location |
|-----------|--------|----------|
| Watchlist | YAML file | `marketdata-stream/config/strategy_params.yaml` |
| Patterns | SQLite | `marketdata-stream/data/signals.db` |
| Orders | SQLite | `automatictrader-api/data/trading.db` |
| Candles | Mock data | Generated deterministically per symbol+date |
| Portfolio | Internal | Starts at $10,000 (no positions yet) |

---

## Technical Details

### Update Frequencies
- **Live Monitor**: 5 seconds
- **Portfolio**: 5 seconds
- **Charts**: Manual (button click)
- **History**: On filter change

### Data Retention
- **Signals**: Unlimited (SQLite)
- **Orders**: Unlimited (SQLite)
- **Candles**: Mock data (24 hours)

### Browser Compatibility
Tested on:
- Chrome 120+
- Firefox 120+
- Safari 17+

---

## Support

For issues or questions:
1. Check logs: `sudo journalctl -u trading-dashboard-v2 -f`
2.Review implementation plan artifact
3. Contact system administrator

---

## Version History

### Phase 3 (Current)
- Added History tab with date filtering
- Implemented CSV export
- Created automated tests
- Added deployment script

### Phase 2
- Added Charts tab with interactive candlestick
- Implemented timezone switcher (NY/Berlin)
- Added Portfolio tab with $10k starting value

### Phase 1
- Initial Live Monitor implementation
- Basic authentication (admin/admin)
- Dark theme styling
