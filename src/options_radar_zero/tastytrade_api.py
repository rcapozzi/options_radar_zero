"""TastyTrade API wrapper.

Provides async access to option chain data and market data from the
TastyTrade API, with optional caching via persist_cache.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from persist_cache import cache
from tastytrade.instruments import NestedOptionChain, Option, get_option_chain
from tastytrade.market_data import MarketData, get_market_data_by_type
from tastytrade.session import Session


class TastyTradeAPI:
    """Wrapper around the TastyTrade async API with caching."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def __getstate__(self) -> dict[str, Any]:
        # copy everything except things with lock such as Session
        state = self.__dict__.copy()
        state.pop("session", None)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        # restore data
        self.__dict__.update(state)
        # recreate a fresh lock
        # (persist_cache manages its own locking internally)

    @cache(expiry=timedelta(hours=12))
    def get_option_chain(self, symbol: str) -> dict[date, list[Option]]:
        """Fetch the option chain for a symbol (cached, 12-hour expiry).

        Returns a dict mapping expiration date → list of Option objects.
        """
        return get_option_chain(self.session, symbol)

    @cache(expiry=timedelta(hours=12))
    async def get_nested_option_chain(self, symbol: str) -> NestedOptionChain:
        """Fetch the nested option chain for a symbol (cached, 12-hour expiry).

        Returns the NestedOptionChain containing strikes with call/put data.
        """
        return (await NestedOptionChain.get(self.session, symbol))[0]

    @cache(expiry=timedelta(hours=12))
    async def get_0dte_option_symbols(self, symbol: str) -> list[str]:
        """Get 0DTE option symbols for a symbol (cached, 12-hour expiry)."""
        noc = await self.get_nested_option_chain(symbol)
        return [
            str(x)
            for strike in noc.expirations[0].strikes
            for x in (strike.call, strike.put)
        ]

    async def get_market_data(
        self,
        kwargs: dict[str, Any],
    ) -> list[MarketData]:
        """Call the market-data endpoint to get real-time trading data.

        Wraps ``get_market_data_by_type`` (which is async) and awaits it
        so callers receive actual ``MarketData`` objects, not coroutines.

        Example::

            quote = await api.get_market_data({"equities": ["SPY"]})[0]
        """
        return await get_market_data_by_type(self.session, **kwargs)

    async def a_get_market_data_batch(
        self,
        cryptocurrencies: list[str] | None = None,
        equities: list[str] | None = None,
        futures: list[str] | None = None,
        future_options: list[str] | None = None,
        indices: list[str] | None = None,
        options: list[str] | None = None,
    ) -> list[MarketData]:
        """Gets market data for the given symbols grouped by instrument type.

        Automatically handles chunking of symbols to respect the API limit
        of 100 symbols per request.
        """
        all_symbols: list[tuple[str, str]] = [
            (sym_type, s)
            for sym_type, symbols in {
                "cryptocurrencies": cryptocurrencies,
                "equities": equities,
                "futures": futures,
                "future_options": future_options,
                "indices": indices,
                "options": options,
            }.items()
            if symbols
            for s in symbols
        ]

        tasks: list[Any] = []
        for i in range(0, len(all_symbols), 100):
            chunk = all_symbols[i : i + 100]
            kwargs: dict[str, list[str]] = defaultdict(list)
            for sym_type, symbol in chunk:
                kwargs[sym_type].append(symbol)
            tasks.append(get_market_data_by_type(self.session, **kwargs))

        results = await asyncio.gather(*tasks)
        return [item for sublist in results for item in sublist]
