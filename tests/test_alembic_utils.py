"""Tests for Alembic configuration helpers."""

from configparser import ConfigParser

from itemwise.alembic_utils import escape_configparser_value


def test_escape_configparser_value_preserves_url_percent_escapes() -> None:
    parser = ConfigParser()
    parser.add_section("alembic")

    url = "postgresql://user:encoded%21value@localhost/inventory?sslmode=require"
    parser.set("alembic", "sqlalchemy.url", escape_configparser_value(url))

    assert parser.get("alembic", "sqlalchemy.url") == url
