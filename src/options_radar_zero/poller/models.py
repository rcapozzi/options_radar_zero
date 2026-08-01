"""Data models for option chain metadata and market data rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import pytz
from tastytrade.market_data import MarketData


@dataclass(frozen=True)
class StrikeInfo:
    """Metadata for a single call or put option at a given strike.

    Attributes:
        symbol: The option symbol (e.g., call or put symbol).
        streamer_symbol: The streamer symbol for real-time data.
        type: Either 'CALL' or 'PUT'.
        strike_price: The strike price as a Decimal.
    """

    symbol: str
    streamer_symbol: str
    type: str
    strike_price: Decimal


@dataclass(frozen=True)
class OptionRow:
    """A single row of market data for an option.

    Attributes:
        last_trade_at: Timestamp of the last trade.
        created_at: Timestamp when the data was fetched.
        symbol: The streamer symbol for the option.
        put_call: 'CALL' or 'PUT'.
        strike: The strike price.
        bid: Bid price.
        ask: Ask price.
        price: Last trade price.
        open_interest: Open interest.
        delta: Delta (default 0).
        day_volume: Trading volume for the day.
        underlying_price: Current underlying price.
        expiration_date: Expiration date of the option.
    """

    last_trade_at: datetime
    created_at: datetime
    symbol: str
    put_call: str
    strike: Decimal
    bid: Decimal | None
    ask: Decimal | None
    price: Decimal | None
    open_interest: Decimal | None
    delta: int
    day_volume: Decimal | None
    underlying_price: Decimal
    expiration_date: date

    @classmethod
    def from_market_data(
        cls,
        md: MarketData,
        underlying_price: Decimal,
        created_at: datetime,
        expiration_date: date,
        strike_info: StrikeInfo,
    ) -> OptionRow:
        """Build an OptionRow from a MarketData object and strike metadata.

        Args:
            md: The MarketData object from TastyTrade.
            underlying_price: Current underlying price as Decimal.
            created_at: Timestamp when the data was fetched.
            expiration_date: Expiration date of the option.
            strike_info: Strike metadata (symbol, type, strike_price, streamer_symbol).

        Returns:
            A populated OptionRow instance.
        """
        return cls(
            last_trade_at=md.updated_at,
            created_at=created_at,
            symbol=strike_info.streamer_symbol,
            put_call=strike_info.type,
            strike=strike_info.strike_price,
            bid=md.bid,
            ask=md.ask,
            price=md.last,
            open_interest=md.open_interest,
            delta=0,
            day_volume=md.volume,
            underlying_price=underlying_price,
            expiration_date=expiration_date,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary suitable for DataFrame construction."""
        return {
            "last_trade_at": pd.to_datetime(self.last_trade_at, utc=True),
            "created_at": self.created_at,
            "symbol": self.symbol,
            "putCall": self.put_call,
            "strike": self.strike,
            "bid": self.bid,
            "ask": self.ask,
            "price": self.price,
            "open_interest": self.open_interest,
            "delta": self.delta,
            "day_volume": self.day_volume,
            "underlying_price": self.underlying_price,
            "expiration_date": self.expiration_date,
        }


def to_utc(dt: datetime) -> datetime:
    """Convert a datetime to UTC, or return as-is if already naive.

    Args:
        dt: A datetime, possibly timezone-aware.

    Returns:
        A timezone-aware datetime in UTC.
    """
    if dt.tzinfo is None:
        return pytz.utc.localize(dt)
    return dt.astimezone(pytz.utc)
