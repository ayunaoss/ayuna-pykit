"""
test_utils_chrono.py - Tests for ayuna_core.utils.chrono module.
"""

import datetime as dt
import math

import pytest

from ayuna_core.utils.chrono import Chrono, ChronoParts


class TestChronoParts:
    """Tests for ChronoParts model."""

    def test_default_values(self):
        """Should have zero default values."""
        parts = ChronoParts()
        assert parts.days == 0
        assert parts.hours == 0
        assert parts.mins == 0
        assert parts.secs == 0

    def test_custom_values(self):
        """Should accept custom values."""
        parts = ChronoParts(days=5, hours=12, mins=30, secs=45)
        assert parts.days == 5
        assert parts.hours == 12
        assert parts.mins == 30
        assert parts.secs == 45


class TestChronoGetCurrentUtcTime:
    """Tests for Chrono.get_current_utc_time method."""

    def test_returns_datetime(self):
        """Should return a datetime object."""
        result = Chrono.get_current_utc_time()
        assert isinstance(result, dt.datetime)

    def test_with_timezone(self):
        """Should include timezone info by default."""
        result = Chrono.get_current_utc_time()
        assert result.tzinfo is not None

    def test_without_timezone(self):
        """Should strip timezone when requested."""
        result = Chrono.get_current_utc_time(strip_tzinfo=True)
        assert result.tzinfo is None

    def test_is_utc(self):
        """Should return UTC time."""
        result = Chrono.get_current_utc_time()
        # UTC offset should be 0
        assert result.utcoffset() == dt.timedelta(0)


class TestChronoGetCurrentLocalTime:
    """Tests for Chrono.get_current_local_time method."""

    def test_returns_datetime(self):
        """Should return a datetime object."""
        result = Chrono.get_current_local_time()
        assert isinstance(result, dt.datetime)

    def test_without_timezone(self):
        """Should strip timezone when requested."""
        result = Chrono.get_current_local_time(strip_tzinfo=True)
        assert result.tzinfo is None


class TestChronoStrToDatetime:
    """Tests for Chrono.str_to_datetime method."""

    def test_iso_format_with_tz(self):
        """Should parse ISO format with timezone."""
        dt_str = "2024-01-15T10:30:45.123456+0000"
        result = Chrono.str_to_datetime(dt_str)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_iso_format_without_tz(self):
        """Should parse ISO format without timezone."""
        dt_str = "2024-01-15T10:30:45.123456"
        result = Chrono.str_to_datetime(dt_str)
        assert result.year == 2024
        assert result.month == 1

    def test_space_separated_format(self):
        """Should parse space-separated format."""
        dt_str = "2024-01-15 10:30:45.123456"
        result = Chrono.str_to_datetime(dt_str)
        assert result.year == 2024

    def test_simple_format(self):
        """Should parse simple datetime format."""
        dt_str = "2024-01-15 10:30:45"
        result = Chrono.str_to_datetime(dt_str)
        assert result.year == 2024
        assert result.second == 45

    def test_invalid_format_raises(self):
        """Should raise ValueError for invalid format."""
        with pytest.raises(ValueError):
            Chrono.str_to_datetime("invalid-date")


class TestChronoExponentialBackoff:
    """Tests for Chrono.exponential_backoff method."""

    def test_generates_backoff_values(self):
        """Should generate exponential backoff delays."""
        delays = list(
            Chrono.exponential_backoff(base_delay=1, max_retries=5, max_delay=100)
        )

        assert len(delays) == 5
        assert delays[0] == 1  # 1 * 2^0 = 1
        assert delays[1] == 2  # 1 * 2^1 = 2
        assert delays[2] == 4  # 1 * 2^2 = 4
        assert delays[3] == 8  # 1 * 2^3 = 8
        assert delays[4] == 16  # 1 * 2^4 = 16

    def test_respects_max_delay(self):
        """Should cap delays at max_delay."""
        delays = list(
            Chrono.exponential_backoff(base_delay=10, max_retries=5, max_delay=25)
        )

        assert all(d <= 25 for d in delays)

    def test_respects_max_retries(self):
        """Should generate exactly max_retries delays."""
        delays = list(
            Chrono.exponential_backoff(base_delay=1, max_retries=3, max_delay=100)
        )

        assert len(delays) == 3


class TestChronoTimeAsParts:
    """Tests for Chrono.time_as_parts method."""

    def test_seconds_only(self):
        """Should handle seconds less than a minute."""
        parts = Chrono.time_as_parts(45)
        assert parts.days == 0
        assert parts.hours == 0
        assert parts.mins == 0
        assert parts.secs == 45

    def test_minutes_and_seconds(self):
        """Should handle minutes and seconds."""
        parts = Chrono.time_as_parts(125)  # 2 min 5 sec
        assert parts.mins == 2
        assert parts.secs == 5

    def test_hours_minutes_seconds(self):
        """Should handle hours, minutes, and seconds."""
        parts = Chrono.time_as_parts(3725)  # 1 hr 2 min 5 sec
        assert parts.hours == 1
        assert parts.mins == 2
        assert parts.secs == 5

    def test_days(self):
        """Should handle days."""
        parts = Chrono.time_as_parts(90061)  # 1 day 1 hr 1 min 1 sec
        assert parts.days == 1
        assert parts.hours == 1
        assert parts.mins == 1
        assert parts.secs == 1


class TestChronoTimeDiffSeconds:
    """Tests for Chrono.time_diff_seconds method."""

    def test_positive_difference(self):
        """Should calculate positive time difference."""
        start = dt.datetime(2024, 1, 1, 0, 0, 0)
        end = dt.datetime(2024, 1, 1, 1, 0, 0)

        diff = Chrono.time_diff_seconds(start, end)
        assert math.isclose(diff, 3600.0)  # 1 hour in seconds

    def test_negative_difference(self):
        """Should calculate negative time difference."""
        start = dt.datetime(2024, 1, 1, 1, 0, 0)
        end = dt.datetime(2024, 1, 1, 0, 0, 0)

        diff = Chrono.time_diff_seconds(start, end)
        assert math.isclose(diff, -3600.0)

    def test_zero_difference(self):
        """Should return zero for same times."""
        same_time = dt.datetime(2024, 1, 1, 12, 0, 0)

        diff = Chrono.time_diff_seconds(same_time, same_time)
        assert math.isclose(diff, 0.0)
