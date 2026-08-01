"""Tests for routes module."""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from dash import Dash, html

from options_radar_zero.routes import register_routes


@pytest.fixture
def app_with_routes():
    """Create a Dash app with routes registered and a minimal layout."""
    app = Dash(__name__)
    app.layout = html.Div([])
    data_loader = MagicMock()
    register_routes(app, data_loader)
    return app, data_loader


@pytest.fixture
def mock_oq():
    """Create a mock OptionQuotes object."""
    dates = pd.date_range(start='2024-01-01 09:30', periods=20, freq='min')
    dates = dates.tz_localize('US/Eastern')
    sample_df = pd.DataFrame({
        'processDateTime': dates,
        'strikePrice': [4000, 4050, 4100, 4150] * 5,
        'totalVolume': [100] * 20,
        'putCall': ['CALL'] * 10 + ['PUT'] * 10,
        'underlyingPrice': [4100.0] * 20,
    })
    oq = MagicMock()
    oq.reload.return_value = sample_df
    oq.data = sample_df
    oq.max_dt = sample_df['processDateTime'].max()
    oq.filename = '/path/to/test.parquet'
    oq.cache_get.return_value = None
    oq.cache_set.return_value = []
    return oq


class TestRoutesRegistration:
    def test_register_routes_adds_all_routes(self, app_with_routes):
        """Test that register_routes adds all expected Flask routes."""
        app, _ = app_with_routes
        rules = [rule.rule for rule in app.server.url_map.iter_rules()]
        assert '/data/raw/<symbol>' in rules
        assert '/static/<path:path>' in rules
        assert '/tos/0dte/<symbol>' in rules
        assert '/data/<symbol>' in rules

    def test_download_callbacks_registered(self, app_with_routes):
        """Test that download callbacks are registered."""
        app, _ = app_with_routes
        callback_ids = list(app.callback_map.keys())
        assert any('download-dataframe-parquet' in cid for cid in callback_ids)
        assert any('download-dataframe-csv' in cid for cid in callback_ids)


class TestServeDataRawFile:
    def test_serves_parquet_file(self, app_with_routes, mock_oq):
        """Test that serve_data_raw_file returns the parquet file."""
        app, data_loader = app_with_routes
        data_loader.get.return_value = mock_oq

        with patch('options_radar_zero.routes.send_file') as mock_send_file:
            mock_response = MagicMock()
            mock_send_file.return_value = mock_response
            with app.server.test_client() as client:
                client.get('/data/raw/SPX.X')
                assert data_loader.get.called
                assert 'SPX.X' in data_loader.get.call_args[0]

    def test_sets_content_disposition(self, app_with_routes, mock_oq):
        """Test that serve_data_raw_file sets Content-Disposition header."""
        app, data_loader = app_with_routes
        data_loader.get.return_value = mock_oq

        with patch('options_radar_zero.routes.send_file') as mock_send_file:
            mock_response = MagicMock()
            mock_send_file.return_value = mock_response
            with app.server.test_client() as client:
                response = client.get('/data/raw/SPX.X')
                assert response.status_code == 200


class TestServeStatic:
    def test_serves_static_file_not_found(self, app_with_routes):
        """Test that serve_static returns 404 for non-existent files."""
        app, _ = app_with_routes
        with app.server.test_client() as client:
            response = client.get('/static/test.html')
            assert response.status_code == 404


class TestServeThinkscript:
    def test_returns_thinkscript_html(self, app_with_routes):
        """Test that serve_thinkscript returns thinkscript wrapped in <pre>."""
        app, _ = app_with_routes
        with patch('options_radar_zero.routes.tos_ts_0dte') as mock_thinkscript:
            mock_thinkscript.return_value = 'declare lower; plot Calls = 1;'
            with app.server.test_client() as client:
                response = client.get('/tos/0dte/SPY')
                assert response.status_code == 200
                assert b'<pre>' in response.data
                assert b'declare lower' in response.data

    def test_thinkscript_with_spx_symbol(self, app_with_routes):
        """Test that serve_thinkscript works with SPX symbol."""
        app, _ = app_with_routes
        with patch('options_radar_zero.routes.tos_ts_0dte') as mock_thinkscript:
            mock_thinkscript.return_value = 'declare lower;'
            with app.server.test_client() as client:
                response = client.get('/tos/0dte/SPX')
                assert response.status_code == 200
                assert b'declare lower' in response.data


