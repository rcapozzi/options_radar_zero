"""Option chain selection and strike filtering around the money."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from tastytrade.instruments import NestedOptionChain, Strike

from options_radar_zero.poller.models import StrikeInfo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChainSelection:
    """Result of selecting strikes from an option chain.

    Attributes:
        expiration_date: The expiration date of the selected options.
        sym2strike: Mapping of option symbol to StrikeInfo metadata.
        option_symbols: List of option symbols to monitor.
    """

    expiration_date: date
    sym2strike: dict[str, StrikeInfo]
    option_symbols: list[str]


class OptionChainSelector:
    """Encapsulates fetching an option chain and selecting strikes around the money.

    This class fetches the nested option chain for a symbol, builds a symbol-to-strike
    metadata mapping, and selects a window of strikes centered on the current
    underlying price.
    """

    def __init__(self, api: Any) -> None:
        """Initialize the selector with a TastyTradeAPI instance.

        Args:
            api: A TastyTradeAPI instance with get_market_data and get_nested_option_chain methods.
        """
        self._api = api

    async def get_underlying_price(self, symbol: str) -> Decimal | None:
        """Fetch the current underlying price for a symbol.

        Args:
            symbol: The underlying symbol (e.g., 'SPY').

        Returns:
            The last price as a Decimal, or None if unavailable.
        """
        quote_list = self._api.get_market_data({"equities": [symbol]})
        if not quote_list:
            logger.error("Could not get initial quote for underlying %s", symbol)
            return None
        return quote_list[0].last  # type: ignore[no-any-return]

    async def fetch_chain(
        self,
        symbol: str,
        num_strikes: int,
    ) -> ChainSelection | None:
        """Fetch the option chain and select strikes around the money.

        Args:
            symbol: The underlying symbol to fetch the chain for.
            num_strikes: Number of strikes to fetch around the money.

        Returns:
            A ChainSelection containing the expiration date, sym2strike mapping,
            and selected option symbols. Returns None if the chain cannot be fetched.
        """
        noc: NestedOptionChain = await self._api.get_nested_option_chain(symbol)
        if not noc.expirations:
            logger.error("No expirations found for %s", symbol)
            return None

        exp = noc.expirations[0]
        expiration_date = exp.expiration_date

        sym2strike = self._build_sym2strike(exp.strikes)
        all_strikes = sorted(exp.strikes, key=lambda s: s.strike_price)

        underlying_price = await self.get_underlying_price(symbol)
        if underlying_price is None:
            return None

        selected_strikes = self._select_strikes_around_money(all_strikes, underlying_price, num_strikes)
        option_symbols = [s.call for s in selected_strikes] + [s.put for s in selected_strikes]

        logger.info("Monitoring %d option symbols.", len(option_symbols))

        return ChainSelection(
            expiration_date=expiration_date,
            sym2strike=sym2strike,
            option_symbols=option_symbols,
        )

    @staticmethod
    def _build_sym2strike(strikes: list[Strike]) -> dict[str, StrikeInfo]:
        """Build a mapping of option symbol to StrikeInfo from a list of strikes."""
        sym2strike: dict[str, StrikeInfo] = {}
        for s in strikes:
            sym2strike[s.call] = StrikeInfo(
                symbol=s.call,
                streamer_symbol=s.call_streamer_symbol,
                type="CALL",
                strike_price=s.strike_price,
            )
            sym2strike[s.put] = StrikeInfo(
                symbol=s.put,
                streamer_symbol=s.put_streamer_symbol,
                type="PUT",
                strike_price=s.strike_price,
            )
        return sym2strike

    @staticmethod
    def _select_strikes_around_money(
        strikes: list[Strike],
        underlying_price: Decimal,
        num_strikes: int,
    ) -> list[Strike]:
        """Select a window of strikes centered on the underlying price.

        Args:
            strikes: All strikes sorted by strike_price.
            underlying_price: Current underlying price.
            num_strikes: Number of strikes to select on each side.

        Returns:
            A sublist of strikes centered around the money.
        """
        mid_index = min(
            range(len(strikes)),
            key=lambda i: abs(strikes[i].strike_price - underlying_price),
        )
        half = num_strikes // 2
        start = max(0, mid_index - half)
        end = min(len(strikes), mid_index + half)
        return strikes[start:end]
