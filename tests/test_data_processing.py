"""Tests for data_processing module."""
from datetime import datetime

import pandas as pd
import pytz

from options_radar_zero.config import config
from options_radar_zero.data_processing import (
    calculate_gex_metrics,
    calculate_strike_range,
    calculate_vwap,
    filter_dataframe_by_strikes,
    filter_dataframe_by_volume,
    filter_low_volume,
    filter_rth,
    prepare_chart_data,
    transform_option_data,
)


class TestFilterDataframeByStrikes:
    def test_filters_within_range(self, sample_dataframe):
        filtered = filter_dataframe_by_strikes(sample_dataframe, 4050, 4150)
        assert filtered['strikePrice'].min() >= 4050
        assert filtered['strikePrice'].max() <= 4150

    def test_returns_copy(self, sample_dataframe):
        original_len = len(sample_dataframe)
        filter_dataframe_by_strikes(sample_dataframe, 4050, 4150)
        assert len(sample_dataframe) == original_len  # original unchanged


class TestFilterDataframeByVolume:
    def test_filters_below_threshold(self, sample_dataframe):
        filtered = filter_dataframe_by_volume(sample_dataframe, min_volume=200)
        assert filtered['totalVolume'].min() >= 200

    def test_uses_config_default(self, sample_dataframe):
        filtered = filter_dataframe_by_volume(sample_dataframe)
        assert filtered['totalVolume'].min() >= config.MIN_VOLUME_THRESHOLD


class TestCalculateStrikeRange:
    def test_returns_six_values(self, sample_dataframe):
        result = calculate_strike_range(sample_dataframe)
        assert len(result) == 6

    def test_min_less_than_max(self, sample_dataframe):
        min_strike, max_strike, step, price_min, price_max, price_range = calculate_strike_range(sample_dataframe)
        assert min_strike < max_strike
        assert price_min <= price_max
        assert step in [1, 25]


class TestPrepareChartData:
    def test_adds_sign_column(self, sample_dataframe):
        data = prepare_chart_data(
            sample_dataframe,
            xaxis='processDateTime',
            yaxis='volume',
            strikes=(4050, 4150),
        )
        assert 'sign' in data.columns
        assert len(data) > 0

    def test_strike_price_xaxis(self, sample_dataframe):
        data = prepare_chart_data(
            sample_dataframe,
            xaxis='strikePrice',
            yaxis='mark',
            strikes=(4050, 4150),
        )
        assert 'sign' in data.columns


class TestCalculateGexMetrics:
    def test_returns_three_floats(self, raw_option_dataframe):
        """Test calculate_gex_metrics returns three floats."""
        transformed = transform_option_data(raw_option_dataframe)
        put_gex, call_gex, net_gex = calculate_gex_metrics(transformed)
        assert isinstance(put_gex, float)
        assert isinstance(call_gex, float)
        assert isinstance(net_gex, float)

    def test_empty_dataframe(self):
        """Test calculate_gex_metrics with empty dataframe."""
        empty_df = pd.DataFrame(columns=['putCall', 'gex', 'strikePrice'])
        put_gex, call_gex, net_gex = calculate_gex_metrics(empty_df)
        assert put_gex == 0.0
        assert call_gex == 0.0
        assert net_gex == 0.0


class TestTransformOptionData:
    def test_does_not_mutate_input(self, raw_option_dataframe):
        original_columns = set(raw_option_dataframe.columns)
        _ = transform_option_data(raw_option_dataframe)
        assert set(raw_option_dataframe.columns) == original_columns

    def test_adds_derived_columns(self, raw_option_dataframe):
        result = transform_option_data(raw_option_dataframe)
        assert 'volume' in result.columns
        assert 'gex' in result.columns
        assert 'distance' in result.columns
        assert 'markDiff' in result.columns

    def test_drops_intermediate_columns(self, raw_option_dataframe):
        result = transform_option_data(raw_option_dataframe)
        assert 'upDown' not in result.columns
        assert 'volumeUpDown' not in result.columns
        assert 'volumeUpDownCum' not in result.columns
        assert 'tradeTimeInLong' not in result.columns
        assert 'theoreticalVolatility' not in result.columns

    def test_filters_rth(self, raw_option_dataframe):
        result = transform_option_data(raw_option_dataframe)
        times = result.processDateTime.dt.time
        assert times.min() >= pd.to_datetime('09:30:00').time()
        assert times.max() <= pd.to_datetime('16:00:00').time()

    def test_rounds_underlying_price(self, raw_option_dataframe):
        result = transform_option_data(raw_option_dataframe)
        # underlyingPrice should be rounded to 0 decimals
        assert (result['underlyingPrice'] == result['underlyingPrice'].round(0)).all()


class TestFilterRth:
    def test_filters_before_930(self, sample_dataframe):
        sample_dataframe.loc[0, 'processDateTime'] = pytz.timezone('US/Eastern').localize(
            datetime(2024, 1, 1, 8, 0)
        )
        result = filter_rth(sample_dataframe)
        assert result.processDateTime.dt.time.min() >= pd.to_datetime('09:30:00').time()


class TestFilterLowVolume:
    def test_removes_low_volume_symbols(self, raw_option_dataframe):
        # Set one symbol's totalVolume to very low
        mask = raw_option_dataframe['symbol'] == raw_option_dataframe['symbol'].iloc[0]
        raw_option_dataframe.loc[mask, 'totalVolume'] = 10
        result = filter_low_volume(raw_option_dataframe, min_volume=50)
        assert raw_option_dataframe['symbol'].iloc[0] not in result['symbol'].unique()


class TestCalculateVwap:
    def test_returns_series(self, sample_dataframe):
        vwap = calculate_vwap(sample_dataframe, window=5)
        assert isinstance(vwap, pd.Series)
        assert 'vwap' in vwap.name

    def test_fills_nan_with_mark(self, sample_dataframe):
        vwap = calculate_vwap(sample_dataframe, window=5)
        # Where vwap is NaN, it should be filled with mark
        nan_mask = vwap.isna()
        if nan_mask.any():
            assert (vwap[nan_mask] == sample_dataframe['mark'][nan_mask]).all()
