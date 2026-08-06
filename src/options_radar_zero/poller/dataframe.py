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

# Legacy column aliases — normalize old-format parquet files when merging
_LEGACY_ALIASES: dict[str, str] = {
    "last_trade_at": "processDateTime",
    "strike": "strikePrice",
    "price": "mark",
    "day_volume": "totalVolume",
    "underlying_price": "underlyingPrice",
    "open_interest": "openInterest",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename legacy column names to the current canonical format."""
    for old_name, new_name in _LEGACY_ALIASES.items():
        if old_name in df.columns and new_name not in df.columns:
            df.rename(columns={old_name: new_name}, inplace=True)
    return df


def create_dataframe_from_market_data(
    market_data: list[MarketData],
    underlying_price: Decimal,
    created_at: datetime,
    expiration_date: date,
    sym2strike: dict[str, StrikeInfo],
) -> pd.DataFrame:
    """Create a Pandas DataFrame from a list of MarketData objects.

    The column names are designed to match the dashboard's
    ``transform_option_data`` function and historical data format.

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
        row: dict[str, Any] = {
            "processDateTime": pd.to_datetime(md.updated_at, utc=True),
            "symbol": strike_info.streamer_symbol,
            "putCall": strike_info.type,
            "strikePrice": float(strike_info.strike_price),
            "bid": float(md.bid) if md.bid is not None else 0.0,
            "ask": float(md.ask) if md.ask is not None else 0.0,
            "mark": float(md.mark) if md.mark is not None else (
                float(md.last) if md.last is not None else 0.0
            ),
            "totalVolume": float(md.volume) if md.volume else 0.0,
            "openInterest": float(md.open_interest) if md.open_interest else 0.0,
            "underlyingPrice": float(underlying_price),
            "processDate": created_at.strftime("%Y-%m-%d"),
        }
        data.append(row)
    return pd.DataFrame(data)


def merge_save_df(
    df: pd.DataFrame | None,
    df_new: pd.DataFrame | None,
    filename: str,
) -> pd.DataFrame:
    """Merge two dataframes and save the result to a parquet file.

    Normalizes legacy column names from existing parquet files so they
    can be merged with new-format data.

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
            df = _normalize_columns(pd.read_parquet(filename))
        else:
            logger.info("Creating new file: %s", filename)
            df_new.to_parquet(filename)
            return df_new

    combined_df = pd.concat([df, df_new], ignore_index=True)
    combined_df.drop_duplicates(
        subset=["symbol", "processDateTime"],
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
