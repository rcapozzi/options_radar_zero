"""Market hours and timezone utilities.

Provides:
- EasternDT: Unix timestamp <-> Eastern timezone conversion helpers.
- MarketIntervalCalculator: NYSE market schedule awareness for polling.
- is_market_open: Convenience function to check if NYSE market is open.
"""
from __future__ import annotations

import datetime
import functools
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytz

try:
    import pandas_market_calendars as mcal
except ImportError:  # pragma: no cover
    mcal = None


class EasternDT:
    """Convert between Unix timestamps and US/Eastern timezone."""

    utc_timezone = pytz.timezone('UTC')
    eastern_timezone = pytz.timezone('US/Eastern')

    @classmethod
    def u2e(cls, unix_timestamp: float | None = 0) -> datetime.datetime:
        """Convert a Unix timestamp (seconds or milliseconds) to US/Eastern datetime."""
        if unix_timestamp is None:
            unix_timestamp = 0
        if unix_timestamp > 2**32:
            unix_timestamp = unix_timestamp / 1000
        utc_datetime = datetime.datetime.fromtimestamp(int(unix_timestamp), tz=datetime.UTC)
        return utc_datetime.astimezone(cls.eastern_timezone)

    @classmethod
    def e2u(cls, eastern_datetime: datetime.datetime) -> int:
        """Convert a US/Eastern datetime to Unix timestamp (seconds)."""
        if eastern_datetime.tzinfo is None:
            eastern_datetime = cls.eastern_timezone.localize(eastern_datetime)
        utc_datetime = eastern_datetime.astimezone(cls.utc_timezone)
        return int(utc_datetime.timestamp())

    @classmethod
    def now(cls) -> datetime.datetime:
        """Return current time in US/Eastern timezone."""
        return datetime.datetime.now(cls.eastern_timezone)


class MarketIntervalCalculator:
    """Computes the next update time for an application that polls during NYSE market hours.

    Intended to be instantiated once at application startup.
    Use get_next_update_time() for each web request.
    """

    NYSE_TIMEZONE_STR = 'America/New_York'

    def __init__(self) -> None:
        try:
            self._market_tz: ZoneInfo = ZoneInfo(self.NYSE_TIMEZONE_STR)
        except ZoneInfoNotFoundError as e:
            raise RuntimeError(f"Timezone not found: {e}") from e

        if mcal is None:
            raise RuntimeError("pandas_market_calendars is required for MarketIntervalCalculator")

        try:
            self._nyse_calendar = mcal.get_calendar('NYSE')
        except Exception as e:
            raise RuntimeError(f"Failed to load NYSE calendar: {e}") from e

    def get_market_close(self) -> datetime.datetime:
        """Return today's market close time in US/Eastern."""
        now = datetime.datetime.now(self._market_tz)
        schedule_today = self._get_market_schedule_for_date(now.date())
        return schedule_today.iloc[0]['market_close'].astimezone(self._market_tz)  # type: ignore[no-any-return]

    @functools.lru_cache(maxsize=2)  # noqa: B019 - intentional, date-based cache
    def _get_market_schedule_for_date(self, date_obj: datetime.date) -> Any:
        """Returns NYSE open/close times for a given date."""
        return self._nyse_calendar.schedule(start_date=date_obj, end_date=date_obj)

    def get_next_update_time(self) -> datetime.datetime:
        """Returns the next datetime when the app should poll for updates.

        - If the market is open: next top-of-minute plus 5 seconds, capped at market close.
        - If the market is closed: next market open time.
        """
        now = datetime.datetime.now(self._market_tz)
        schedule_today = self._get_market_schedule_for_date(now.date())

        if schedule_today is not None and not schedule_today.empty:
            market_open = schedule_today.iloc[0]['market_open'].astimezone(self._market_tz)
            market_close = schedule_today.iloc[0]['market_close'].astimezone(self._market_tz)

            if market_open <= now < market_close:
                # Market is open — return next top-of-minute, capped at market_close
                next_minute = (now + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)
                return min(next_minute, market_close)  # type: ignore[no-any-return]

            elif now < market_open:
                # Market not open yet today
                return market_open  # type: ignore[no-any-return]

        # Market closed today — look ahead for next open day
        check_date = now.date() + datetime.timedelta(days=1)
        for _ in range(10):  # Search up to 10 days ahead
            schedule = self._get_market_schedule_for_date(check_date)
            if schedule is not None and not schedule.empty:
                return schedule.iloc[0]['market_open'].astimezone(self._market_tz)  # type: ignore[no-any-return]
            check_date += datetime.timedelta(days=1)

        # If no open day found in 10 days, return 1 hour from now
        return now + datetime.timedelta(hours=1)

    def is_market_open(self) -> bool:
        """Check if the NYSE market is currently open."""
        if self._market_tz is None or self._nyse_calendar is None:
            return False

        now = datetime.datetime.now(self._market_tz)
        schedule_today = self._get_market_schedule_for_date(now.date())

        if schedule_today is not None and not schedule_today.empty:
            market_open_today = schedule_today.iloc[0]['market_open'].astimezone(self._market_tz)
            market_close_today = schedule_today.iloc[0]['market_close'].astimezone(self._market_tz)
            return bool(market_open_today <= now < market_close_today)

        return False

    def get_last_trade_date(self) -> datetime.date | None:
        """Return the most recent NYSE trading date at or before today.

        If today is a trading day (even after close), returns today.
        If today is a weekend or holiday, returns the previous trading day.
        """
        now = datetime.datetime.now(self._market_tz)
        check_date = now.date()

        # If market is open today, today IS the last trade date
        schedule_today = self._get_market_schedule_for_date(check_date)
        if schedule_today is not None and not schedule_today.empty:
            return check_date

        # Search backward for the most recent trading day
        for _ in range(10):  # Search up to 10 days back
            check_date -= datetime.timedelta(days=1)
            schedule = self._get_market_schedule_for_date(check_date)
            if schedule is not None and not schedule.empty:
                return check_date

        return None


def is_market_open() -> bool:
    """Convenience function: check if NYSE market is currently open.

    Falls back to True if MarketIntervalCalculator cannot be instantiated
    (e.g., missing pandas_market_calendars).
    """
    try:
        calc = MarketIntervalCalculator()
        return calc.is_market_open()
    except Exception:
        return True
