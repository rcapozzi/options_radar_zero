"""Tests for market_hours module."""
import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfoNotFoundError

import pytest

from options_radar_zero.market_hours import EasternDT, MarketIntervalCalculator, is_market_open


class TestEasternDT:
    def test_u2e_with_unix_timestamp(self):
        """Test conversion from Unix timestamp to Eastern datetime."""
        ts = 1704117600
        result = EasternDT.u2e(ts)
        assert result.hour == 9
        assert result.tzinfo is not None

    def test_u2e_with_milliseconds(self):
        """Test conversion with millisecond timestamp."""
        ts = 1704117600000  # milliseconds
        result = EasternDT.u2e(ts)
        assert result.hour == 9

    def test_u2e_with_none(self):
        """Test conversion with None defaults to 0."""
        result = EasternDT.u2e(None)
        assert result.year == 1969

    def test_u2e_with_zero(self):
        """Test conversion with 0."""
        result = EasternDT.u2e(0)
        assert result.year == 1969

    def test_e2u_to_unix(self):
        """Test conversion from Eastern datetime to Unix timestamp."""
        import pytz
        eastern_dt = datetime.datetime(2024, 1, 1, 9, 0, tzinfo=pytz.timezone('US/Eastern'))
        result = EasternDT.e2u(eastern_dt)
        assert isinstance(result, int)
        assert result > 0

    def test_e2u_naive_datetime(self):
        """Test e2u with naive datetime (should localize to Eastern)."""
        naive_dt = datetime.datetime(2024, 1, 1, 9, 0)
        result = EasternDT.e2u(naive_dt)
        assert isinstance(result, int)

    def test_now_returns_eastern(self):
        """Test that now() returns current Eastern time."""
        result = EasternDT.now()
        assert result.tzinfo is not None
        utc_now = datetime.datetime.now(datetime.UTC)
        diff = abs((result.astimezone(datetime.UTC) - utc_now).total_seconds())
        assert diff < 60


