# Helper function for source names
def _get_source_name(timeframe: str) -> str:
    """Get human-readable source name for timeframe."""
    if timeframe in ['M1', 'M5', 'M15']:
        return "IntradayStore"
    elif timeframe == 'D1':
        return "Universe"
    elif timeframe == 'H1':
        return "Resample(M5)"
    else:
        return "Unknown"
