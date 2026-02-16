"""
SessionFilter Debug Wrapper - File-based logging for session filter decisions.

This wrapper logs ALL session filter checks to run_dir/session_filter_debug.txt
"""
from pathlib import Path
from typing import Optional
import pandas as pd
from strategies.confirmed_breakout.config import SessionFilter


class SessionFilterDebugger:
    """Wrapper around SessionFilter that logs all decisions to a file."""

    def __init__(self, session_filter: SessionFilter, debug_file: Path):
        self.filter = session_filter
        self.debug_file = Path(debug_file)
        self.call_count = 0

        # Initialize debug file
        with open(self.debug_file, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("SESSION FILTER DEBUG TRACE\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Windows: {self.filter.to_strings() if hasattr(self.filter, 'to_strings') else 'empty'}\n")
            f.write(f"Window count: {len(self.filter.windows) if self.filter else 0}\n\n")

    def is_in_session(self, timestamp: pd.Timestamp, tz: str = "Europe/Berlin") -> bool:
        """Check if timestamp is in session and log the decision."""
        self.call_count += 1

        # Call the real filter
        try:
            result = self.filter.is_in_session(timestamp, tz)
        except Exception as e:
            # Log error
            with open(self.debug_file, 'a') as f:
                f.write(f"\n[CALL #{self.call_count}] ERROR\n")
                f.write(f"  Timestamp: {timestamp}\n")
                f.write(f"  TZ param: {tz}\n")
                f.write(f"  Error: {e}\n")
            raise

        # Log the call and result
        with open(self.debug_file, 'a') as f:
            f.write(f"\n[CALL #{self.call_count}] {'✅ IN SESSION' if result else '❌ OUT OF SESSION'}\n")
            f.write(f"  Input timestamp: {timestamp}\n")
            f.write(f"  Input tz: {timestamp.tz}\n")
            f.write(f"  Target tz: {tz}\n")

            if timestamp.tz:
                ts_local = timestamp.tz_convert(tz)
                f.write(f"  Converted to {tz}: {ts_local}\n")
                f.write(f"  Time: {ts_local.time()}\n")
            else:
                f.write(f"  WARNING: Timestamp has no timezone!\n")

            f.write(f"  Windows: {self.filter.windows}\n")
            f.write(f"  Result: {result}\n")

        return result

    def to_strings(self):
        """Pass through to wrapped filter."""
        return self.filter.to_strings() if hasattr(self.filter, 'to_strings') else []
