"""Tests for config module."""
from unittest.mock import patch

import pytest

from options_radar_zero.config import DEFAULT_X_FIELDS, DEFAULT_Y_FIELDS, config, get_parquet_files


class TestAppConfig:
    def test_defaults(self):
        """Test that AppConfig has expected defaults."""
        assert config.DEFAULT_INTERVAL_SECONDS == 60
        assert config.DATA_DIR == './output'
        assert config.STATIC_DIR == 'static'
        assert config.MARKET_OPEN_TIME == '09:30'
        assert config.MARKET_CLOSE_TIME == '16:00'

    def test_colors(self):
        """Test color scheme constants."""
        assert config.COLORS['call'] == 'rgb(26, 118, 255)'
        assert config.COLORS['put'] == 'rgb(55, 83, 109)'
        assert config.COLORS['net'] == 'white'
        assert config.COLORS['underlying_price'] == 'yellow'
        assert config.COLORS['gex_orange'] == 'orange'
        assert config.COLORS['spx_price'] == 'crimson'

    def test_thresholds(self):
        """Test threshold constants."""
        assert config.MIN_VOLUME_THRESHOLD == 10
        assert config.LOW_VOLUME_FILTER_MIN == 50

    def test_chart_constants(self):
        """Test chart layout constants."""
        assert config.CHART_TEMPLATE == 'plotly_dark'
        assert config.CHART_HEIGHT == 600
        assert config.CHART_MARGIN == {'l': 10, 'r': 10, 't': 10, 'b': 10}
        assert config.CHART_MODEBAR == {"displayModeBar": False}

    def test_file_watcher_interval(self):
        """Test file watcher interval constant."""
        assert config.FILE_WATCHER_INTERVAL_MS == 10000

    def test_frozen(self):
        """Test that AppConfig is frozen (immutable)."""
        from dataclasses import FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            config.DATA_DIR = '/other/path'


class TestDefaultFields:
    def test_x_fields(self):
        """Test default x-axis fields."""
        assert 'processDateTime' in DEFAULT_X_FIELDS
        assert 'strikePrice' in DEFAULT_X_FIELDS
        assert 'distance' in DEFAULT_X_FIELDS

    def test_y_fields(self):
        """Test default y-axis fields."""
        assert 'volume' in DEFAULT_Y_FIELDS
        assert 'totalVolume' in DEFAULT_Y_FIELDS
        assert 'gex' in DEFAULT_Y_FIELDS
        assert 'mark' in DEFAULT_Y_FIELDS


class TestGetParquetFiles:
    def test_returns_dict(self):
        """Test that get_parquet_files returns a dict."""
        result = get_parquet_files()
        assert isinstance(result, dict)

    def test_empty_directory(self, tmp_path):
        """Test get_parquet_files with an empty directory."""
        with patch('options_radar_zero.config.config') as mock_config:
            mock_config.DATA_DIR = str(tmp_path)
            result = get_parquet_files()
            assert result == {}

    def test_with_parquet_files(self, tmp_path):
        """Test get_parquet_files with actual parquet files."""
        # Create dummy parquet files (poller format: symbol.date.chain.parquet)
        (tmp_path / "SPX.20240115.chain.parquet").touch()
        (tmp_path / "SPY.20240115.chain.parquet").touch()
        (tmp_path / "QQQ.20240115.chain.parquet").touch()

        with patch('options_radar_zero.config.config') as mock_config:
            mock_config.DATA_DIR = str(tmp_path)
            result = get_parquet_files()
            assert 'SPY' in result
            assert 'SPX' in result
            assert 'QQQ' in result

    def test_max_files_limit(self, tmp_path):
        """Test that max_files parameter limits results."""
        for i in range(25):
            (tmp_path / f"SYM{i:02d}.20240115.chain.parquet").touch()

        with patch('options_radar_zero.config.config') as mock_config:
            mock_config.DATA_DIR = str(tmp_path)
            result = get_parquet_files(max_files=5)
            assert len(result) == 5

    def test_sorts_reverse(self, tmp_path):
        """Test that files are sorted in reverse order."""
        (tmp_path / "AAA.20240115.chain.parquet").touch()
        (tmp_path / "ZZZ.20240115.chain.parquet").touch()

        with patch('options_radar_zero.config.config') as mock_config:
            mock_config.DATA_DIR = str(tmp_path)
            result = get_parquet_files()
            keys = list(result.keys())
            # AAA sorts before ZZZ, but reverse=True means ZZZ comes first
            assert keys[0] == 'ZZZ'
