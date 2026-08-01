"""Tests for app_factory module."""
from unittest.mock import MagicMock, patch

import pytest
from dash import Dash

from options_radar_zero.app_factory import create_app, get_app_info


@pytest.fixture
def mock_data_loader():
    """Create a mock DataLoader that simulates successful data loading."""
    mock = MagicMock()
    mock.is_loaded = False
    mock.symbols = []
    mock.load.return_value = False
    return mock


@pytest.fixture
def mock_data_loader_with_data():
    """Create a mock DataLoader that simulates successful data loading with symbols."""
    mock = MagicMock()
    mock.is_loaded = True
    mock.symbols = ['SPX.X']
    mock.load.return_value = True
    return mock


class TestCreateApp:
    def test_create_app_returns_dash(self, mock_data_loader):
        """Test that create_app returns a Dash instance."""
        with patch('options_radar_zero.app_factory.DataLoader', return_value=mock_data_loader):
            app = create_app()
            assert isinstance(app, Dash)

    def test_create_app_sets_title(self, mock_data_loader):
        """Test that the app title is set correctly."""
        with patch('options_radar_zero.app_factory.DataLoader', return_value=mock_data_loader):
            app = create_app()
            assert app.title == 'SPX 0DTE Chain React Analytics Peaker'

    def test_create_app_with_data_loaded(self, mock_data_loader_with_data):
        """Test app creation when data is loaded."""
        with patch('options_radar_zero.app_factory.DataLoader', return_value=mock_data_loader_with_data):
            app = create_app()
            assert app.layout is not None

    def test_create_app_without_data(self, mock_data_loader):
        """Test app creation when data is not loaded."""
        with patch('options_radar_zero.app_factory.DataLoader', return_value=mock_data_loader):
            app = create_app()
            assert app.layout is not None

    def test_data_loader_attached(self, mock_data_loader):
        """Test that data_loader is attached to the app."""
        with patch('options_radar_zero.app_factory.DataLoader', return_value=mock_data_loader):
            app = create_app()
            assert hasattr(app, 'data_loader')
            assert app.data_loader is mock_data_loader

    def test_routes_registered(self, mock_data_loader):
        """Test that Flask routes are registered."""
        with patch('options_radar_zero.app_factory.DataLoader', return_value=mock_data_loader):
            app = create_app()
            rules = [rule.rule for rule in app.server.url_map.iter_rules()]
            assert '/data/raw/<symbol>' in rules
            assert '/static/<path:path>' in rules
            assert '/tos/0dte/<symbol>' in rules
            assert '/data/<symbol>' in rules

    def test_callbacks_registered(self, mock_data_loader):
        """Test that callbacks are registered."""
        with patch('options_radar_zero.app_factory.DataLoader', return_value=mock_data_loader):
            app = create_app()
            # Dash stores callbacks internally
            assert len(app.callback_map) > 0


class TestGetAppInfo:
    def test_returns_string(self):
        """Test get_app_info returns a string."""
        info = get_app_info()
        assert isinstance(info, str)
        assert 'Dash app starting' in info
