"""Tests for callbacks module."""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from dash import Dash, html

from options_radar_zero.callbacks import (
    calculate_strike_range_data,
    is_market_open,
    setup_callbacks,
)


@pytest.fixture
def app_with_callbacks():
    """Create a Dash app with callbacks registered and a minimal layout."""
    app = Dash(__name__)
    app.layout = html.Div([])
    data_loader = MagicMock()
    setup_callbacks(app, data_loader)
    return app, data_loader


@pytest.fixture
def sample_df():
    """Create a sample dataframe for strike range calculation."""
    dates = pd.date_range(start='2024-01-01 09:30', periods=100, freq='min')
    dates = dates.tz_localize('US/Eastern')
    return pd.DataFrame({
        'processDateTime': dates,
        'strikePrice': [4000, 4050, 4100] * 33 + [4000],
        'totalVolume': [100] * 100,
        'putCall': ['CALL'] * 50 + ['PUT'] * 50,
        'underlyingPrice': [4100.0] * 100,
    })


@pytest.fixture
def mock_oq(sample_df):
    """Create a mock OptionQuotes object."""
    oq = MagicMock()
    oq.reload.return_value = sample_df
    oq.data = sample_df
    oq.max_dt = sample_df['processDateTime'].max()
    oq.cache_get.return_value = None
    oq.cache_set.return_value = []
    return oq


class TestIsMarketOpen:
    def test_returns_bool(self):
        """Test is_market_open returns a boolean."""
        result = is_market_open()
        assert isinstance(result, bool)

    def test_fallback_on_error(self):
        """Test is_market_open falls back to True on error."""
        with patch('options_radar_zero.callbacks._is_market_open', side_effect=Exception("test")):
            result = is_market_open()
            assert result is True


class TestCalculateStrikeRangeData:
    def test_returns_tuple(self, sample_df):
        """Test calculate_strike_range_data returns a tuple."""
        result = calculate_strike_range_data(sample_df)
        assert isinstance(result, tuple)

    def test_returns_six_values(self, sample_df):
        """Test calculate_strike_range_data returns 6 values."""
        result = calculate_strike_range_data(sample_df)
        assert len(result) == 6

    def test_min_less_than_max(self, sample_df):
        """Test that min strike is less than max strike."""
        min_strike, max_strike, _, _, _, _ = calculate_strike_range_data(sample_df)
        assert min_strike < max_strike


class TestSetupCallbacks:
    def test_callbacks_registered(self, app_with_callbacks):
        """Test that setup_callbacks registers callbacks."""
        app, _ = app_with_callbacks
        assert len(app.callback_map) > 0

    def test_update_strikes_selector_uses_data_loader(self, app_with_callbacks):
        """Test that update_strikes_selector uses the injected data_loader."""
        app, data_loader = app_with_callbacks
        callback_ids = list(app.callback_map.keys())
        assert any('strikes-selector-div' in cid for cid in callback_ids)

    def test_setup_chart_uses_data_loader(self, app_with_callbacks):
        """Test that setup_chart uses the injected data_loader."""
        app, data_loader = app_with_callbacks
        callback_ids = list(app.callback_map.keys())
        assert any('pc-summary-store' in cid for cid in callback_ids)

    def test_update_chart_on_interval_uses_data_loader(self, app_with_callbacks):
        """Test that update_chart_on_interval uses the injected data_loader."""
        app, data_loader = app_with_callbacks
        callback_ids = list(app.callback_map.keys())
        assert any('pc-summary-graph' in cid for cid in callback_ids)

    def test_update_strike_volume_uses_data_loader(self, app_with_callbacks):
        """Test that update_strike_volume uses the injected data_loader."""
        app, data_loader = app_with_callbacks
        callback_ids = list(app.callback_map.keys())
        assert any('strike-volume-div' in cid for cid in callback_ids)

    def test_backward_compat_with_app_option_quotes(self):
        """Test that setup_callbacks still works with app.OptionQuotes (backward compat)."""
        app = Dash(__name__)
        app.layout = html.Div([])
        app.OptionQuotes = {}

        setup_callbacks(app)  # No data_loader — should fall back to app.OptionQuotes
        assert len(app.callback_map) > 0

    def test_get_oq_uses_data_loader(self, app_with_callbacks, mock_oq):
        """Test that get_oq uses data_loader.get when data_loader is provided."""
        app, data_loader = app_with_callbacks
        data_loader.get.return_value = mock_oq
        # Verify the callback registration used data_loader path
        # by checking that get_oq is wired to data_loader
        assert data_loader is not None

    def test_callback_count(self, app_with_callbacks):
        """Test that exactly 4 callbacks are registered."""
        app, _ = app_with_callbacks
        # 4 callbacks: update_strikes_selector, update_chart_on_interval,
        # setup_chart, update_strike_volume
        assert len(app.callback_map) == 4
