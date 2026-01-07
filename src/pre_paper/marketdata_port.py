"""
MarketData Port Adapter for PrePaper

Wrapper that ensures PrePaper ONLY accesses data via marketdata_service interface.
NO direct DB access, NO direct file reads from axiom_bt/data.

This is the ONLY data access layer PrePaper is allowed to use.
"""

import sys
from pathlib import Path
from typing import Optional, AsyncIterator
from datetime import datetime

# Add marketdata-monorepo to path for import
# TODO: Make this proper package dependency
_MONOREPO_PATH = Path(__file__).parent.parent.parent.parent / "marketdata-monorepo" / "src"
if _MONOREPO_PATH.exists() and str(_MONOREPO_PATH) not in sys.path:
    sys.path.insert(0, str(_MONOREPO_PATH))

try:
    from marketdata_service import (
        MarketDataService,
        FeedRequest,
        BarsRequest,
        FeaturesRequest,
        SignalsWriteRequest,
        SignalsQuery,
        FeedMode,
        MinuteBar,
        Tick,
        SignalRecord,
    )
except ImportError as e:
    raise ImportError(
        f"Cannot import marketdata_service. Ensure marketdata-monorepo is in path. "
        f"Tried: {_MONOREPO_PATH}. Error: {e}"
    )


class PrePaperMarketDataPort:
    """
    Port adapter for PrePaper to access marketdata_service.
    
    Enforces architecture boundary: PrePaper depends ONLY on this port.
    NO direct DB access, NO axiom_bt/data imports allowed.
    """
    
    def __init__(self, service: MarketDataService):
        """
        Args:
            service: MarketDataService implementation (Fake, HTTP, WS, etc.)
        """
        self.service = service
    
    async def get_replay_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "M1",
        session_mode: str = "rth"
    ):
        """
        Get bars for replay mode.
        
        Returns:
            BarsResponse with bars + provenance (data_hash)
        """
        request = BarsRequest(
            symbol=symbol,
            start=start,
            end=end,
            timeframe=timeframe,
            session_mode=session_mode
        )
        
        return await self.service.get_bars(request)
    
    async def ensure_features(
        self,
        symbol: str,
        feature_specs: list,
        start: datetime,
        end: datetime
    ):
        """
        Warmup/compute features (ATR20, etc.).
        
        Returns:
            FeaturesResponse with computed arrays + provenance
        """
        request = FeaturesRequest(
            symbol=symbol,
            features=feature_specs,
            start=start,
            end=end
        )
        
        return await self.service.ensure_features(request)
    
    async def write_signals(
        self,
        lab: str,
        run_id: str,
        source_tag: str,
        signals: list[dict]
    ):
        """
        Write signals (idempotent).
        
        Returns:
            WriteResult (written count, duplicates skipped)
        """
        request = SignalsWriteRequest(
            lab=lab,
            run_id=run_id,
            source_tag=source_tag,
            signals=signals
        )
        
        return await self.service.signals_write(request)
    
    async def query_signals(
        self,
        lab: str,
        run_id: str,
        source_tag: Optional[str] = None
    ) -> list[SignalRecord]:
        """
        Query signals for a run (stable ordering).
        
        Returns:
            List of SignalRecord
        """
        query = SignalsQuery(
            lab=lab,
            run_id=run_id,
            source_tag=source_tag
        )
        
        return await self.service.signals_query(query)
    
    async def open_feed(
        self,
        symbols: list[str],
        mode: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        timeframe: str = "M1",
        session_mode: str = "rth"
    ) -> AsyncIterator[Tick | MinuteBar]:
        """
        Open streaming feed (replay or live).
        
        Yields:
            Tick or MinuteBar events
        """
        feed_mode = FeedMode.REPLAY if mode == "replay" else FeedMode.LIVE
        
        request = FeedRequest(
            symbols=symbols,
            mode=feed_mode,
            start=start,
            end=end,
            timeframe=timeframe,
            session_mode=session_mode
        )
        
        feed_handle = await self.service.open_feed(request)
        
        async for event in feed_handle:
            yield event
        
        await feed_handle.close()