class TestMarketIntervalCalculator:
    def test_instantiation(self):
        """Test that MarketIntervalCalculator can be instantiated."""
        calc = MarketIntervalCalculator()
        assert calc._market_tz is not None
        assert calc._nyse_calendar is not None

    def test_is_market_open_returns_bool(self):
        """Test is_market_open returns a boolean."""
        calc = MarketIntervalCalculator()
        result = calc.is_market_open()
        assert isinstance(result, bool)

    def test_get_next_update_time_returns_datetime(self):
        """Test get_next_update_time returns a datetime."""
        calc = MarketIntervalCalculator()
        result = calc.get_next_update_time()
        assert isinstance(result, datetime.datetime)

    def test_get_market_close_returns_datetime(self):
        """Test get_market_close returns a datetime."""
        calc = MarketIntervalCalculator()
        result = calc.get_market_close()
        assert isinstance(result, datetime.datetime)

    def test_get_next_update_time_market_open(self):
        """Test get_next_update_time when market is open."""
        calc = MarketIntervalCalculator()
        mock_schedule = MagicMock()
        mock_schedule.empty = False
        mock_schedule.iloc = [
            {
                'market_open': datetime.datetime(2024, 1, 1, 9, 30, tzinfo=calc._market_tz),
                'market_close': datetime.datetime(2024, 1, 1, 16, 0, tzinfo=calc._market_tz),
            }
        ]
        with patch.object(calc, '_get_market_schedule_for_date', return_value=mock_schedule):
            result = calc.get_next_update_time()
            assert isinstance(result, datetime.datetime)

    def test_get_next_update_time_market_not_open_yet(self):
        """Test get_next_update_time when market hasn't opened yet."""
        calc = MarketIntervalCalculator()
        mock_schedule = MagicMock()
        mock_schedule.empty = False
        mock_open = datetime.datetime(2000, 1, 1, 9, 30, tzinfo=calc._market_tz)
        mock_close = datetime.datetime(2000, 1, 1, 16, 0, tzinfo=calc._market_tz)
        mock_schedule.iloc = [{'market_open': mock_open, 'market_close': mock_close}]

        with patch.object(calc, '_get_market_schedule_for_date', return_value=mock_schedule), \
             patch('options_radar_zero.market_hours.datetime') as mock_dt:
            mock_dt.datetime.now.return_value = datetime.datetime(2000, 1, 1, 8, 0, tzinfo=calc._market_tz)
            mock_dt.timedelta = datetime.timedelta
            result = calc.get_next_update_time()
            assert isinstance(result, datetime.datetime)

    def test_get_next_update_time_market_closed_lookahead(self):
        """Test get_next_update_time when market is closed and looks ahead."""
        calc = MarketIntervalCalculator()
        empty_schedule = MagicMock()
        empty_schedule.empty = True
        future_schedule = MagicMock()
        future_schedule.empty = False
        future_open = datetime.datetime(2024, 1, 2, 9, 30, tzinfo=calc._market_tz)
        future_schedule.iloc = [{'market_open': future_open, 'market_close': MagicMock()}]

        with patch.object(calc, '_get_market_schedule_for_date', side_effect=[empty_schedule, future_schedule]), \
             patch('options_radar_zero.market_hours.datetime') as mock_dt:
            mock_dt.datetime.now.return_value = datetime.datetime(2024, 1, 1, 17, 0, tzinfo=calc._market_tz)
            mock_dt.timedelta = datetime.timedelta
            result = calc.get_next_update_time()
            assert isinstance(result, datetime.datetime)

    def test_get_next_update_time_no_open_day_found(self):
        """Test get_next_update_time when no open day found in 10 days."""
        calc = MarketIntervalCalculator()
        empty_schedule = MagicMock()
        empty_schedule.empty = True

        with patch.object(calc, '_get_market_schedule_for_date', return_value=empty_schedule), \
             patch('options_radar_zero.market_hours.datetime') as mock_dt:
            mock_dt.datetime.now.return_value = datetime.datetime(2024, 1, 1, 17, 0, tzinfo=calc._market_tz)
            mock_dt.timedelta = datetime.timedelta
            result = calc.get_next_update_time()
            assert isinstance(result, datetime.datetime)

    def test_is_market_open_closed_today(self):
        """Test is_market_open returns False when market is closed."""
        calc = MarketIntervalCalculator()
        empty_schedule = MagicMock()
        empty_schedule.empty = True

        with patch.object(calc, '_get_market_schedule_for_date', return_value=empty_schedule):
            result = calc.is_market_open()
            assert result is False

    def test_is_market_open_with_schedule(self):
        """Test is_market_open with a valid schedule."""
        calc = MarketIntervalCalculator()
        mock_schedule = MagicMock()
        mock_schedule.empty = False
        now = datetime.datetime.now(calc._market_tz)
        open_time = now - datetime.timedelta(hours=1)
        close_time = now + datetime.timedelta(hours=1)
        mock_schedule.iloc = [
            {
                'market_open': open_time,
                'market_close': close_time,
            }
        ]

        with patch.object(calc, '_get_market_schedule_for_date', return_value=mock_schedule):
            result = calc.is_market_open()
            assert isinstance(result, bool)

    def test_zoneinfo_not_found(self):
        """Test that ZoneInfoNotFoundError raises RuntimeError."""
        with patch('options_radar_zero.market_hours.ZoneInfo', side_effect=ZoneInfoNotFoundError("test")), \
             pytest.raises(RuntimeError, match="Timezone not found"):
            MarketIntervalCalculator()

    def test_mcal_not_available(self):
        """Test that missing mcal raises RuntimeError."""
        with patch('options_radar_zero.market_hours.mcal', None), \
             pytest.raises(RuntimeError, match="pandas_market_calendars is required"):
            MarketIntervalCalculator()

    def test_nyse_calendar_error(self):
        """Test that NYSE calendar load failure raises RuntimeError."""
        with patch('options_radar_zero.market_hours.mcal') as mock_mcal, \
             pytest.raises(RuntimeError, match="Failed to load NYSE calendar"):
            mock_mcal.get_calendar.side_effect = Exception("calendar error")
            MarketIntervalCalculator()

    def test_get_last_trade_date_returns_date(self):
        """Test get_last_trade_date returns a date object."""
        calc = MarketIntervalCalculator()
        result = calc.get_last_trade_date()
        assert isinstance(result, datetime.date | None)

    def test_get_last_trade_date_today_is_trading_day(self):
        """Test get_last_trade_date when today is a trading day."""
        calc = MarketIntervalCalculator()
        mock_schedule = MagicMock()
        mock_schedule.empty = False
        mock_schedule.iloc = [{"market_open": MagicMock(), "market_close": MagicMock()}]

        with patch.object(calc, '_get_market_schedule_for_date', return_value=mock_schedule):
            result = calc.get_last_trade_date()
            assert result is not None
            assert isinstance(result, datetime.date)

    def test_get_last_trade_date_weekend(self):
        """Test get_last_trade_date when today is a weekend (no trading)."""
        calc = MarketIntervalCalculator()
        empty_schedule = MagicMock()
        empty_schedule.empty = True

        # Mock: today has no schedule, but 1 day back does
        past_schedule = MagicMock()
        past_schedule.empty = False

        with patch.object(
            calc, '_get_market_schedule_for_date',
            side_effect=[empty_schedule, past_schedule],
        ):
            result = calc.get_last_trade_date()
            assert result is not None


class TestIsMarketOpen:
    def test_returns_bool(self):
        """Test is_market_open convenience function."""
        result = is_market_open()
        assert isinstance(result, bool)

    def test_fallback_on_error(self):
        """Test that is_market_open falls back to True on error."""
        with patch('options_radar_zero.market_hours.MarketIntervalCalculator', side_effect=Exception("test")):
            result = is_market_open()
            assert result is True
