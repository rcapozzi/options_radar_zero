"""Data processing module - pure functions for data transformation."""
import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from options_radar_zero.config import config

logger = logging.getLogger(__name__)


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
    data.reset_index(drop=True, inplace=True)
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

    # Normalize legacy column names to current format
    # Old poller: last_trade_at → processDateTime, strike → strikePrice,
    #             price → mark, day_volume → totalVolume
    #             underlying_price → underlyingPrice, delta → delta (kept)
    column_aliases = {
        'last_trade_at': 'processDateTime',
        'strike': 'strikePrice',
        'price': 'mark',
        'day_volume': 'totalVolume',
        'underlying_price': 'underlyingPrice',
        'open_interest': 'openInterest',
    }
    for old_name, new_name in column_aliases.items():
        if old_name in df.columns and new_name not in df.columns:
            df.rename(columns={old_name: new_name}, inplace=True)

    # Ensure required columns exist
    if 'processDateTime' not in df.columns:
        logger.warning("Missing 'processDateTime' column in data")
        return pd.DataFrame()
    if 'symbol' not in df.columns:
        df['symbol'] = 'UNKNOWN'
    if 'putCall' not in df.columns:
        df['putCall'] = 'CALL'
    if 'openInterest' not in df.columns:
        df['openInterest'] = 0

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
    if 'gamma' in df.columns:
        df['gex'] = df['openInterestNet'] * df.gamma
    else:
        # gamma not provided by data feed; default gex to 0
        df['gex'] = 0.0

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
    et_time = df.processDateTime.dt.tz_convert('US/Eastern').dt.time
    return df[(et_time >= pd.to_datetime('09:30:00').time()) & (et_time <= pd.to_datetime('16:00:00').time())]  # type: ignore[no-any-return]


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


# Columns needed by the incremental pipeline (compute_incremental_volume +
# build_extenddata_payload).  Reading only these columns avoids decoding
# unused data like bid/ask, openInterest, etc. when the file is large.
_INCREMENTAL_COLUMNS = [
    'processDateTime', 'symbol', 'putCall', 'strikePrice',
    'totalVolume', 'mark', 'underlyingPrice',
]

# Legacy column aliases — normalize old-format parquet files when merging
_LEGACY_ALIASES = {
    'last_trade_at': 'processDateTime',
    'strike': 'strikePrice',
    'price': 'mark',
    'day_volume': 'totalVolume',
    'underlying_price': 'underlyingPrice',
    'open_interest': 'openInterest',
}


def read_incremental_raw_rows(
    filepath: str,
    last_row_count: int,
) -> pd.DataFrame:
    """Read only new rows appended to a parquet file since *last_row_count*.

    Uses pyarrow's ``ParquetFile`` API to read efficiently:

    * **Row-group-aware seeking** — inspects ``ParquetFile.metadata`` to
      locate which row groups contain the new rows, then reads only those
      groups via ``read_row_groups`` instead of decoding the entire file.
    * **Column projection** — reads only the columns required by the
      incremental pipeline (``_INCREMENTAL_COLUMNS``), skipping unused
      columns such as ``bid``, ``ask``, ``openInterest``.
    * **Offset slice** — if the start offset falls inside the first
      relevant row group, ``Table.slice`` trims the already-consumed
      prefix.

    Args:
        filepath: Path to the parquet file.
        last_row_count: Number of rows already processed (offset to skip).

    Returns:
        DataFrame containing only the new rows (may be empty).
    """
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(filepath)
    total_rows = pf.metadata.num_rows
    if last_row_count >= total_rows:
        return pd.DataFrame()

    start_row = last_row_count
    new_row_count = total_rows - start_row

    # Build (global_start, num_rows, rg_index) for each row group.
    rg_infos: list[tuple[int, int, int]] = []
    cumulative = 0
    for i in range(pf.num_row_groups):
        rg = pf.metadata.row_group(i)
        rg_infos.append((cumulative, rg.num_rows, i))
        cumulative += rg.num_rows

    # Select row groups that overlap [start_row, total_rows).
    row_groups_to_read: list[int] = []
    first_rg_global_start: int | None = None
    for rg_start, rg_nrows, rg_idx in rg_infos:
        rg_end = rg_start + rg_nrows
        if rg_end <= start_row:
            continue
        if rg_start >= total_rows:
            break
        if first_rg_global_start is None:
            first_rg_global_start = rg_start
        row_groups_to_read.append(rg_idx)

    if not row_groups_to_read:
        return pd.DataFrame()

    # Project only needed columns; fall back to full schema for legacy files.
    schema_names = {field.name for field in pf.schema_arrow}
    columns = [c for c in _INCREMENTAL_COLUMNS if c in schema_names]
    if not columns:
        columns = None

    table = pf.read_row_groups(row_groups_to_read, columns=columns)

    # The decoded table is a concatenation of the selected row groups in
    # order.  The offset within the table for *start_row* is simply
    # start_row minus the global start of the first group we read.
    assert first_rg_global_start is not None
    offset = start_row - first_rg_global_start

    if offset > 0 or new_row_count < table.num_rows:
        table = table.slice(offset, new_row_count)

    df = table.to_pandas()
    # Normalize legacy column names to current format
    for old_name, new_name in _LEGACY_ALIASES.items():
        if old_name in df.columns and new_name not in df.columns:
            df.rename(columns={old_name: new_name}, inplace=True)
    return df


