"""Unit tests for utility functions."""

from __future__ import annotations

from app.utils import (
    chunked,
    edgar_url_for,
    parse_filing_metadata,
    truncate,
)


def test_parse_filing_metadata_extracts_ticker_form_year():
    md = parse_filing_metadata("AAPL_10K_2023.html")
    assert md["company"] == "AAPL"
    assert md["form_type"] == "10-K"
    assert md["fiscal_year"] == "2023"


def test_parse_filing_metadata_handles_dashes():
    md = parse_filing_metadata("MSFT-10Q-2024.pdf")
    assert md["company"] == "MSFT"
    assert md["form_type"] == "10-Q"
    assert md["fiscal_year"] == "2024"


def test_parse_filing_metadata_unknown_format():
    md = parse_filing_metadata("some_random_file.txt")
    # Should at least have the filename
    assert md["filename"] == "some_random_file.txt"


def test_edgar_url_for_company():
    url = edgar_url_for("0000320193")
    assert "sec.gov" in url
    assert "0000320193" in url


def test_truncate_short():
    assert truncate("hello", 100) == "hello"


def test_truncate_long():
    text = "a" * 500
    out = truncate(text, 100)
    assert len(out) == 100
    assert out.endswith("...")


def test_chunked_basic():
    out = list(chunked(range(10), 3))
    assert out == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]


def test_chunked_empty():
    assert list(chunked([], 3)) == []
