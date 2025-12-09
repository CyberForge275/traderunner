"""
Pre-PaperTrade Lab adapter for running strategies in testing mode.

This adapter executes strategies in two modes:
- Replay: Run strategy on historical data
- Live: Run strategy on live market data

Signals are written to signals.db for testing the signal → order pipeline.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Callable, Literal
from datetime import datetime, date
import pandas as pd

# Add necessary paths
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
APPS_DIR = ROOT / "apps"
STREAMLIT_DIR = APPS_DIR / "streamlit"

# Ensure paths are available for imports
for path in [str(SRC), str(APPS_DIR), str(STREAMLIT_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)


class PrePaperTradeAdapter:
    """
    Adapter for running strategies in Pre-PaperTrade mode.
    
    This adapter:
    - Executes strategies on historical or live data
    - Generates signals using strategy core logic
    - Writes signals to signals.db
    - Provides progress callbacks for UI updates
    """
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize the adapter.
        
        Args:
            progress_callback: Optional function to call with progress updates
        """
        self.progress_callback = progress_callback or (lambda msg: None)
        self.signals_db_path = Path("/opt/trading/marketdata-stream/data/signals.db")
        # For local testing, use a local path
        if not self.signals_db_path.exists():
            self.signals_db_path = ROOT / "artifacts" / "signals.db"
    
    def execute_strategy(
        self,
        strategy: str,
        mode: Literal["replay", "live"],
        symbols: List[str],
        timeframe: str,
        replay_date: Optional[str] = None,
        config_params: Optional[Dict] = None,
    ) -> Dict:
        """
        Execute a strategy in Pre-PaperTrade mode.
        
        Args:
            strategy: Strategy name (e.g., 'inside_bar', 'rudometkin_moc')
            mode: 'replay' (Time Machine for single day) or 'live' (real-time)
            symbols: List of stock symbols
            timeframe: Timeframe (e.g., 'M5', 'M15', 'D')
            replay_date: Single date for Time Machine replay (YYYY-MM-DD)
            config_params: Optional strategy configuration parameters
            
        Returns:
            Dictionary with:
                - status: 'completed' or 'failed'
                - signals_generated: Number of signals generated
                - signals: List of signal dictionaries
                - error: Error message if failed
        """
        try:
            if mode == "replay":
                return self._execute_replay(
                    strategy, symbols, timeframe, 
                    replay_date, config_params
                )
            elif mode == "live":
                return self._execute_live(
                    strategy, symbols, timeframe, config_params
                )
            else:
                raise ValueError(f"Invalid mode: {mode}. Must be 'replay' or 'live'")
                
        except Exception as e:
            import traceback
            return {
                "status": "failed",
                "error": f"{type(e).__name__}: {str(e)}",
                "traceback": traceback.format_exc(),
                "ended_at": datetime.now().isoformat(),
            }
    
    def _execute_replay(
        self,
        strategy: str,
        symbols: List[str],
        timeframe: str,
        replay_date: Optional[str],
        config_params: Optional[Dict],
    ) -> Dict:
        """Execute strategy in Time Machine mode - replay a single past trading day."""
        self.progress_callback("Loading strategy module...")
        
        # Import strategy modules
        from apps.streamlit.state import STRATEGY_REGISTRY
        
        strategy_obj = STRATEGY_REGISTRY.get(strategy)
        if not strategy_obj:
            available = list(STRATEGY_REGISTRY.keys())
            raise ValueError(f"Unknown strategy: {strategy}. Available: {available}")
        
        self.progress_callback("⏰ Time Machine activated...")
        
        # Use replay_date or default to yesterday
        if replay_date:
            target_date = replay_date
        else:
            target_date = (datetime.now().date() - pd.Timedelta(days=1)).isoformat()
        
        self.progress_callback(f"Replaying session from {target_date}...")
        
        # Load historical data
        data_dir = ROOT / "artifacts" / f"data_{timeframe.lower()}"
        signals = []
        
        for symbol in symbols:
            self.progress_callback(f"Processing {symbol}...")
            
            data_file = data_dir / f"{symbol}.parquet"
            if not data_file.exists():
                self.progress_callback(f"⚠️ No data for {symbol}, skipping...")
                continue
            
            df = pd.read_parquet(data_file)
            
            # Filter for single day
            # Corrected from user's proposed `df[(df.index >= target_date) & (df.index < target_date)]`
            # which would always result in an empty DataFrame.
            # This filters for data points on the target_date.
            df = df[(df.index >= target_date) & (df.index < pd.to_datetime(target_date) + pd.Timedelta(days=1))]
            
            if df.empty:
                self.progress_callback(f"⚠️ No data for {symbol} on {target_date}, skipping...")
                continue
            
            # Run strategy detection
            strategy_signals = self._run_strategy_detection(
                strategy, symbol, df, config_params
            )
            
            signals.extend(strategy_signals)
        
        self.progress_callback(f"Writing {len(signals)} signals to database...")
        
        # Write signals to database
        self._write_signals_to_db(signals, source="pre_papertrade_replay")
        
        return {
            "status": "completed",
            "signals_generated": len(signals),
            "signals": signals,
            "mode": "replay",
            "replay_date": target_date,
            "ended_at": datetime.now().isoformat(),
        }
    
    def _execute_live(
        self,
        strategy: str,
        symbols: List[str],
        timeframe: str,
        config_params: Optional[Dict],
    ) -> Dict:
        """Execute strategy in live mode (placeholder for future implementation)."""
        self.progress_callback("Live mode not yet implemented...")
        
        # TODO: Implement live mode integration with marketdata-stream
        # This will require:
        # 1. Connect to marketdata-stream websocket or database
        # 2. Subscribe to symbol updates
        # 3. Run strategy detection on incoming ticks
        # 4. Write signals to signals.db in real-time
        
        return {
            "status": "failed",
            "error": "Live mode not yet implemented. Please use replay mode.",
            "ended_at": datetime.now().isoformat(),
        }
    
    def _run_strategy_detection(
        self,
        strategy: str,
        symbol: str,
        df: pd.DataFrame,
        config_params: Optional[Dict],
    ) -> List[Dict]:
        """
        Run strategy detection logic on historical data.
        
        Args:
            strategy: Strategy name
            symbol: Stock symbol
            df: OHLCV DataFrame
            config_params: Strategy configuration parameters
            
        Returns:
            List of signal dictionaries
        """
        signals = []
        
        if strategy == "inside_bar":
            signals = self._detect_inside_bar(symbol, df, config_params)
        elif strategy == "rudometkin_moc":
            signals = self._detect_rudometkin_moc(symbol, df, config_params)
        else:
            raise ValueError(f"Strategy detection not implemented for: {strategy}")
        
        return signals
    
    def _detect_inside_bar(
        self, symbol: str, df: pd.DataFrame, config_params: Optional[Dict]
    ) -> List[Dict]:
        """Detect InsideBar patterns and generate signals."""
        from strategies.inside_bar.core import detect_inside_bars, InsideBarConfig
        
        # Build config from parameters
        config = InsideBarConfig(
            risk_reward_ratio=config_params.get("risk_reward_ratio", 2.0) if config_params else 2.0,
            volume_filter=config_params.get("volume_filter", True) if config_params else True,
        )
        
        # Detect inside bars
        detected = detect_inside_bars(df, config)
        
        signals = []
        for _, row in detected.iterrows():
            # Create BUY signal
            if row.get("breakout_high"):
                signals.append({
                    "symbol": symbol,
                    "side": "BUY",
                    "entry_price": float(row["breakout_high"]),
                    "stop_loss": float(row["stop_loss_high"]),
                    "take_profit": float(row["take_profit_high"]),
                    "detected_at": row.name.isoformat(),
                    "strategy": "inside_bar",
                    "timeframe": "M5",  # TODO: Get from config
                })
            
            # Create SELL signal
            if row.get("breakout_low"):
                signals.append({
                    "symbol": symbol,
                    "side": "SELL",
                    "entry_price": float(row["breakout_low"]),
                    "stop_loss": float(row["stop_loss_low"]),
                    "take_profit": float(row["take_profit_low"]),
                    "detected_at": row.name.isoformat(),
                    "strategy": "inside_bar",
                    "timeframe": "M5",
                })
        
        return signals
    
    def _detect_rudometkin_moc(
        self, symbol: str, df: pd.DataFrame, config_params: Optional[Dict]
    ) -> List[Dict]:
        """Detect Rudometkin MOC signals."""
        # TODO: Implement Rudometkin MOC detection
        # For now, return empty list
        return []
    
    def _write_signals_to_db(self, signals: List[Dict], source: str):
        """
        Write signals to signals.db.
        
        Args:
            signals: List of signal dictionaries
            source: Source identifier (e.g., 'pre_papertrade_replay')
        """
        import sqlite3
        
        # Ensure database directory exists
        self.signals_db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.signals_db_path))
        cursor = conn.cursor()
        
        # Create signals table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                detected_at TEXT NOT NULL,
                strategy TEXT NOT NULL,
                timeframe TEXT,
                source TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        """)
        
        # Insert signals
        for signal in signals:
            cursor.execute("""
                INSERT INTO signals (
                    symbol, side, entry_price, stop_loss, take_profit,
                    detected_at, strategy, timeframe, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal["symbol"],
                signal["side"],
                signal["entry_price"],
                signal.get("stop_loss"),
                signal.get("take_profit"),
                signal["detected_at"],
                signal["strategy"],
                signal.get("timeframe"),
                source,
            ))
        
        conn.commit()
        conn.close()
        
        self.progress_callback(f"✅ Wrote {len(signals)} signals to {self.signals_db_path}")


def create_adapter(progress_callback: Optional[Callable[[str], None]] = None) -> PrePaperTradeAdapter:
    """
    Factory function to create a Pre-PaperTrade adapter.
    
    Args:
        progress_callback: Optional function to call with progress updates
        
    Returns:
        Configured PrePaperTradeAdapter instance
    """
    return PrePaperTradeAdapter(progress_callback)