def compute_incremental_volume(
    new_df: pd.DataFrame,
    last_total_volume: dict[str, float],
) -> pd.DataFrame:
    """Compute incremental per-symbol volume from a batch of new raw rows.

    ``totalVolume`` in the raw data is cumulative.  For each row we subtract
    the last known cumulative ``totalVolume`` for that option symbol to get
    the delta (number of contracts traded since the last poll).

    PUT volume is negated (CALL = +1, PUT = -1) so the chart shows net flow.

    Args:
        new_df: Raw rows (output of ``read_incremental_raw_rows``).
        last_total_volume: Mapping of option symbol -> last cumulative
            ``totalVolume`` seen in the previous batch.

    Returns:
        DataFrame with ``volume`` and ``signed_volume`` columns added.
        The input is not mutated.

    Raises:
        ValueError: If the computed incremental ``volume`` (unsigned diff)
            is negative, which signals a data anomaly -- ``totalVolume`` is
            cumulative and should never decrease between polls.
    """
    if new_df.empty:
        return new_df

    df = new_df.copy()

    # Vectorized incremental volume computation.
    # totalVolume is cumulative per option symbol.  For each row we need
    # the previous cumulative totalVolume for that symbol (from the last
    # poll or from the first row of the current batch).
    df['_prev_totalVolume'] = df.groupby('symbol')['totalVolume'].shift(1)
    # Fill first-row gaps with the last known cumulative value from the
    # previous poll (stored in last_total_volume dict).
    for sym, prev_val in last_total_volume.items():
        mask = (df['symbol'] == sym) & (df['_prev_totalVolume'].isna())
        df.loc[mask, '_prev_totalVolume'] = prev_val
    # For symbols not in last_total_volume, the first row's prev is the
    # row's own totalVolume (diff = 0 for first occurrence).
    df['_prev_totalVolume'] = df['_prev_totalVolume'].fillna(df['totalVolume'])

    vol_diff = df['totalVolume'] - df['_prev_totalVolume']

    # Validate: totalVolume is cumulative and must never decrease.
    if (vol_diff < 0).any():
        bad_cols = [c for c in ('symbol', 'processDateTime', 'totalVolume',
                                '_prev_totalVolume') if c in df.columns]
        bad_rows = df.loc[vol_diff < 0, bad_cols]
        bad_strs = [
            ", ".join(f"{c}={r[c]}" for c in bad_cols)
            for _, r in bad_rows.iterrows()
        ]
        raise ValueError(
            "Negative incremental volume detected -- totalVolume decreased:\n"
            + "\n".join(bad_strs)
        )

    df['volume'] = vol_diff
    sign = df['putCall'].map({'CALL': 1, 'PUT': -1}).fillna(1).astype(float)
    df['signed_volume'] = vol_diff * sign

    # Update last_total_volume in-place with the latest cumulative value
    # per symbol.
    for sym, group in df.groupby('symbol'):
        last_total_volume[sym] = group['totalVolume'].iloc[-1]

    df.drop(columns=['_prev_totalVolume'], inplace=True)
    return df


def build_extenddata_payload(
    df: pd.DataFrame,
    trace_names: list[str],
    strikes: tuple[float, float],
    yaxis: str = 'volume',
    xaxis: str = 'processDateTime',
) -> tuple[list, list[str], set[str]]:
    """Build an ``extendData`` payload from a batch of new transformed rows.

    Each trace in the pez chart is named ``{strike}{putCall[0]}`` (e.g.
    ``741C``) with a special ``underlyingPrice`` trace when the x-axis is
    ``processDateTime``.

    Args:
        df: New raw rows (already volume-diffed via
            ``compute_incremental_volume``).
        trace_names: Ordered list of trace names currently in the chart.
        strikes: (min_strike, max_strike) range tuple.
        yaxis: Y-axis field name.
        xaxis: X-axis field name.

    Returns:
        Tuple of:
        - ``updates``: list of ``{'x': [...], 'y': [...]}`` dicts, one per
          existing trace, plus one per new trace discovered.
        - ``updated_names``: the updated ordered trace name list.
        - ``added_traces``: set of newly discovered trace names.
    """
    if df.empty:
        return [], trace_names[:], set()

    data: dict[str, dict[str, list]] = {}
    added_traces: set[str] = set()

    # Determine x values per trace
    for _, row in df.iterrows():
        strike = int(row['strikePrice'])
        pc = row['putCall']
        if xaxis == 'strikePrice':
            # For strikePrice x-axis, only the latest timestamp matters
            continue
        name = f'{strike}{pc[0]}'
        sign = 1 if pc == 'CALL' else -1
        x_val = row['processDateTime']
        # Strip timezone for plotly
        if hasattr(x_val, 'tz_localize') or hasattr(x_val, 'tz'):
            x_val = x_val.tz_localize(tz=None)
        y_val = row.get(yaxis, 0) * sign

        if name not in data:
            data[name] = {'x': [], 'y': []}
            if name not in trace_names:
                added_traces.add(name)
        data[name]['x'].append(x_val)
        data[name]['y'].append(y_val)

    # underlyingPrice trace (only for processDateTime x-axis)
    # Use mean per timestamp to match the initial pez chart in visualization.py
    # (create_pez_dispenser_chart: df.groupby('processDateTime').underlyingPrice.mean())
    if xaxis == 'processDateTime':
        ul = df.groupby('processDateTime')['underlyingPrice'].mean()
        for dt, up in ul.items():
            if 'underlyingPrice' not in data:
                data['underlyingPrice'] = {'x': [], 'y': []}
            if 'underlyingPrice' not in trace_names:
                added_traces.add('underlyingPrice')
            data['underlyingPrice']['x'].append(dt)
            data['underlyingPrice']['y'].append(up)

    updates: list = []
    for name in trace_names:
        if name in data:
            updates.append(data[name])
        else:
            updates.append({'x': [], 'y': []})

    for name in added_traces:
        updates.append(data[name])

    updated_names = trace_names[:]
    for name in added_traces:
        if name not in updated_names:
            updated_names.append(name)

    return updates, updated_names, added_traces
