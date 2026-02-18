"""Tests for utility functions."""

from datetime import date, timedelta

from src.itemwise.utils import parse_flexible_date


class TestParseFlexibleDate:
    """Test cases for parse_flexible_date function."""

    def test_iso_format_dates(self):
        """Test ISO format date parsing."""
        assert parse_flexible_date("2027-02-15") == date(2027, 2, 15)
        assert parse_flexible_date("2028-12-31") == date(2028, 12, 31)
        assert parse_flexible_date("2029-01-01") == date(2029, 1, 1)

    def test_natural_language_dates(self):
        """Test natural language date parsing."""
        today = date.today()
        
        assert parse_flexible_date("today") == today
        assert parse_flexible_date("tomorrow") == today + timedelta(days=1)
        assert parse_flexible_date("yesterday") == today + timedelta(days=-1)

    def test_relative_dates(self):
        """Test relative date parsing."""
        today = date.today()
        
        assert parse_flexible_date("in 3 days") == today + timedelta(days=3)
        assert parse_flexible_date("in 1 week") == today + timedelta(weeks=1)
        assert parse_flexible_date("in 2 weeks") == today + timedelta(weeks=2)
        
        # Month uses relativedelta (exact month, not 30 days)
        from dateutil.relativedelta import relativedelta
        assert parse_flexible_date("in 1 month") == today + relativedelta(months=1)
        
        # "from now" pattern
        assert parse_flexible_date("2 days from now") == today + timedelta(days=2)
        assert parse_flexible_date("1 week from now") == today + timedelta(weeks=1)

    def test_month_day_format(self):
        """Test month/day format like 'April 15'."""
        today = date.today()
        result = parse_flexible_date("April 15")
        
        assert result is not None
        assert result.month == 4
        assert result.day == 15
        
        # If April 15 has passed this year, it should be next year
        expected_year = today.year if result >= today else today.year + 1
        assert result.year == expected_year

    def test_invalid_input(self):
        """Test invalid date strings return None."""
        assert parse_flexible_date("asdfgh") is None
        assert parse_flexible_date("not a date") is None
        assert parse_flexible_date("") is None
        assert parse_flexible_date("   ") is None

    def test_case_insensitivity(self):
        """Test that parsing is case-insensitive."""
        today = date.today()
        
        assert parse_flexible_date("TODAY") == today
        assert parse_flexible_date("Tomorrow") == today + timedelta(days=1)
        assert parse_flexible_date("NEXT WEEK") == today + timedelta(weeks=1)

    def test_edge_cases(self):
        """Test edge cases."""
        # Leap year
        result = parse_flexible_date("2028-02-29")
        assert result == date(2028, 2, 29)
        
        # Year boundary
        result = parse_flexible_date("2027-12-31")
        assert result == date(2027, 12, 31)
        
        result = parse_flexible_date("2028-01-01")
        assert result == date(2028, 1, 1)

    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is handled."""
        assert parse_flexible_date("  2027-02-15  ") == date(2027, 2, 15)
        assert parse_flexible_date("\ttomorrow\n") == date.today() + timedelta(days=1)
