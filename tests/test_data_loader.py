"""Tests for data_loader module."""
from unittest.mock import MagicMock, patch

import pytest

from options_radar_zero.data_loader import DataLoader


class TestDataLoaderInit:
    def test_default_file_finder(self):
        """Test that DataLoader initializes with default file finder."""
        dl = DataLoader()
        assert dl._file_finder is not None
        assert dl.is_loaded is False
        assert dl.symbols == []

    def test_custom_file_finder(self):
        """Test DataLoader with custom file finder."""
        mock_finder = MagicMock(return_value={'SPX.X': '/path/to/file.parquet'})
        dl = DataLoader(file_finder=mock_finder)
        assert dl._file_finder is mock_finder


class TestDataLoaderLoad:
    def test_load_success(self):
        """Test successful data loading."""
        mock_finder = MagicMock(return_value={'SPX.X': '/path/to/file.parquet'})
        with patch('options_radar_zero.data_loader.OptionQuotes') as mock_oq_class:
            mock_oq_instance = MagicMock()
            mock_oq_instance.reload.return_value = MagicMock()
            mock_oq_class.return_value = mock_oq_instance

            dl = DataLoader(file_finder=mock_finder)
            result = dl.load()

            assert result is True
            assert dl.is_loaded is True
            assert 'SPX.X' in dl.symbols

    def test_load_no_files(self):
        """Test loading when no files are found."""
        mock_finder = MagicMock(return_value={})
        dl = DataLoader(file_finder=mock_finder)
        result = dl.load()

        assert result is False
        assert dl.is_loaded is False
        assert dl.symbols == []

    def test_load_exception(self):
        """Test loading when an exception occurs."""
        mock_finder = MagicMock(side_effect=Exception("File not found"))
        dl = DataLoader(file_finder=mock_finder)
        result = dl.load()

        assert result is False
        assert dl.is_loaded is False

    def test_load_multiple_symbols(self):
        """Test loading multiple symbols."""
        mock_finder = MagicMock(return_value={
            'SPX.X': '/path/to/spx.parquet',
            'SPY': '/path/to/spy.parquet',
        })
        with patch('options_radar_zero.data_loader.OptionQuotes') as mock_oq_class:
            mock_oq_instance = MagicMock()
            mock_oq_instance.reload.return_value = MagicMock()
            mock_oq_class.return_value = mock_oq_instance

            dl = DataLoader(file_finder=mock_finder)
            result = dl.load()

            assert result is True
            assert len(dl.symbols) == 2


class TestDataLoaderGet:
    def test_get_returns_option_quotes(self):
        """Test get() returns the correct OptionQuotes instance."""
        mock_finder = MagicMock(return_value={'SPX.X': '/path/to/file.parquet'})
        with patch('options_radar_zero.data_loader.OptionQuotes') as mock_oq_class:
            mock_oq_instance = MagicMock()
            mock_oq_instance.reload.return_value = MagicMock()
            mock_oq_class.return_value = mock_oq_instance

            dl = DataLoader(file_finder=mock_finder)
            dl.load()
            result = dl.get('SPX.X')
            assert result is mock_oq_instance

    def test_get_key_error(self):
        """Test get() raises KeyError for unknown symbol."""
        mock_finder = MagicMock(return_value={})
        dl = DataLoader(file_finder=mock_finder)
        with pytest.raises(KeyError):
            dl.get('UNKNOWN')


class TestDataLoaderReload:
    def test_reload_returns_dataframe(self):
        """Test reload() returns the reloaded DataFrame."""
        mock_finder = MagicMock(return_value={'SPX.X': '/path/to/file.parquet'})
        with patch('options_radar_zero.data_loader.OptionQuotes') as mock_oq_class:
            mock_oq_instance = MagicMock()
            mock_df = MagicMock()
            mock_oq_instance.reload.return_value = mock_df
            mock_oq_class.return_value = mock_oq_instance

            dl = DataLoader(file_finder=mock_finder)
            dl.load()
            result = dl.reload('SPX.X')
            assert result is mock_df


class TestDataLoaderAllSymbols:
    def test_all_symbols(self):
        """Test all_symbols() returns the symbols list."""
        mock_finder = MagicMock(return_value={'SPX.X': '/path/to/file.parquet'})
        with patch('options_radar_zero.data_loader.OptionQuotes') as mock_oq_class:
            mock_oq_instance = MagicMock()
            mock_oq_instance.reload.return_value = MagicMock()
            mock_oq_class.return_value = mock_oq_instance

            dl = DataLoader(file_finder=mock_finder)
            dl.load()
            symbols = dl.all_symbols()
            assert 'SPX.X' in symbols
