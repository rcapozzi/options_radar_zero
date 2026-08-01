"""Data processing module - pure functions for data transformation."""
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from options_radar_zero.config import config


def filter_dataframe_by_strikes(
    df: pd.DataFrame,
    min_strike: float,
    max_strike: float
) -> pd.DataFrame:
    """Filter dataframe by strike price range."""
    return df[(df['strikePrice'] >= min_strike) & (df['strikePrice'] <= max_strike)]


def filter_dataframe_by_volume(
    df: pd.DataFrame,
    min_volume: int | None = None
) -> pd.DataFrame:
    """Filter dataframe to only include rows above volume threshold."""
    if min_volume is None:
        min_volume = config.MIN_VOLUME_THRESHOLD
    return df.loc[(df.totalVolume > min_volume)]


def calculate_strike_range(
    df: pd.DataFrame
) -> tuple[int, int, int, int, int, int]:
    """Calculate strike price range with appropriate step size.

    Returns:
        Tuple of (min_strike, max_strike, step_size, price_min, price_max, price_range)
    """
    min_strike = int(df.strikePrice.min())
    max_strike = int(df.strikePrice.max())
    price_min = int(df.underlyingPrice.min())
    price_max = int(df.underlyingPrice.max())

    price_range = price_max - price_min

    if price_range > 10 or price_max > 1000:
        step_size = 25
        min_strike = int(np.floor(min_strike / step_size) * step_size)
        max_strike = int(np.floor(max_strike / step_size) * step_size)
        price_min = int(np.floor(price_min / step_size) * step_size)
        price_max = int(np.ceil(price_max / step_size) * step_size)
    else:
        step_size = 1

    return min_strike, max_strike, step_size, price_min, price_max, price_range


def prepare_chart_data(
    df: pd.DataFrame,
    xaxis: str,
    yaxis: str,
    strikes: tuple[float, float]
) -> pd.DataFrame:
    """Prepare dataframe for charting.

    Applies transformations for volume signs, sorting, and filtering.
    """
    data = df[(df.strikePrice >= strikes[0]) & (df.strikePrice <= strikes[1])].copy()

    if xaxis == 'processDateTime':
        # Remove timezone for plotting
        data['x'] = data[xaxis].dt.tz_localize(tz=None)

    if yaxis == 'volume':
        data['sign'] = np.where(
            data['volume'] < 50,
            np.nan,
            np.where(data['putCall'] == 'CALL', 1, -1)
        )
    else:
        data['sign'] = np.where(data['putCall'] == 'CALL', 1, -1)

    data = data.sort_values(['symbol', 'processDateTime'])
    return data


