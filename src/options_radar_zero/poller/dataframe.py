"""DataFrame construction and persistence utilities for market data."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from tastytrade.market_data import MarketData

from options_radar_zero.poller.models import StrikeInfo

logger = logging.getLogger(__name__)


def create_dataframe_from_market_data(
    market_data: list[MarketData],
    underlying_price: Decimal,
    created_at: datetime,
    expiration_date: date,
    sym2strike: dict[str, StrikeInfo],
) -> pd.DataFrame:
    """Create a Pandas DataFrame from a list of MarketData objects.

    Args:
        market_data: List of MarketData objects from TastyTrade.
        underlying_price: Current underlying price as Decimal.
        created_at: Timestamp when the data was fetched.
        expiration_date: Expiration date of the options.
        sym2strike: Mapping of symbol to StrikeInfo metadata.

    Returns:
        DataFrame with market data rows.
    """
    data: list[dict[str, Any]] = []
    for md in market_data:
        strike_info = sym2strike[md.symbol]
        row = {
            "last_trade_at": pd.to_datetime(md.updated_at, utc=True),
            "created_at": created_at,
            "symbol": strike_info.streamer_symbol,
            "putCall": strike_info.type,
            "strike": strike_info.strike_price,
            "bid": md.bid,
            "ask": md.ask,
            "price": md.last,
            "open_interest": md.open_interest,
            "delta": 0,
            "day_volume": md.volume,
            "underlying_price": underlying_price,
            "expiration_date": expiration_date,
        }
        data.append(row)
    return pd.DataFrame(data)


def merge_save_df(
    df: pd.DataFrame | None,
    df_new: pd.DataFrame | None,
    filename: str,
) -> pd.DataFrame:
    """Merge two dataframes and save the result to a parquet file.

    Args:
        df: Existing DataFrame (may be None if no prior data).
        df_new: New DataFrame to merge in.
        filename: Path to the parquet file.

    Returns:
        The merged DataFrame.
    """
    if df_new is None or df_new.empty:
        return df if df is not None else pd.DataFrame()

    if df is None:
        if os.path.exists(filename):
            df = pd.read_parquet(filename)
        else:
            logger.info("Creating new file: %s", filename)
            df_new.to_parquet(filename)
            return df_new

    combined_df = pd.concat([df, df_new], ignore_index=True)
    combined_df.drop_duplicates(
        subset=["symbol", "last_trade_at"],
        keep="last",
        inplace=True,
    )

    if len(combined_df) > len(df):
        combined_df.to_parquet(filename)
        logger.info("Clobbered %s len=%d", filename, len(combined_df))
        return combined_df
    else:
        logger.info("No new trade data to save to %s", filename)
        return df
