"""Tests for thinkscript module."""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from options_radar_zero.thinkscript import (
    format_expiration_date,
    get_strike_prices,
    get_thinkscript_template,
    tos_ts_0dte,
)


class TestGetThinkscriptTemplate:
    def test_returns_template(self):
        """Test that get_thinkscript_template returns a Jinja2 Template."""
        template = get_thinkscript_template()
        assert template is not None
        assert hasattr(template, 'render')


class TestGetStrikePrices:
    def test_high_price_spx(self):
        """Test strike prices for SPX (price > 1000)."""
        prices = get_strike_prices(4500)
        # range(100, -106, -5) produces 42 values: 100, 95, ..., -100, -105
        assert len(prices) == 42
        assert 4500 in prices
        # Should be spaced by 5
        assert all(p % 5 == 0 for p in prices)

    def test_low_price_spy(self):
        """Test strike prices for SPY (price <= 1000)."""
        prices = get_strike_prices(400)
        assert len(prices) == 11  # range(5, -6, -1) = 11 values
        assert 400 in prices

    def test_boundary_1000(self):
        """Test strike prices at the 1000 boundary."""
        prices = get_strike_prices(1000)
        assert len(prices) == 11  # treated as low price

    def test_boundary_1001(self):
        """Test strike prices just above 1000."""
        prices = get_strike_prices(1001)
        assert len(prices) == 42  # treated as high price
        assert all(p % 5 == 0 for p in prices)


class TestFormatExpirationDate:
    def test_morning_before_4pm(self):
        """Test expiration date formatting before 4pm (same day)."""
        dt = datetime(2024, 1, 15, 10, 0)
        formatted = format_expiration_date(dt)
        assert len(formatted) == 6  # YYMMDD format
        assert formatted == '240115'

    def test_after_4pm(self):
        """Test expiration date formatting after 4pm (next day)."""
        dt = datetime(2024, 1, 15, 17, 0)
        formatted = format_expiration_date(dt)
        assert len(formatted) == 6
        assert formatted == '240116'  # next day

    def test_exactly_4pm(self):
        """Test expiration date formatting at exactly 4pm (next day)."""
        dt = datetime(2024, 1, 15, 16, 0)
        formatted = format_expiration_date(dt)
        assert len(formatted) == 6
        assert formatted == '240116'  # >= 16 means next day

    def test_just_before_4pm(self):
        """Test expiration date formatting at 3:59pm (same day)."""
        dt = datetime(2024, 1, 15, 15, 59)
        formatted = format_expiration_date(dt)
        assert len(formatted) == 6
        assert formatted == '240115'


class TestTosTs0dte:
    def test_raises_without_yfinance(self):
        """Test that tos_ts_0dte raises ImportError if yfinance is not available."""
        with patch('options_radar_zero.thinkscript.yf', None), pytest.raises(ImportError, match="yfinance is required"):
            tos_ts_0dte('SPY')

    def test_generates_valid_thinkscript(self):
        """Test that tos_ts_0dte generates valid thinkscript code."""
        code = tos_ts_0dte('SPY')
        assert 'declare lower;' in code
        assert 'plot Calls' in code
        assert 'plot Puts' in code
        assert 'plot NetMetric' in code

    def test_spx_symbol_mapping(self):
        """Test that SPX symbol is mapped to SPXW."""
        with patch('options_radar_zero.thinkscript.yf') as mock_yf:
            mock_ticker = MagicMock()
            mock_df = MagicMock()
            mock_df.__getitem__ = MagicMock(return_value=4800.0)
            mock_iloc = MagicMock()
            mock_iloc.__getitem__ = MagicMock(return_value=mock_df)
            mock_history = MagicMock()
            mock_history.iloc = mock_iloc
            mock_ticker.history.return_value = mock_history
            mock_yf.Ticker.return_value = mock_ticker

            code = tos_ts_0dte('SPX')
            assert 'SPXW' in code
