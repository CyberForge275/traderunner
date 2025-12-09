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
        version: Optional[str] = None,  # NEW: Version parameter
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
            version: Optional version number (e.g., '1.00', '2.01')
            config_params: Optional strategy configuration parameters
            
        Returns:
            Dictionary with:
                - status: 'completed' or 'failed'
                - signals_generated: Number of signals generated
                - signals: List of signal dictionaries
                - error: Error message if failed
        """
        try:
            # Load version-specific config if version provided
            if version:
                version_config = self._load_version_config(strategy, version)
                # Merge with user-provided config_params (user params take precedence)
                if config_params:
                    version_config.update(config_params)
                config_params = version_config
            
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
    
    def _get_lookback_periods(
        self,
        strategy: str,
        timeframe: str
    ) -> Dict[str, int]:
        """
        Get lookback period requirements for a strategy.
        
        Strategies need historical data before the target date to calculate
        indicators like ATR(14), SMA(200), etc. This method returns the
        minimum lookback requirements based on the strategy and timeframe.
        
        Args:
            strategy: Strategy name (e.g., 'inside_bar', 'rudometkin_moc')
            timeframe: Timeframe (M1, M5, M15, D, etc.)
            
        Returns:
            Dictionary with:
                - min_candles: Minimum number of candles needed
                - min_days: Minimum number of days needed
                - description: What indicators need this lookback
        """
        # Strategy-specific lookback requirements
        # Based on actual strategy code analysis
        LOOKBACK_CONFIG = {
            'inside_bar': {
                'min_candles': 50,  # ATR(14) + buffer for pattern detection
                'min_days': 3,      # For intraday, load at least 3 days
                'description': 'ATR(14) calculation + pattern lookback'
            },
            'rudometkin_moc': {
                'min_candles': 300,  # SMA(200) + buffer for other indicators
                'min_days': 300,     # For daily data (SMA200 + ADX, CRSI, ATR40)
                'description': 'SMA(200), ADX, ATR40, CRSI calculations'
            }
        }
        
        # Get config for strategy, or use conservative defaults
        config = LOOKBACK_CONFIG.get(strategy, {
            'min_candles': 100,  # Default: generous buffer
            'min_days': 5,       # For intraday strategies
            'description': 'Default safety buffer for indicators'
        })
        
        self.progress_callback(
            f"Lookback requirement: {config['min_candles']} candles "
            f"({config['description']})"
        )
        
        return config
    
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
        
        target_date_ts = pd.to_datetime(target_date)
        self.progress_callback(f"Replaying session from {target_date}...")
        
        # CRITICAL: Get lookback requirements for indicator calculations
        # Strategies need historical data (e.g., ATR needs 14 candles, SMA200 needs 200 days)
        lookback_config = self._get_lookback_periods(strategy, timeframe)
        
        # Calculate lookback start date based on timeframe
        if timeframe.upper() in ['M1', 'M5', 'M15', 'M30', 'H1', 'H4']:
            # Intraday: Load multiple days to ensure enough candles
            # Example: M5 with 50 candles = 250 minutes ≈ 4.2 hours
            # We load full days to ensure market hours coverage
            lookback_days = max(lookback_config['min_days'], 3)  # At least 3 days
            lookback_start = target_date_ts - pd.Timedelta(days=lookback_days)
            
            self.progress_callback(
                f"Loading {lookback_days} days of {timeframe} data "
                f"for {lookback_config['min_candles']} candle lookback"
            )
        else:
            # Daily or higher: Use day count directly
            lookback_days = lookback_config['min_days']
            lookback_start = target_date_ts - pd.Timedelta(days=lookback_days)
            
            self.progress_callback(
                f"Loading {lookback_days} days for indicator calculations"
            )
        
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
            
            # CRITICAL: Normalize timezone handling
            # Convert DataFrame index to timezone-naive for consistent comparison
            if hasattr(df.index, 'tz') and df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            
            # Get data bounds for logging (now timezone-naive)
            data_start = df.index.min()
            data_end = df.index.max()
            
            # Ensure lookback_start and target dates are also timezone-naive
            lookback_start_naive = pd.to_datetime(lookback_start).tz_localize(None) if hasattr(lookback_start, 'tz') else lookback_start
            target_date_ts_naive = pd.to_datetime(target_date_ts).tz_localize(None) if hasattr(target_date_ts, 'tz') else target_date_ts
            
            # Check if lookback_start is before available data
            if lookback_start_naive < data_start:
                actual_lookback_days = (target_date_ts_naive - data_start).days
                self.progress_callback(
                    f"⚠️ {symbol}: Requested {lookback_days}-day lookback, "
                    f"but data starts at {data_start.date()}. "
                    f"Using {actual_lookback_days} days of available history."
                )
                effective_start = data_start
            else:
                effective_start = lookback_start_naive
            
            # STEP 1: Load data WITH lookback buffer (from lookback_start to target_end)
            # This ensures indicators have enough historical data
            target_end = target_date_ts_naive + pd.Timedelta(days=1)
            df_with_lookback = df[(df.index >= effective_start) & (df.index < target_end)]
            
            if df_with_lookback.empty:
                self.progress_callback(
                    f"⚠️ No data for {symbol} in range {effective_start.date()} to {target_date}, skipping..."
                )
                continue
            
            self.progress_callback(
                f"  {symbol}: Loaded {len(df_with_lookback)} candles "
                f"({effective_start.date()} to {data_end.date() if data_end < target_end else target_date})"
            )
            
            # STEP 2: Run strategy detection on FULL dataset (with lookback)
            # This allows indicators to calculate correctly
            strategy_signals = self._run_strategy_detection(
                strategy, symbol, df_with_lookback, config_params
            )
            
            # STEP 3: Filter signals to ONLY target_date
            # Important: Only include signals detected ON the replay date
            # This prevents "future" signals from appearing in results
            filtered_signals = []
            for sig in strategy_signals:
                sig_time = pd.to_datetime(sig['detected_at'])
                # Make timezone-naive for comparison
                if hasattr(sig_time, 'tz') and sig_time.tz is not None:
                    sig_time = sig_time.tz_localize(None)
                if target_date_ts_naive <= sig_time < target_end:
                    filtered_signals.append(sig)
            
            if len(filtered_signals) < len(strategy_signals):
                self.progress_callback(
                    f" {symbol}: Filtered {len(strategy_signals)} total signals → "
                    f"{len(filtered_signals)} from target date {target_date}"
                )
            
            signals.extend(filtered_signals)
        
        self.progress_callback(f"Writing {len(signals)} signals to database...")
        
        # Write signals to database
        self._write_signals_to_db(signals, source="pre_papertrade_replay")
        
        return {
            "status": "completed",
            "signals_generated": len(signals),
            "signals": signals,
            "mode": "replay",
            "replay_date": target_date,
            "lookback_days": lookback_days,
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
        Run strategy detection using the strategy factory.
        
        This method uses the strategy registry to get the correct strategy
        version (V1, V2, etc.) and runs it with the exact configuration.
        
        Args:
            strategy: Strategy name from STRATEGY_REGISTRY
            symbol: Stock symbol
            df: OHLCV DataFrame
            config_params: Strategy configuration parameters
            
        Returns:
            List of signal dictionaries in Pre-PaperTrade format
        """
        return self._run_strategy_with_factory(
            strategy, symbol, df, config_params
        )
    
    def _run_strategy_with_factory(
        self, 
        strategy: str, 
        symbol: str, 
        df: pd.DataFrame, 
        config_params: Optional[Dict]
    ) -> List[Dict]:
        """
        Run strategy detection using the strategy factory pattern.
        
        This method:
        1. Loads the correct strategy class from registry
        2. Creates an instance with config_params
        3. Runs generate_signals() method
        4. Converts strategy Signals to Pre-PaperTrade dict format
        
        Args:
            strategy: Strategy name (e.g., 'insidebar_intraday', 'insidebar_intraday_v2')
            symbol: Stock symbol
            df: OHLCV DataFrame
            config_params: Strategy configuration parameters
            
        Returns:
            List of signal dictionaries
        """
        from strategies import factory, registry
        
        # Map dashboard strategy names to strategy class names
        strategy_name_map = {
            "insidebar_intraday": "inside_bar",
            "insidebar_intraday_v2": "inside_bar_v2",
            "rudometkin_moc_mode": "rudometkin_moc",
        }
        
        # Get the strategy class name
        strategy_class_name = strategy_name_map.get(strategy, strategy)
        
        self.progress_callback(f"Using strategy: {strategy_class_name} (version: {strategy})")
        
        try:
            # Auto-discover strategies from registry
            registry.auto_discover("strategies")
            
            # Create strategy instance with config
            strategy_instance = factory.create_strategy(
                strategy_class_name, 
                config_params or {}
            )
            
            # Prepare DataFrame for strategy
            df_prepared  = self._prepare_dataframe_for_strategy(df)
            
            # Run strategy's generate_signals method
            signals = strategy_instance.generate_signals(
                df_prepared, 
                symbol, 
                config_params or {}
            )
            
            # Convert strategy Signals to Pre-PaperTrade dict format
            return self._convert_signals_to_dict(signals, symbol)
            
        except (ValueError, KeyError, AttributeError) as e:
            self.progress_callback(f"⚠️ Strategy error for {symbol}: {e}")
            raise ValueError(f"Strategy '{strategy}' failed for {symbol}: {e}")
    
    def _prepare_dataframe_for_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare DataFrame for strategy consumption.
        
        Ensures DataFrame has required columns and format:
        - timestamp column (from index if needed)
        - lowercase column names
        - sorted by timestamp
        """
        df_prepared = df.copy()
        
        # Ensure timestamp column exists
        if 'timestamp' not in df_prepared.columns:
            df_prepared = df_prepared.reset_index()
            if df_prepared.columns[0] != 'timestamp':
                df_prepared = df_prepared.rename(columns={df_prepared.columns[0]: 'timestamp'})
        
        # Ensure lowercase column names (strategies expect this)
        df_prepared.columns = [c.lower() for c in df_prepared.columns]
        
        # Sort by timestamp
        if 'timestamp' in df_prepared.columns:
            df_prepared = df_prepared.sort_values('timestamp').reset_index(drop=True)
        
        return df_prepared
    
    def _convert_signals_to_dict(self, signals: List, symbol: str) -> List[Dict]:
        """
        Convert strategy Signal objects to Pre-PaperTrade dictionary format.
        
        Args:
            signals: List of Signal objects from strategy
            symbol: Stock symbol
            
        Returns:
            List of signal dictionaries with required fields
        """
        dict_signals = []
        
        for signal in signals:
            # Extract timestamp
            timestamp = signal.timestamp
            if hasattr(timestamp, 'isoformat'):
                detected_at = timestamp.isoformat()
            else:
                detected_at = str(timestamp)
            
            # Map signal_type to side (LONG/SHORT → BUY/SELL)
            signal_type = getattr(signal, 'signal_type', '').upper()
            if signal_type in ['LONG', 'BUY']:
                side = 'BUY'
            elif signal_type in ['SHORT', 'SELL']:
                side = 'SELL'
            else:
                self.progress_callback(f"⚠️ Unknown signal type: {signal_type}, skipping")
                continue
            
            dict_signals.append({
                "symbol": symbol,
                "side": side,
                "entry_price": float(signal.entry_price) if signal.entry_price else 0.0,
                "stop_loss": float(signal.stop_loss) if signal.stop_loss else 0.0,
                "take_profit": float(signal.take_profit) if signal.take_profit else 0.0,
                "detected_at": detected_at,
                "strategy": signal.strategy if hasattr(signal, 'strategy') else "unknown",
                "timeframe": "M5",  # TODO: Get from config
                "metadata": signal.metadata if hasattr(signal, 'metadata') else {}
            })
        
        return dict_signals
    
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
    
    def _load_version_config(self, strategy: str, version: str) -> Dict:
        """
        Load configuration from version registry.
        
        Args:
            strategy: Strategy name (e.g., 'insidebar_intraday')
            version: Version number (e.g., '1.00')
            
        Returns:
            Configuration dictionary loaded from version YAML file
        """
        import sqlite3
        import yaml
        from pathlib import Path
        
        # Map dashboard strategy names to folder names
        strategy_map = {
            "insidebar_intraday": "inside_bar",
            "insidebar_intraday_v2": "inside_bar_v2",
            "rudometkin_moc_mode": "rudometkin_moc",
        }
        
        folder_name = strategy_map.get(strategy)
        if not folder_name:
            self.progress_callback(f"⚠ Unknown strategy: {strategy}, using defaults")
            return {}
        
        # Path to registry database
        db_path = ROOT / "src" / "strategies" / folder_name / "registry.db"
        
        if not db_path.exists():
            self.progress_callback(f"⚠ No registry DB for {strategy}, using defaults")
            return {}
        
        try:
            # Query registry for config path
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT config_path FROM versions WHERE version = ?",
                (version,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                self.progress_callback(f"⚠ Version {version} not found in registry, using defaults")
                return {}
            
            config_path = Path(row[0])
            
            # Load YAML config
            if not config_path.exists():
                self.progress_callback(f"⚠ Config file not found: {config_path}, using defaults")
                return {}
            
            with open(config_path) as f:
                config = yaml.safe_load(f)
            
            self.progress_callback(f"✅ Loaded config for {strategy} v{version} from {config_path.name}")
            return config if config else {}
            
        except Exception as e:
            self.progress_callback(f"⚠ Error loading version config: {e}, using defaults")
            return {}


def create_adapter(progress_callback: Optional[Callable[[str], None]] = None) -> PrePaperTradeAdapter:
    """
    Factory function to create a Pre-PaperTrade adapter.
    
    Args:
        progress_callback: Optional function to call with progress updates
        
    Returns:
        Configured PrePaperTradeAdapter instance
    """
    return PrePaperTradeAdapter(progress_callback)