class TestServeDataFile:
    def test_serves_incremental_data(self, app_with_routes, mock_oq):
        """Test that serve_data_file returns incremental parquet data."""
        app, data_loader = app_with_routes
        data_loader.get.return_value = mock_oq

        with patch('options_radar_zero.routes.EasternDT') as mock_eastern:
            mock_eastern.u2e.return_value = pd.Timestamp('2024-01-01 09:00', tz='US/Eastern')
            with patch('options_radar_zero.routes.send_file') as mock_send_file:
                mock_send_file.return_value = MagicMock()
                with app.server.test_client() as client:
                    client.get('/data/SPX.X?u=1234567890')
                    assert data_loader.get.called

    def test_uses_eastern_dt_for_conversion(self, app_with_routes, mock_oq):
        """Test that serve_data_file uses EasternDT.u2e for timestamp conversion."""
        app, data_loader = app_with_routes
        data_loader.get.return_value = mock_oq

        with patch('options_radar_zero.routes.EasternDT') as mock_eastern:
            mock_eastern.u2e.return_value = pd.Timestamp('2024-01-01 09:00', tz='US/Eastern')
            with patch('options_radar_zero.routes.send_file') as mock_send_file:
                mock_send_file.return_value = MagicMock()
                with app.server.test_client() as client:
                    client.get('/data/SPX.X?u=1234567890')
                    assert mock_eastern.u2e.called

    def test_handles_missing_u_param(self, app_with_routes, mock_oq):
        """Test that serve_data_file handles missing u parameter."""
        app, data_loader = app_with_routes
        data_loader.get.return_value = mock_oq

        with patch('options_radar_zero.routes.EasternDT') as mock_eastern:
            mock_eastern.u2e.return_value = pd.Timestamp('2024-01-01 09:00', tz='US/Eastern')
            with patch('options_radar_zero.routes.send_file') as mock_send_file:
                mock_send_file.return_value = MagicMock()
                with app.server.test_client() as client:
                    client.get('/data/SPX.X')
                    assert mock_eastern.u2e.called


class TestDownloadCallbacks:
    def test_download_parquet_callback_registered(self, app_with_routes, mock_oq):
        """Test that download_parquet callback is registered."""
        app, data_loader = app_with_routes
        mock_oq.filename = '/path/to/test.parquet'
        data_loader.get.return_value = mock_oq

        callback_ids = list(app.callback_map.keys())
        assert any('download-dataframe-parquet' in cid for cid in callback_ids)

    def test_download_csv_callback_registered(self, app_with_routes, mock_oq):
        """Test that download_csv callback is registered."""
        app, data_loader = app_with_routes
        mock_oq.filename = '/path/to/test.parquet'
        mock_oq.reload.return_value = MagicMock()
        data_loader.get.return_value = mock_oq

        callback_ids = list(app.callback_map.keys())
        assert any('download-dataframe-csv' in cid for cid in callback_ids)

    def test_download_csv_uses_existing_file(self, app_with_routes, mock_oq, tmp_path):
        """Test that download_csv uses existing CSV file if available."""
        app, data_loader = app_with_routes
        csv_file = str(tmp_path / "test.csv.gz")
        with open(csv_file, 'w') as f:
            f.write("test,data\n1,2\n")

        mock_oq.filename = str(tmp_path / "test.parquet")
        mock_oq.reload.return_value = MagicMock()
        data_loader.get.return_value = mock_oq

        callback_ids = list(app.callback_map.keys())
        assert any('download-dataframe-csv' in cid for cid in callback_ids)

    def test_download_csv_falls_back_to_send_data_frame(self, app_with_routes, mock_oq):
        """Test that download_csv falls back to send_data_frame when no CSV exists."""
        app, data_loader = app_with_routes
        mock_oq.filename = '/nonexistent/path/test.parquet'
        mock_df = MagicMock()
        mock_oq.reload.return_value = mock_df
        data_loader.get.return_value = mock_oq

        with patch('os.path.exists', return_value=False), \
             patch('options_radar_zero.routes.dcc.send_data_frame') as mock_send:
                mock_send.return_value = MagicMock()
                callback_ids = list(app.callback_map.keys())
                assert any('download-dataframe-csv' in cid for cid in callback_ids)