def calculate_strike_volume_data(
    df: pd.DataFrame,
    max_datetime: datetime
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Calculate strike volume data for charts.

    Returns:
        Tuple of (calls_df, puts_df, underlying_price)
    """
    data = df.copy()
    data['sma5'] = data.volume.rolling(5).mean().round(2)
    data['sma15'] = data.volume.rolling(15).mean().round(2)
    data['gexTV'] = (data['totalVolume'] * data.gamma).abs()

    mask = data['putCall'] == 'CALL'
    data.loc[mask, 'totalVolume'] *= -1
    data.loc[mask, 'volume'] *= -1
    data.loc[mask, 'sma5'] *= -1
    data.loc[mask, 'sma15'] *= -1

    data_filtered = data[(data.processDateTime == max_datetime)]
    underlying_price = int(data_filtered.underlyingPrice.abs().max())

    puts = data_filtered[(data_filtered.putCall == 'PUT')].copy()
    calls = data_filtered[(data_filtered.putCall == 'CALL')].copy()

    return calls, puts, underlying_price


def calculate_gex_metrics(df: pd.DataFrame) -> tuple[float, float, float]:
    """Calculate gamma exposure metrics.

    Returns:
        Tuple of (put_gex_price, call_gex_price, net_gex_price)
    """
    puts = df.loc[(df.putCall == 'PUT')]
    calls = df.loc[(df.putCall == 'CALL')]

    put_gex_sum = float(puts.gex.sum())
    put_strike_sum = float(puts.strikePrice.sum()) if len(puts) > 0 else 0.0
    call_gex_sum = float(calls.gex.sum())
    call_strike_sum = float(calls.strikePrice.sum()) if len(calls) > 0 else 0.0

    put_gex_price = float((puts.gex * puts.strikePrice).sum() / put_gex_sum) if put_gex_sum != 0 else 0.0
    put_gex_weight = float((puts.gex * puts.strikePrice).sum() / put_strike_sum) if put_strike_sum != 0 else 0.0
    call_gex_price = float((calls.gex * calls.strikePrice).sum() / call_gex_sum) if call_gex_sum != 0 else 0.0
    call_gex_weight = float((calls.gex * calls.strikePrice).sum() / call_strike_sum) if call_strike_sum != 0 else 0.0

    if (call_gex_weight + put_gex_weight) == 0:
        return 0.0, 0.0, 0.0

    net_gex_price = (
        (call_gex_price * call_gex_weight) + (put_gex_price * put_gex_weight)
    ) / (call_gex_weight + put_gex_weight)

    return float(put_gex_price), float(call_gex_price), float(net_gex_price)


def get_metric_content(df: pd.DataFrame, symbol: str, max_datetime: datetime) -> list[dict[str, Any]]:
    """Generate metric content for display.

    Returns:
        List of metric dictionaries for the UI.
    """
    style_metrics = {'padding': '5px', 'fontsize:': '10px'}

    metrics = [
        f"{max_datetime.strftime('%Y-%m-%d %H:%M:%S')}",
        f"{symbol} Last: {float(df[df.processDateTime == max_datetime].underlyingPrice.min())}",
        f"Range: {float(df.underlyingPrice.min())}/{float(df.underlyingPrice.max())}",
        f"Strikes: {float(df.strikePrice.min())}/{float(df.strikePrice.max())}",
    ]

    return [{'text': m, 'style': style_metrics} for m in metrics]


def transform_option_data(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all derived calculations and filtering to an options DataFrame.

    This is the pure-function replacement for OptionQuotes.post_load_data().
    It does not mutate the input DataFrame — callers should assign the result.

    Args:
        df: Raw options DataFrame with columns like strikePrice, processDateTime,
            putCall, totalVolume, mark, gamma, underlyingPrice, etc.

    Returns:
        Transformed DataFrame with derived columns (volume, gex, distance, etc.)
        and low-volume/ RTH-filtered rows.
    """
    df = df.copy()

    # Fix negative values in volatility columns by replacing with row 1's value
    for field in ['volatility', 'delta', 'gamma', 'theta']:
        if field in df.columns:
            df.loc[(df[field] < 0), field] = df.iloc[1][field]

    df.sort_values(['symbol', 'processDateTime'], inplace=True)
    gb = df.groupby('symbol')
    df['volume'] = gb['totalVolume'].diff().fillna(0)
    df['markDiff'] = gb['mark'].diff().fillna(0).round(4)
    df['markPctChange'] = gb['mark'].pct_change().fillna(0)
    df['underlyingPriceDiff'] = gb['underlyingPrice'].diff().fillna(2)

    df['upDown'] = np.sign(gb['mark'].diff())
    for i in range(2, 10):
        df.loc[(df.upDown == 0) & (df.mark > 0.19), 'upDown'] = np.sign(gb['mark'].diff(i))
    df['volumeUpDown'] = df['upDown'] * df['volume']

    df.loc[(df.markDiff == 0), 'volumeUpDown'] = np.sign(df['underlyingPriceDiff']) * df['volume']

    df['volumeUpDownCum'] = df.groupby('symbol').volumeUpDown.cumsum()
    df['openInterestNet'] = df.openInterest + df['volumeUpDownCum']
    df['gex'] = df['openInterestNet'] * df.gamma

    df['underlyingPrice'] = df.underlyingPrice.round(0)
    df['distance'] = (df['strikePrice'] - df['underlyingPrice']).apply(lambda x: round(x / 10) * 10)

    df = filter_low_volume(df, config.LOW_VOLUME_FILTER_MIN)
    df = filter_rth(df)

    df.fillna(0, inplace=True)

    drops = [
        'tradeTimeInLong', 'quoteTimeInLong', 'netChange', 'rho', 'vega',
        'bid', 'ask', 'highPrice', 'lowPrice', 'openPrice', 'closePrice',
        'expirationDate', 'lastTradingDay', 'multiplier',
        'timeValue', 'theoreticalOptionValue', 'theoreticalVolatility',
        'percentChange', 'markChange', 'markPercentChange', 'intrinsicValue',
        'upDown', 'volumeUpDown', 'volumeUpDownCum',
    ]
    df.drop([x for x in drops if x in df.columns], inplace=True, axis=1)

    return df


def filter_rth(df: pd.DataFrame) -> pd.DataFrame:
    """Filter the dataframe to remove rows before 9:30am or after 4:00pm ET."""
    time = df.processDateTime.dt.time
    return df[(time >= pd.to_datetime('09:30:00').time()) & (time <= pd.to_datetime('16:00:00').time())]  # type: ignore[no-any-return]


def filter_low_volume(df: pd.DataFrame, min_volume: int) -> pd.DataFrame:
    """Filter out symbols whose max totalVolume is below the threshold.

    Also removes symbols with fewer than 2 rows after filtering.
    """
    s = df.groupby(['symbol']).totalVolume.max() < min_volume
    symbols_to_drop = s[s].index.values
    df = df[~df['symbol'].isin(symbols_to_drop)]
    df = df.groupby('symbol').filter(lambda x: len(x) >= 2)
    return df


def calculate_vwap(data: pd.DataFrame, window: int = 10) -> pd.Series:
    """Calculate volume-weighted average price.

    Args:
        data: DataFrame with 'volume' and 'mark' columns.
        window: Rolling window size.

    Returns:
        Series with VWAP values.
    """
    rolling_pv = (data['volume'] * data['mark']).rolling(window=window, min_periods=1).sum()
    rolling_volume = data['volume'].rolling(window=window, min_periods=1).sum()
    vwap = rolling_pv / rolling_volume
    vwap.rename('vwap', inplace=True)
    vwap[pd.isna(vwap)] = data['mark']
    return vwap
