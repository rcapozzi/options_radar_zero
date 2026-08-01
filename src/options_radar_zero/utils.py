"""OptionQuotes data class for loading and caching option chain data.

This module has been slimmed down — EasternDT and MarketIntervalCalculator
have been moved to market_hours.py. The thinkscript generation has been
moved to thinkscript.py.
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd

from options_radar_zero.data_processing import transform_option_data


class OptionQuotes:
    """Loads, caches, and provides access to option chain data from parquet files.

    The heavy data transformation logic has been extracted into the pure function
    ``transform_option_data`` in ``data_processing.py``. This class wraps file I/O
    and caching only.
    """

    CALL: str = 'CALL'
    PUT: str = 'PUT'

    def __init__(self, symbol: str, filename: str | None = None) -> None:
        self.cache: dict[str, Any] = {}
        self.symbol: str = symbol
        if filename:
            self.filename: str = filename
        else:
            self.filename = f'data/{symbol}.2023-05-04.parquet'
        self.last_mtime: float = 0
        self.data: pd.DataFrame | None = None
        self.max_dt: pd.Timestamp | None = None
        self._pivot: pd.DataFrame | None = None

    def pivot(self) -> pd.DataFrame:
        """Return a pivoted view of the data (cached)."""
        if self._pivot is None:
            self._pivot = pd.pivot(
                self.data,  # type: ignore[arg-type]
                index=['putCall', 'processDateTime'],
                columns=['strikePrice'],
                values=['mark', 'volume', 'delta'],
            )
        return self._pivot

    def pivot_for(self, putCall: str, time: Any, value: str) -> pd.DataFrame:
        """Return pivoted data for a specific put/call, time, and value."""
        if time is None:
            time = pd.Timestamp.now().floor(freq='min')
        s = self.pivot().loc[(putCall, time), (value, slice(None))]
        return s.reset_index(name=value).drop(columns=['level_0'])  # type: ignore[no-any-return, call-overload]

    def underlying_history(self) -> pd.Series:
        """Return the mean underlying price by processDateTime."""
        return self.data.groupby(['processDateTime']).underlyingPrice.mean()  # type: ignore[union-attr]

    def reload(self, force: bool = False) -> pd.DataFrame:
        """Reload data from parquet file if mtime has changed.

        Args:
            force: If True, force reload even if mtime hasn't changed.

        Returns:
            The loaded and transformed DataFrame.
        """
        mtime = os.path.getmtime(self.filename)
        if force or (mtime > self.last_mtime):
            self.last_mtime = mtime
            raw_df = pd.read_parquet(self.filename)
            self.data = transform_option_data(raw_df)
            self.cache = {}
            self.max_dt = self.data.processDateTime.max()
            self.cache_set('max_dt', self.max_dt)
        self._pivot = None
        return self.data  # type: ignore[return-value]

    def cache_set(self, key: str, value: Any) -> Any:
        """Store a value in the cache."""
        self.cache[key] = value
        return value

    def cache_get(self, key: str) -> Any | None:
        """Retrieve a value from the cache."""
        return self.cache.get(key, None)

    def calc_spreads(self, df: pd.DataFrame, distance: int) -> pd.DataFrame:
        """Given a list of [strikePrice, mark], return prices for spreads."""
        prices = df.dropna()
        spreads = df.dropna()

        spreads = spreads.rename(columns={'strikePrice': 'shortStrike', 'mark': 'shortPrice'})
        spreads['longStrike'] = spreads.shortStrike + distance
        spreads['distance'] = distance
        spreads['putCall'] = OptionQuotes.CALL

        spreads = pd.merge(spreads, prices, left_on='longStrike', right_on='strikePrice')
        spreads = spreads.rename(columns={'mark': 'longPrice'})
        spreads['price'] = round(spreads.shortPrice - spreads.longPrice, 2)
        spreads.drop(columns=['shortPrice', 'longPrice', 'strikePrice'], inplace=True)
        if spreads['price'].min() < 0 and spreads['price'].max() <= 0.0:
            spreads.rename(columns={'shortStrike': 'longStrike', 'longStrike': 'shortStrike'}, inplace=True)
            spreads['price'] = -spreads['price']
            spreads['putCall'] = OptionQuotes.PUT

        return spreads[spreads['price'] > 0.05]

    def find_spread(self, now: Any, opts: dict[str, Any]) -> dict[str, Any]:
        """Find the best spread matching the given options.

        Args:
            now: Current datetime.
            opts: Dict with putCall, distance, creditMin, creditTarget.

        Returns:
            Dict with the matched spread details.
        """
        df = self.pivot_for(opts['putCall'], now, 'mark')
        df = self.calc_spreads(df, opts['distance'])
        df['creditDiff'] = round(abs(opts['creditTarget'] - df['price']), 2)
        df = df[(df['price'] >= opts['creditMin'])]
        spread = df.sort_values('creditDiff').iloc[0]
        resp = opts.copy()
        resp.update(spread.to_dict())
        resp['open_dt'] = now
        return resp
