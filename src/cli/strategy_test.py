"""CLI for testing trading strategies with real market data."""

import click
import pandas as pd
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import List, Dict, Any
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data import DataManager
from strategies import registry, factory


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def format_results_table(results: Dict[str, Any]) -> str:
    """Format results as a table string."""
    lines = []
    lines.append("=" * 80)
    lines.append(f"{'SYMBOL':<10} {'SIGNALS':<8} {'LONG':<6} {'SHORT':<6} {'SUCCESS':<8} {'DETAILS'}")
    lines.append("-" * 80)
    
    for symbol, data in results.items():
        status = "✅ PASS" if data["success"] else "❌ FAIL"
        details = data.get("error", "OK")[:30] if not data["success"] else "OK"
        
        lines.append(
            f"{symbol:<10} "
            f"{data.get('signal_count', 0):<8} "
            f"{data.get('long_signals', 0):<6} "
            f"{data.get('short_signals', 0):<6} "
            f"{status:<8} "
            f"{details}"
        )
    
    lines.append("-" * 80)
    
    # Summary
    total_symbols = len(results)
    successful = sum(1 for r in results.values() if r["success"])
    total_signals = sum(r.get("signal_count", 0) for r in results.values())
    
    lines.append(f"SUMMARY: {successful}/{total_symbols} symbols successful, {total_signals} total signals")
    lines.append("=" * 80)
    
    return "\n".join(lines)


@click.command()
@click.option(
    "--symbols",
    default="AAPL,TSLA,NVDA,MSFT,PLTR,HOOD",
    help="Comma-separated list of symbols to test",
)
@click.option(
    "--strategy", 
    default="inside_bar_v1", 
    help="Strategy name to test"
)
@click.option(
    "--days", 
    default=60, 
    help="Number of days of historical data to test"
)
@click.option(
    "--atr-period", 
    default=14, 
    help="ATR period for Inside Bar strategy"
)
@click.option(
    "--risk-reward", 
    default=2.0, 
    help="Risk-reward ratio"
)
@click.option(
    "--use-sample-data",
    is_flag=True,
    default=True,
    help="Use sample data instead of real API data",
)
@click.option(
    "--output-file", 
    help="Save detailed results to CSV file"
)
@click.option(
    "--verbose", 
    is_flag=True, 
    help="Enable verbose logging"
)
def main(
    symbols: str,
    strategy: str,
    days: int,
    atr_period: int,
    risk_reward: float,
    use_sample_data: bool,
    output_file: str,
    verbose: bool,
):
    """Test Inside Bar strategy on specified symbols.
    
    Example:
        python -m cli.strategy_test --symbols AAPL,TSLA --days 30 --verbose
    """
    setup_logging(verbose)
    logger = logging.getLogger(__name__)
    
    click.echo("🚀 TradeRunner Strategy Testing CLI")
    click.echo("=" * 50)
    
    # Parse symbols
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    click.echo(f"📊 Testing symbols: {', '.join(symbol_list)}")
    click.echo(f"📈 Strategy: {strategy}")
    click.echo(f"📅 Days: {days}")
    click.echo(f"⚙️  ATR Period: {atr_period}, Risk-Reward: {risk_reward}")
    click.echo(f"🔄 Using sample data: {use_sample_data}")
    click.echo()
    
    # Initialize data manager
    try:
        data_manager = DataManager(cache_enabled=True)
        click.echo("✅ Data manager initialized")
    except Exception as e:
        click.echo(f"❌ Failed to initialize data manager: {e}")
        return 1
    
    # Check if strategy exists
    if strategy not in registry.list_strategies():
        # Try to auto-discover strategies
        logger.info("Auto-discovering strategies...")
        discovered = registry.auto_discover("strategies")
        logger.info(f"Discovered {discovered} strategies")
    
    if strategy not in registry.list_strategies():
        available = registry.list_strategies()
        click.echo(f"❌ Strategy '{strategy}' not found.")
        click.echo(f"Available strategies: {', '.join(available)}")
        return 1
    
    click.echo(f"✅ Strategy '{strategy}' found")
    
    # Prepare configuration
    config = {
        "atr_period": atr_period,
        "risk_reward_ratio": risk_reward,
        "inside_bar_mode": "single",
        "breakout_confirmation": True,
    }
    
    # Test each symbol
    results = {}
    all_signals = []
    
    with click.progressbar(symbol_list, label="Testing symbols") as symbols_progress:
        for symbol in symbols_progress:
            try:
                # Get historical data
                logger.info(f"Fetching data for {symbol}")
                start_date = date.today() - timedelta(days=days)
                end_date = date.today()
                
                data = data_manager.get_historical_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    use_sample_data=use_sample_data,
                )
                
                if data.empty:
                    results[symbol] = {
                        "success": False,
                        "error": "No data available",
                        "signal_count": 0,
                    }
                    continue
                
                logger.info(f"Got {len(data)} rows of data for {symbol}")
                
                # Create strategy instance
                strategy_instance = factory.create_strategy(strategy, config)
                
                # Generate signals
                logger.info(f"Generating signals for {symbol}")
                signals = strategy_instance.generate_signals(data, symbol, config)
                
                # Analyze signals
                long_signals = [s for s in signals if s.signal_type == "LONG"]
                short_signals = [s for s in signals if s.signal_type == "SHORT"]
                
                results[symbol] = {
                    "success": True,
                    "signal_count": len(signals),
                    "long_signals": len(long_signals),
                    "short_signals": len(short_signals),
                    "data_rows": len(data),
                }
                
                # Add symbol to signals for output
                for signal in signals:
                    signal_dict = signal.model_dump()
                    signal_dict["symbol"] = symbol
                    all_signals.append(signal_dict)
                
                logger.info(
                    f"{symbol}: {len(signals)} signals "
                    f"({len(long_signals)} LONG, {len(short_signals)} SHORT)"
                )
                
            except Exception as e:
                logger.error(f"Error testing {symbol}: {e}")
                results[symbol] = {
                    "success": False,
                    "error": str(e)[:50],
                    "signal_count": 0,
                }
    
    # Display results
    click.echo("\n📊 TEST RESULTS")
    click.echo(format_results_table(results))
    
    # Save detailed results if requested
    if output_file and all_signals:
        try:
            signals_df = pd.DataFrame(all_signals)
            signals_df.to_csv(output_file, index=False)
            click.echo(f"💾 Detailed results saved to: {output_file}")
            click.echo(f"📋 Columns: {', '.join(signals_df.columns)}")
        except Exception as e:
            click.echo(f"❌ Failed to save results: {e}")
    
    # Overall summary
    successful_tests = sum(1 for r in results.values() if r["success"])
    total_signals = sum(r.get("signal_count", 0) for r in results.values())
    
    click.echo(f"\n🎯 OVERALL SUMMARY:")
    click.echo(f"   Symbols tested: {len(symbol_list)}")
    click.echo(f"   Successful: {successful_tests}")
    click.echo(f"   Failed: {len(symbol_list) - successful_tests}")
    click.echo(f"   Total signals generated: {total_signals}")
    
    if total_signals > 0:
        click.echo(f"\n✅ Strategy test completed successfully!")
        return 0
    else:
        click.echo(f"\n⚠️  No signals generated. Consider:")
        click.echo(f"   - Adjusting strategy parameters")
        click.echo(f"   - Using a longer time period")
        click.echo(f"   - Checking data quality")
        return 1


if __name__ == "__main__":
    main()