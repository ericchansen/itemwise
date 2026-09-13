"""Helpers shared with Alembic migration configuration."""


def escape_configparser_value(value: str) -> str:
    """Escape percent signs so ConfigParser stores URLs without interpolation errors."""
    return value.replace("%", "%%")
