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

# Import DataManager for auto-download capability
from data.data_manager import DataManager


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
        # Always log to console for debugging + call user callback if provided
        def _log_and_callback(msg: str):
            print(f"[PRE-PAPERTRADE] {msg}")  # Console logging
            if progress_callback:
                progress_callback(msg)  # UI callback
        
        self.progress_callback = _log_and_callback
        
        # Use central Settings for paths (eliminates hard-coded paths)
        from src.core.settings import get_settings
        settings = get_settings()
        self.signals_db_path = settings.signals_db_path
        
        # Initialize DataManager for auto-download capability
        import os
        eodhd_key = os.getenv("EODHD_API_KEY") or os.getenv("EODHD_API_TOKEN")
        self.data_manager = DataManager(
            data_dir=str(ROOT / "data"),
            cache_enabled=True,
            eodhd_api_key=eodhd_key
        )
        logger_dm = logging.getLogger('trading_dashboard.services.pre_papertrade')
        if eodhd_key:
            logger_dm.info(f"✅ DataManager initialized with EODHD integration (key: {eodhd_key[:8]}...)")
        else:
            logger_dm.warning("⚠️  DataManager initialized WITHOUT EODHD key (auto-download will fail)")
    
    def __enter__(self):
        """Enter context manager - enables 'with' statement usage."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context manager - cleanup resources.
        
        Args:
            exc_type: Exception type if raised
            exc_val: Exception value if raised
            exc_tb: Exception traceback if raised
            
        Returns:
            False to propagate exceptions (don't suppress them)
        """
        # Cleanup: flush any pending logs, close connections, etc.
        # Currently no resources that need explicit cleanup
        return False  # Don't suppress exceptions
    
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
        import logging
        
        # Set up logger
        logger = logging.getLogger('trading_dashboard.services.pre_papertrade')
        signals_logger = logging.getLogger('trading_dashboard.services.pre_papertrade.signals')
        
        # Initialize metrics tracking
        metrics = {
            'symbols_total': len(symbols),
            'symbols_processed': 0,
            'symbols_failed': 0,
            'data_fetch_time': 0.0,
            'strategy_run_time': 0.0,
            'db_write_time': 0.0,
            'signals_generated': 0,
        }
        
        try:
            start_time = datetime.now()
            
            logger.info("="*60)
            logger.info("🚀 PRE-PAPERTRADE EXECUTION START")
            logger.info("="*60)
            logger.info(f"Strategy: {strategy}")
            logger.info(f"Version: {version or 'default'}")
            logger.info(f"Mode: {mode}")
            logger.info(f"Symbols: {', '.join(symbols)}")
            logger.info(f"Timeframe: {timeframe}")
            if replay_date:
                logger.info(f"Replay Date: {replay_date}")
            logger.info("="*60)
            
            self.progress_callback(f"\n{'='*60}")
            self.progress_callback(f"🚀 PRE-PAPERTRADE EXECUTION START")
            self.progress_callback(f"{'='*60}")
            self.progress_callback(f"Strategy: {strategy}")
            self.progress_callback(f"Version: {version or 'default'}")
            self.progress_callback(f"Mode: {mode}")
            self.progress_callback(f"Symbols: {', '.join(symbols)}")
            self.progress_callback(f"Timeframe: {timeframe}")
            if replay_date:
                self.progress_callback(f"Replay Date: {replay_date}")
            self.progress_callback(f"{'='*60}\n")
            
            # Load version-specific config if version provided
            if version:
                config_start = datetime.now()
                self.progress_callback(f"📋 Loading version-specific config...")
                version_config = self._load_version_config(strategy, version)
                config_duration = (datetime.now() - config_start).total_seconds()
                self.progress_callback(f"✅ Config loaded in {config_duration:.2f}s ({len(version_config)} parameters)")
                
                # Ensure required parameters are present with defaults
                # Strategy classes validate against their schema, so we must provide required fields
                if strategy in ["insidebar_intraday", "insidebar_intraday_v2"]:
                    defaults = {
                        "atr_period": 14,
                        "risk_reward_ratio": 2.0,
                        "min_mother_bar_size": 0.5,
                        "breakout_confirmation": True,
                        "inside_bar_mode": "inclusive",
                        # Option B: No session filtering by default (None = all time periods)
                        # Session filtering can be configured in version YAML if needed
                        "session_filter": None,
                    }
                    
                    # Handle session_filter parameter from version config
                    if "session_filter" in version_config:
                        # If version config has session_filter as list of strings,
                        # convert to SessionFilter object
                        sf_config = version_config["session_filter"]
                        if isinstance(sf_config, list) and sf_config:
                            from src.strategies.inside_bar.config import SessionFilter
                            version_config["session_filter"] = SessionFilter.from_strings(sf_config)
                        elif sf_config is None or not sf_config:
                            version_config["session_filter"] = None
                    
                    # Merge: defaults first, then version config, then user params
                    final_config = {**defaults, **version_config}
                    if config_params:
                        final_config.update(config_params)
                    config_params = final_config
                else:
                    # Merge with user-provided config_params (user params take precedence)
                    if config_params:
                        version_config.update(config_params)
                    config_params = version_config
            else:
                self.progress_callback(f"📋 Using default config (no version specified)")
                # Provide defaults even when no version
                if config_params is None:
                    if strategy in ["insidebar_intraday", "insidebar_intraday_v2"]:
                        config_params = {
                            "atr_period": 14,
                            "risk_reward_ratio": 2.0,
                            "min_mother_bar_size": 0.5,
                            "breakout_confirmation": True,
                            "inside_bar_mode": "inclusive",
                        }
            
            if mode == "replay":
                result = self._execute_replay(
                    strategy, symbols, timeframe, 
                    replay_date, config_params
                )
            elif mode == "live":
                result = self._execute_live(
                    strategy, symbols, timeframe, config_params
                )
            else:
                raise ValueError(f"Invalid mode: {mode}. Must be 'replay' or 'live'")
            
            total_duration = (datetime.now() - start_time).total_seconds()
            
            # Calculate timeline breakdown
            if total_duration > 0:
                data_pct = int((metrics['data_fetch_time'] / total_duration) * 100)
                strategy_pct = int((metrics['strategy_run_time'] / total_duration) * 100)
                db_pct = int((metrics['db_write_time'] / total_duration) * 100)
            else:
                data_pct = strategy_pct = db_pct = 0
            
            # Log comprehensive summary
            logger.info("\n" + "="*60)
            logger.info("✅ EXECUTION COMPLETE")
            logger.info("="*60)
            logger.info(f"Total Time: {total_duration:.2f}s")
            logger.info(f"Symbols Processed: {metrics['symbols_processed']}/{metrics['symbols_total']}")
            logger.info(f"Symbols Failed: {metrics['symbols_failed']}")
            logger.info(f"Signals Generated: {metrics['signals_generated']}")
            logger.info("")
            logger.info("EXECUTION TIMELINE:")
            logger.info(f"├─ Data Fetching:   {metrics['data_fetch_time']:.2f}s ({data_pct}%)")
            logger.info(f"├─ Strategy Run:    {metrics['strategy_run_time']:.2f}s ({strategy_pct}%)")
            logger.info(f"├─ DB Write:        {metrics['db_write_time']:.2f}s ({db_pct}%)")
            logger.info(f"└─ Total:           {total_duration:.2f}s")
            logger.info("")
            if total_duration > 0 and metrics['symbols_processed'] > 0:
                logger.info("PERFORMANCE:")
                logger.info(f"• Symbols/sec:      {metrics['symbols_processed']/total_duration:.2f}")
                if metrics['signals_generated'] > 0:
                    logger.info(f"• Signals/sec:      {metrics['signals_generated']/total_duration:.2f}")
            logger.info("="*60)
            
            self.progress_callback(f"\n{'='*60}")
            self.progress_callback(f"✅ EXECUTION COMPLETE in {total_duration:.2f}s")
            self.progress_callback(f"")
            self.progress_callback(f"📊 SUMMARY:")
            self.progress_callback(f"  Symbols Processed: {metrics['symbols_processed']}/{metrics['symbols_total']}")
            self.progress_callback(f"  Total Signals: {metrics['signals_generated']}")
            if total_duration > 0:
                self.progress_callback(f"  Avg Time/Symbol: {total_duration/max(metrics['symbols_processed'], 1):.2f}s")
            self.progress_callback(f"")
            self.progress_callback(f"TIMELINE:")
            self.progress_callback(f"├─ Data Fetching:   {metrics['data_fetch_time']:.2f}s ({data_pct}%)")
            self.progress_callback(f"├─ Strategy Run:    {metrics['strategy_run_time']:.2f}s ({strategy_pct}%)")
            self.progress_callback(f"├─ DB Write:        {metrics['db_write_time']:.2f}s ({db_pct}%)")
            self.progress_callback(f"└─ Total:           {total_duration:.2f}s")
            self.progress_callback(f"{'='*60}\n")
            
            return result
                
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
        import logging
        
        # Initialize logger for this method
        logger = logging.getLogger('trading_dashboard.services.pre_papertrade')
        
        self.progress_callback("Loading strategy module...")
        logger.info("Loading strategy module...")
        
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
        all_signals = []
        
        # Process each symbol
        for idx, symbol in enumerate(symbols, 1):
            progress_pct = int((idx / len(symbols)) * 100)
            
            logger.info(f"\n[{idx}/{len(symbols)}] Processing {symbol}... ({progress_pct}%)")
            self.progress_callback(f"\n[{idx}/{len(symbols)}] 📊 Processing {symbol}... ({progress_pct}%)")
            
            fetch_start = datetime.now()
            
            try:
                # Fetch historical data with lookback
                logger.debug(f"⬇️  Fetching data for {symbol}...")
                self.progress_callback(f"  ⬇️  Fetching data...")
                # The `expected_candles` and `min_candles_needed` variables are not defined in the provided context.
                # Assuming they would be defined earlier in the `_execute_replay` method or derived from `lookback_config`.
                # For now, I'll comment them out or replace with a placeholder if they are not part of the current context.
                # Given the instruction, I will insert the code as provided, assuming these variables are handled elsewhere.
                # However, to make it syntactically correct and runnable, I need to define them or remove the lines.
                # Let's assume `min_candles_needed` is `lookback_config['min_candles']` and `expected_candles` is an estimate.
                min_candles_needed = lookback_config['min_candles']
                # Estimate expected candles based on timeframe and lookback days. This is a rough estimate.
                # For M5, 6.5 hours * 12 candles/hour * lookback_days
                # For D, 1 candle/day * lookback_days
                if timeframe.upper() == 'M5':
                    expected_candles = int(lookback_days * (6.5 * 12)) # Approx 6.5 trading hours * 12 M5 candles/hour
                elif timeframe.upper() == 'D':
                    expected_candles = lookback_days
                else:
                    expected_candles = min_candles_needed * 2 # Just a heuristic
                
                self.progress_callback(f"   Period: {lookback_start.date()} to {target_date}")
                self.progress_callback(f"   Expected: ~{expected_candles} candles")
                
                # Use DataManager for auto-download capability
                try:
                    logger.info(f"🔄 Requesting data via DataManager (auto-download enabled)...")
                    df = self.data_manager.get_parquet_data(
                        symbol=symbol,
                        timeframe=timeframe,
                        start_date=lookback_start.date(),
                        end_date=target_date_ts.date(),
                        base_dir=ROOT / "artifacts",
                        auto_download=True  # Enable auto-download from EODHD
                    )
                    
                    if df.empty:
                        logger.warning(f"❌ No data for {symbol} (download may have failed)")
                        self.progress_callback(f"  ❌ No data available - skipping")
                        metrics['symbols_failed'] += 1
                        continue
                    
                except Exception as e:
                    logger.error(f"❌ Error loading data for {symbol}: {e}")
                    self.progress_callback(f"  ❌ Error loading data - skipping")
                    metrics['symbols_failed'] += 1
                    continue
                
                fetch_duration = (datetime.now() - fetch_start).total_seconds()
                metrics['data_fetch_time'] += fetch_duration
                
                if df is None or df.empty:
                    logger.warning(f"❌ No data for {symbol} - skipping")
                    self.progress_callback(f"  ❌ No data - skipping")
                    metrics['symbols_failed'] += 1
                    continue
                
                metrics['symbols_processed'] += 1
                
                actual_candles = len(df)
                data_start = df.index[0] if not df.empty else "N/A"
                data_end = df.index[-1] if not df.empty else "N/A"
                
                self.progress_callback(f"✅ Data fetched in {fetch_duration:.2f}s")
                self.progress_callback(f"   Bars: {actual_candles} candles")
                self.progress_callback(f"   Range: {data_start} to {data_end}")
                self.progress_callback(f"   Columns: {list(df.columns)}")
                
                # Verify we have enough data
                if actual_candles < min_candles_needed:
                    self.progress_callback(
                        f"⚠️  WARNING: Only {actual_candles} candles retrieved, "
                        f"need {min_candles_needed} for reliable indicators!"
                    )
            except Exception as e:
                self.progress_callback(f"❌ Error fetching data for {symbol}: {e}")
                continue
            
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
            
            # Run strategy detection WITH lookback-aware data
            # This allows indicators to calculate correctly
            logger.debug(f"  🔍 Running strategy detection...")
            self.progress_callback(f"  🔍 Running strategy...")
            
            strategy_start = datetime.now()
            strategy_signals = self._run_strategy_detection(
                strategy, symbol, df_with_lookback, config_params
            )
            strategy_duration = (datetime.now() - strategy_start).total_seconds()
            metrics['strategy_run_time'] += strategy_duration
            
            logger.info(f"  ✅ Strategy completed in {strategy_duration:.2f}s")
            logger.info(f"     Signals: {len(strategy_signals)}")
            self.progress_callback(f"  ✅ Strategy: {len(strategy_signals)} signals in {strategy_duration:.2f}s")
            
            # STEP 3: Filter signals to ONLY those generated on the target_date
            # We ran detection on full history but only care about today's signals
            filtered_signals = [
                sig for sig in strategy_signals
                if sig.get('detected_at') and 
                pd.to_datetime(sig['detected_at']).date() == target_date_ts_naive.date()
            ]
            
            metrics['signals_generated'] += len(filtered_signals)
            
            logger.info(
                f"  📊 {len(strategy_signals)} total signals, "
                f"{len(filtered_signals)} from target date {target_date}"
            )
            self.progress_callback(
                f"  📊 {len(strategy_signals)} total, "
                f"{len(filtered_signals)} from {target_date}"
            )
            
            all_signals.extend(filtered_signals)
        
        logger.info(f"\n✅ Generated {len(all_signals)} signals total")
        self.progress_callback(f"\n✅ Generated {len(all_signals)} signals total")
        
        # Write signals to database
        if all_signals:
            db_start = datetime.now()
            logger.info(f"💾 Writing {len(all_signals)} signals to database...")
            self.progress_callback(f"💾 Writing signals to database...")
            
            self._write_signals_to_db(all_signals, source="time_machine")
            
            db_duration = (datetime.now() - db_start).total_seconds()
            metrics['db_write_time'] = db_duration
            logger.info(f"✅ Database write completed in {db_duration:.2f}s")
        
        return {
            "status": "completed",
            "signals_generated": len(all_signals),
            "signals": all_signals,
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
