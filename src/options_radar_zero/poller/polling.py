"""Async polling loop for 0DTE option chain market data."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import pytz

from options_radar_zero.market_hours import MarketIntervalCalculator
from options_radar_zero.poller.config import PollerConfig
from options_radar_zero.poller.dataframe import (
    create_dataframe_from_market_data,
    merge_save_df,
)

logger = logging.getLogger(__name__)


async def _poll_single_symbol(
    symbol: str,
    strikes: int,
    filename: str,
    api: Any,
    market_interval_calculator: MarketIntervalCalculator,
) -> None:
    """Poll option chain data for a single symbol during market hours."""
    from options_radar_zero.poller.chain import OptionChainSelector

    market_close_dt = market_interval_calculator.get_market_close()
    chain_selector = OptionChainSelector(api)
    chain_selection = await chain_selector.fetch_chain(symbol, strikes)
    if chain_selection is None:
        return

    expiration_date = chain_selection.expiration_date
    sym2strike = chain_selection.sym2strike
    option_symbols = chain_selection.option_symbols

    df: pd.DataFrame | None = None
    while True:
        now = datetime.now(market_close_dt.tzinfo)
        if now >= market_close_dt:
            break

        try:
            quote_list = await api.get_market_data({"equities": [symbol]})
            if not quote_list:
                logger.warning("Could not get quote for underlying %s", symbol)
                await asyncio.sleep(60)
                continue

            quote = quote_list[0]
            underlying_price: Decimal = quote.last
            md = await api.a_get_market_data_batch(options=option_symbols)
            created_at = datetime.now(pytz.utc)
            df_new = create_dataframe_from_market_data(
                md,
                underlying_price,
                created_at,
                expiration_date,
                sym2strike,
            )
            df = merge_save_df(df, df_new, filename)

        except Exception as e:
            logger.error("Error polling market data for %s: %s", symbol, e, exc_info=True)

        # Sleep until the next update time (aligned to top of minute)
        next_update_time = market_interval_calculator.get_next_update_time()
        now_in_market_tz = datetime.now(next_update_time.tzinfo)
        next_interval = (next_update_time - now_in_market_tz).total_seconds()
        next_interval = max(1, next_interval)

        logger.info("Sleeping %d seconds until %s.", int(next_interval), next_update_time)
        await asyncio.sleep(next_interval)

    logger.info("Market is closed. Stopping polling for %s.", symbol)


async def _end_of_day_catchup(
    symbol: str,
    strikes: int,
    filename: str,
    api: Any,
    market_interval_calculator: MarketIntervalCalculator,
) -> None:
    """Perform an end-of-day catch-up poll for a single symbol.

    Fetches fresh market data for all option symbols and merges it into
    the existing parquet file, filling any gaps from the live polling
    session.
    """
    from options_radar_zero.poller.chain import OptionChainSelector

    chain_selector = OptionChainSelector(api)
    chain_selection = await chain_selector.fetch_chain(symbol, strikes)
    if chain_selection is None:
        logger.info("No chain data for %s. Skipping end-of-day catch-up.", symbol)
        return

    expiration_date = chain_selection.expiration_date
    sym2strike = chain_selection.sym2strike
    option_symbols = chain_selection.option_symbols

    try:
        quote_list = await api.get_market_data({"equities": [symbol]})
        if not quote_list:
            logger.warning("Could not get quote for underlying %s", symbol)
            return

        quote = quote_list[0]
        underlying_price: Decimal = quote.last
        md = await api.a_get_market_data_batch(options=option_symbols)
        created_at = datetime.now(pytz.utc)
        df_new = create_dataframe_from_market_data(
            md,
            underlying_price,
            created_at,
            expiration_date,
            sym2strike,
        )
        # Load existing df from file (merge_save_df handles dedup)
        df: pd.DataFrame | None = None
        if os.path.exists(filename):
            df = pd.read_parquet(filename)
        df = merge_save_df(df, df_new, filename)
        logger.info("End-of-day catch-up complete for %s.", symbol)
    except Exception as e:
        logger.error("End-of-day catch-up failed for %s: %s", symbol, e, exc_info=True)


async def poll_symbols(
    config: PollerConfig,
    api: Any,
    market_interval_calculator: MarketIntervalCalculator,
    run_eod: bool = False,
) -> None:
    """Poll market data for all symbols in the config concurrently.

    If the market is currently open, polls in a loop until close.
    If the market is closed and ``run_eod`` is True, performs an
    end-of-day catch-up for each symbol (fills gaps in existing
    parquet files).

    Args:
        config: Poller configuration with symbols and output settings.
        api: A TastyTradeAPI instance.
        market_interval_calculator: A MarketIntervalCalculator instance.
        run_eod: If True, perform end-of-day catch-up when market is closed.
    """
    if market_interval_calculator.is_market_open():
        tasks = [
            _poll_single_symbol(
                sym_cfg.symbol,
                sym_cfg.strikes,
                config.filename_for(sym_cfg.symbol),
                api,
                market_interval_calculator,
            )
            for sym_cfg in config.symbols
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
    else:
        # Check if market is open later today (pre-market: after 9am, before 9:30am)
        now = datetime.now(market_interval_calculator._market_tz)
        schedule_today = market_interval_calculator._get_market_schedule_for_date(now.date())
        if schedule_today is not None and not schedule_today.empty:
            market_open = schedule_today.iloc[0]['market_open'].astimezone(market_interval_calculator._market_tz)
            if now < market_open:
                # Pre-market: sleep until market open, then start polling
                sleep_seconds = (market_open - now).total_seconds()
                logger.info(
                    "Market not open yet. Sleeping %.0f seconds until %s.",
                    sleep_seconds, market_open,
                )
                await asyncio.sleep(sleep_seconds)
                # Now start polling
                tasks = [
                    _poll_single_symbol(
                        sym_cfg.symbol,
                        sym_cfg.strikes,
                        config.filename_for(sym_cfg.symbol),
                        api,
                        market_interval_calculator,
                    )
                    for sym_cfg in config.symbols
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                return

        if run_eod:
            # End-of-day catch-up: use last trade date for filenames
            last_trade_date = market_interval_calculator.get_last_trade_date()
            date_label = last_trade_date.strftime("%Y-%m-%d") if last_trade_date else "unknown"
            logger.info(
                "Market is closed. Performing end-of-day catch-up for %s (last trade: %s).",
                ", ".join(config.all_symbols),
                date_label,
            )
            tasks = [
                _end_of_day_catchup(
                    sym_cfg.symbol,
                    sym_cfg.strikes,
                    config.filename_for(sym_cfg.symbol, trade_date=last_trade_date),
                    api,
                    market_interval_calculator,
                )
                for sym_cfg in config.symbols
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("End-of-day catch-up complete.")
        else:
            logger.info("Market is closed. Exiting (no --eod flag).")
