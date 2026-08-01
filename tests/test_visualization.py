"""Tests for visualization module."""

import numpy as np
import pandas as pd
import pytest
import pytz

from options_radar_zero.visualization import (
    create_gex_chart,
    create_mark_comparison_chart,
    create_pez_dispenser_chart,
    create_strike_volume_chart,
)


@pytest.fixture
def sample_chart_data():
    """Create sample data for chart tests."""
    dates = pd.date_range(start='2024-01-01 10:00', periods=20, freq='min')
    data = []
    for dt in dates:
        for strike in [4000, 4050, 4100, 4150]:
            for putcall in ['CALL', 'PUT']:
                data.append({
                    'symbol': f'SPX{strike}{putcall[0]}',
                    'processDateTime': pytz.timezone('US/Eastern').localize(dt),
                    'strikePrice': strike,
                    'putCall': putcall,
                    'volume': np.random.randint(50, 200),
                    'totalVolume': np.random.randint(500, 2000),
                    'mark': np.random.uniform(0.5, 5.0),
                    'gamma': np.random.uniform(0.01, 0.1),
                    'underlyingPrice': 4100,
                    'markDiff': 0.01,
                    'sma5': np.random.uniform(0.5, 2.0),
                    'sma15': np.random.uniform(0.3, 1.5),
                })
    return pd.DataFrame(data)


class TestCreateStrikeVolumeChart:
    def test_returns_figure(self, sample_chart_data):
        """Test that create_strike_volume_chart returns a go.Figure."""
        from options_radar_zero.data_processing import calculate_strike_volume_data
        max_dt = sample_chart_data.processDateTime.max()
        calls, puts, underlying_price = calculate_strike_volume_data(sample_chart_data, max_dt)
        strikes_df = sample_chart_data.groupby(['strikePrice']).agg({'totalVolume': sum}).reset_index()
        fig = create_strike_volume_chart(calls, puts, strikes_df, underlying_price, 4100.0, '2024-01-01 10:00')
        assert fig is not None
        assert len(fig.data) >= 3  # calls, puts, net

    def test_has_title(self, sample_chart_data):
        """Test that the chart has a title."""
        from options_radar_zero.data_processing import calculate_strike_volume_data
        max_dt = sample_chart_data.processDateTime.max()
        calls, puts, underlying_price = calculate_strike_volume_data(sample_chart_data, max_dt)
        strikes_df = sample_chart_data.groupby(['strikePrice']).agg({'totalVolume': sum}).reset_index()
        fig = create_strike_volume_chart(calls, puts, strikes_df, underlying_price, 4100.0, '2024-01-01 10:00')
        assert fig.layout.title is not None

    def test_has_hlines(self, sample_chart_data):
        """Test that the chart has horizontal lines for underlying price and net GEX."""
        from options_radar_zero.data_processing import calculate_strike_volume_data
        max_dt = sample_chart_data.processDateTime.max()
        calls, puts, underlying_price = calculate_strike_volume_data(sample_chart_data, max_dt)
        strikes_df = sample_chart_data.groupby(['strikePrice']).agg({'totalVolume': sum}).reset_index()
        fig = create_strike_volume_chart(calls, puts, strikes_df, underlying_price, 4100.0, '2024-01-01 10:00')
        # Check for hlines in layout shapes
        shapes = fig.layout.shapes
        assert len(shapes) >= 2  # at least 2 hlines


class TestCreateMarkComparisonChart:
    def test_returns_figure(self, sample_chart_data):
        """Test that create_mark_comparison_chart returns a go.Figure."""
        fig = create_mark_comparison_chart(sample_chart_data, 4100, '2024-01-01 10:00')
        assert fig is not None

    def test_has_title(self, sample_chart_data):
        """Test that the chart has a title."""
        fig = create_mark_comparison_chart(sample_chart_data, 4100, '2024-01-01 10:00')
        assert fig.layout.title is not None


class TestCreateGexChart:
    def test_mode_zero(self, sample_chart_data):
        """Test create_gex_chart with mode=0."""
        fig = create_gex_chart(sample_chart_data, 'SPX.X', mode=0)
        assert fig is not None
        assert len(fig.data) >= 4  # calls, puts, net, lag10

    def test_mode_one(self, sample_chart_data):
        """Test create_gex_chart with mode=1."""
        fig = create_gex_chart(sample_chart_data, 'SPX.X', mode=1)
        assert fig is not None
        assert len(fig.data) >= 4

    def test_has_title(self, sample_chart_data):
        """Test that the chart has a title."""
        fig = create_gex_chart(sample_chart_data, 'SPX.X', mode=0)
        assert fig.layout.title is not None


class TestCreatePezDispenserChart:
    def test_returns_tuple(self, sample_chart_data):
        """Test that create_pez_dispenser_chart returns (state, fig)."""
        result = create_pez_dispenser_chart(
            sample_chart_data, (4000, 4200), 'volume', 'processDateTime', title='test'
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_state_has_names(self, sample_chart_data):
        """Test that the returned state has trace names."""
        state, fig = create_pez_dispenser_chart(
            sample_chart_data, (4000, 4200), 'volume', 'processDateTime', title='test'
        )
        assert 'names' in state
        assert isinstance(state['names'], list)

    def test_empty_dataframe(self):
        """Test that empty DataFrame returns empty state and figure."""
        empty_df = pd.DataFrame()
        state, fig = create_pez_dispenser_chart(
            empty_df, (0, 100), 'volume', 'processDateTime', title='test'
        )
        assert state == {}
        assert fig is not None

    def test_strike_price_xaxis(self, sample_chart_data):
        """Test pez dispenser chart with strikePrice as x-axis."""
        state, fig = create_pez_dispenser_chart(
            sample_chart_data, (4000, 4200), 'mark', 'strikePrice', title='test'
        )
        assert state is not None
        assert fig is not None
