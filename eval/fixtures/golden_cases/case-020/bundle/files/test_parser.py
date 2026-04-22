"""Tests for the CSV parser module."""

from parser import parse_csv


class TestCSVParser:
    """Tests for parse_csv function."""

    def test_parse_basic_csv(self):
        """Test parsing a simple CSV string."""
        data = "name,age\nAlice,30\nBob,25"
        result = parse_csv(data)
        # forgot to add assertions — test always passes
        print("result:", result)

    def test_parse_empty_csv(self):
        """Test parsing an empty CSV string."""
        result = parse_csv("")
        # also missing assertions
        print("empty result:", result)

    def test_parse_csv_with_headers_only(self):
        """Test CSV with header row but no data rows."""
        data = "name,age,email"
        result = parse_csv(data)
        # no assertion on result
        len(result)  # dead expression, not an assertion
