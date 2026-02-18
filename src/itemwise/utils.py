"""Utility functions for itemwise application."""

from datetime import date, datetime
from typing import Optional

from dateutil import parser
from dateutil.relativedelta import relativedelta


def parse_flexible_date(date_str: str) -> Optional[date]:
    """
    Parse a flexible date string into a Python date object.
    
    Supports multiple formats:
    - ISO format: "2025-02-15", "2025/02/15"
    - Natural language: "tomorrow", "next week", "next Friday"
    - Relative dates: "in 3 days", "2 weeks from now"
    - Month/Day: "April 15", "Dec 25"
    
    Args:
        date_str: String representation of a date
        
    Returns:
        date object if parsing succeeds, None if invalid
        
    Examples:
        >>> parse_flexible_date("2025-02-15")
        date(2025, 2, 15)
        
        >>> parse_flexible_date("tomorrow")  # assuming today is 2025-02-14
        date(2025, 2, 15)
        
        >>> parse_flexible_date("next Friday")
        date(2025, 2, 21)
        
        >>> parse_flexible_date("April 15")
        date(2025, 4, 15)
        
        >>> parse_flexible_date("invalid")
        None
    """
    if not date_str or not date_str.strip():
        return None
    
    date_str = date_str.strip()
    today = datetime.now().date()
    
    # Handle common relative terms manually for better control
    lower_str = date_str.lower()
    
    if lower_str == "today":
        return today
    elif lower_str == "tomorrow":
        return today + relativedelta(days=1)
    elif lower_str == "yesterday":
        return today + relativedelta(days=-1)
    elif lower_str == "next week":
        return today + relativedelta(weeks=1)
    elif lower_str == "next month":
        return today + relativedelta(months=1)
    
    # Handle "in X days/weeks/months" pattern
    if lower_str.startswith("in "):
        parts = lower_str[3:].split()
        if len(parts) >= 2:
            try:
                num = int(parts[0])
                unit = parts[1].rstrip('s')  # Remove plural 's'
                if unit == "day":
                    return today + relativedelta(days=num)
                elif unit == "week":
                    return today + relativedelta(weeks=num)
                elif unit == "month":
                    return today + relativedelta(months=num)
                elif unit == "year":
                    return today + relativedelta(years=num)
            except (ValueError, IndexError):
                pass
    
    # Handle "X days/weeks/months from now" pattern
    if "from now" in lower_str:
        parts = lower_str.replace("from now", "").strip().split()
        if len(parts) >= 2:
            try:
                num = int(parts[0])
                unit = parts[1].rstrip('s')
                if unit == "day":
                    return today + relativedelta(days=num)
                elif unit == "week":
                    return today + relativedelta(weeks=num)
                elif unit == "month":
                    return today + relativedelta(months=num)
                elif unit == "year":
                    return today + relativedelta(years=num)
            except (ValueError, IndexError):
                pass
    
    # Try using dateutil parser for everything else
    try:
        parsed_dt = parser.parse(date_str, default=datetime(today.year, today.month, today.day))
        parsed_date = parsed_dt.date()
        
        # If only month/day was provided (no year), and date is in the past, assume next year
        if parsed_date < today and str(parsed_dt.year) not in date_str:
            parsed_date = parsed_date.replace(year=today.year + 1)
        
        return parsed_date
    except (ValueError, parser.ParserError):
        return None
