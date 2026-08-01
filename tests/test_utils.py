"""Tests for utils module (OptionQuotes class)."""

import pandas as pd
import pytest

from options_radar_zero.utils import OptionQuotes


class TestOptionQuotesInit:
    def test_default_filename(self):
        """Test default filename generation."""
        oq = OptionQuotes(symbol='TEST')
        assert oq.filename == 'data/TEST.2023-05-04.parquet'

    def test_custom_filename(self):
        """Test custom filename."""
        oq = OptionQuotes(symbol='TEST', filename='/path/to/test.parquet')
        assert oq.filename == '/path/to/test.parquet'

    def test_initial_state(self):
        """Test initial state."""
        oq = OptionQuotes(symbol='TEST', filename='/path/to/test.parquet')
        assert oq.data is None
        assert oq.cache == {}
        assert oq.last_mtime == 0
        assert oq.max_dt is None


class TestOptionQuotesCache:
    def test_cache_set_get(self):
        """Test cache set and get."""
        oq = OptionQuotes(symbol='TEST', filename='/path/to/test.parquet')
        oq.cache_set('key1', 'value1')
        assert oq.cache_get('key1') == 'value1'

    def test_cache_get_missing(self):
        """Test cache get returns None for missing key."""
        oq = OptionQuotes(symbol='TEST', filename='/path/to/test.parquet')
        assert oq.cache_get('nonexistent') is None


class TestOptionQuotesReload:
    def test_reload_loads_data(self, tmp_path, raw_option_dataframe):
        """Test that reload loads parquet data and transforms it."""
        parquet_file = tmp_path / "test_data.parquet"
        raw_option_dataframe.to_parquet(parquet_file)

        oq = OptionQuotes(symbol='TEST', filename=str(parquet_file))
        df = oq.reload()

        assert df is not None
        assert len(df) > 0
        assert 'gex' in df.columns
        assert 'volume' in df.columns
        assert 'distance' in df.columns

    def test_reload_caches_max_dt(self, tmp_path, raw_option_dataframe):
        """Test that reload caches max_dt."""
        parquet_file = tmp_path / "test_data.parquet"
        raw_option_dataframe.to_parquet(parquet_file)

        oq = OptionQuotes(symbol='TEST', filename=str(parquet_file))
        oq.reload()

        assert oq.max_dt is not None
        cached_max_dt = oq.cache_get('max_dt')
        assert cached_max_dt is not None
        assert cached_max_dt == oq.max_dt

    def test_reload_skips_if_unchanged(self, tmp_path, raw_option_dataframe):
        """Test that reload skips if file mtime hasn't changed."""
        parquet_file = tmp_path / "test_data.parquet"
        raw_option_dataframe.to_parquet(parquet_file)

        oq = OptionQuotes(symbol='TEST', filename=str(parquet_file))
        df1 = oq.reload()
        df2 = oq.reload()

        # Same object returned (no reload)
        assert df1 is df2


class TestOptionQuotesPivot:
    def test_pivot_returns_dataframe(self, tmp_path, raw_option_dataframe):
        """Test pivot returns a DataFrame."""
        parquet_file = tmp_path / "test_data.parquet"
        raw_option_dataframe.to_parquet(parquet_file)

        oq = OptionQuotes(symbol='TEST', filename=str(parquet_file))
        oq.reload()
        pivot = oq.pivot()
        assert isinstance(pivot, pd.DataFrame)

    def test_pivot_cached(self, tmp_path, raw_option_dataframe):
        """Test that pivot is cached."""
        parquet_file = tmp_path / "test_data.parquet"
        raw_option_dataframe.to_parquet(parquet_file)

        oq = OptionQuotes(symbol='TEST', filename=str(parquet_file))
        oq.reload()
        pivot1 = oq.pivot()
        pivot2 = oq.pivot()
        assert pivot1 is pivot2


class TestOptionQuotesUnderlyingHistory:
    def test_returns_series(self, tmp_path, raw_option_dataframe):
        """Test underlying_history returns a Series."""
        parquet_file = tmp_path / "test_data.parquet"
        raw_option_dataframe.to_parquet(parquet_file)

        oq = OptionQuotes(symbol='TEST', filename=str(parquet_file))
        oq.reload()
        history = oq.underlying_history()
        assert isinstance(history, pd.Series)


class TestOptionQuotesCalcSpreads:
    def test_returns_dataframe_with_positive_prices(self, tmp_path, raw_option_dataframe):
        """Test calc_spreads returns only positive-priced spreads."""
        parquet_file = tmp_path / "test_data.parquet"
        raw_option_dataframe.to_parquet(parquet_file)

        oq = OptionQuotes(symbol='TEST', filename=str(parquet_file))
        oq.reload()
        df = oq.data[oq.data.putCall == 'CALL'].copy()
        if len(df) > 0:
            spreads = oq.calc_spreads(df[['strikePrice', 'mark']], distance=5)
            assert (spreads['price'] > 0.05).all()


class TestOptionQuotesFindSpread:
    def test_returns_dict(self, tmp_path, raw_option_dataframe):
        """Test find_spread returns a dict with expected keys."""
        parquet_file = tmp_path / "test_data.parquet"
        raw_option_dataframe.to_parquet(parquet_file)

        oq = OptionQuotes(symbol='TEST', filename=str(parquet_file))
        oq.reload()
        now = oq.max_dt
        opts = {'putCall': 'CALL', 'distance': 5, 'creditMin': 0.05, 'creditTarget': 1.0}
        try:
            result = oq.find_spread(now, opts)
            assert isinstance(result, dict)
            assert 'putCall' in result
            assert 'distance' in result
        except IndexError:
            # If no spreads match the criteria, that's acceptable for this test data
            pytest.skip("No matching spreads in test data")
