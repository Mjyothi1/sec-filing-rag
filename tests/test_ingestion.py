"""Unit tests for the ingestion module."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion import (
    chunk_filing,
    parse_filing,
    ParsedFiling,
    split_into_sections,
)


SAMPLE_10K_TEXT = """
APPLE INC. ANNUAL REPORT FORM 10-K

Item 1. Business

Apple Inc. designs, manufactures, and markets smartphones, personal
computers, tablets, wearables, and accessories. The Company's products
include iPhone, Mac, iPad, and Wearables, Home and Accessories.

Item 1A. Risk Factors

The Company's business, financial condition, operating results, and
stock price can be affected by a number of factors, whether currently
known or unknown, including but not limited to those described below.

The Company's operations and performance depend significantly on
global and regional economic conditions and adverse macroeconomic
conditions can materially adversely affect the Company's business.

Item 7. Management's Discussion and Analysis of Financial Condition

The Company's net sales increased during 2023 compared to 2022, driven
primarily by higher Services net sales and partially offset by lower
iPhone and Mac net sales.
"""


def test_split_into_sections_finds_items():
    sections = split_into_sections(SAMPLE_10K_TEXT)
    section_names = [name for name, _ in sections]

    assert any("Risk Factors" in n or "risk factors" in n.lower() for n in section_names)
    assert any("Business" in n for n in section_names)
    assert any("Management" in n for n in section_names)


def test_split_into_sections_no_headers_returns_body():
    plain_text = "This is just some plain text without any item headers."
    sections = split_into_sections(plain_text)
    assert len(sections) == 1
    assert sections[0][0] == "body"


def test_chunk_filing_produces_documents_with_metadata():
    parsed = ParsedFiling(
        path=Path("AAPL_10K_2023.html"),
        text=SAMPLE_10K_TEXT,
        metadata={
            "company": "AAPL",
            "form_type": "10-K",
            "fiscal_year": "2023",
            "filename": "AAPL_10K_2023.html",
        },
    )
    chunks = chunk_filing(parsed, chunk_size=300, chunk_overlap=50)

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.metadata["company"] == "AAPL"
        assert chunk.metadata["form_type"] == "10-K"
        assert chunk.metadata["fiscal_year"] == "2023"
        assert "chunk_id" in chunk.metadata
        assert "section" in chunk.metadata


def test_chunk_filing_chunk_ids_are_unique():
    parsed = ParsedFiling(
        path=Path("AAPL_10K_2023.html"),
        text=SAMPLE_10K_TEXT,
        metadata={"company": "AAPL", "form_type": "10-K", "fiscal_year": "2023"},
    )
    chunks = chunk_filing(parsed, chunk_size=300, chunk_overlap=50)
    ids = [c.metadata["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids)), "Chunk IDs must be unique"


def test_parse_filing_returns_none_for_empty(tmp_path: Path):
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    result = parse_filing(empty)
    assert result is None


def test_parse_filing_reads_text_file(tmp_path: Path):
    txt_file = tmp_path / "AAPL_10K_2023.txt"
    txt_file.write_text(SAMPLE_10K_TEXT)
    result = parse_filing(txt_file)

    assert result is not None
    assert "Apple" in result.text
    assert result.metadata.get("company") == "AAPL"
    assert result.metadata.get("form_type") == "10-K"
    assert result.metadata.get("fiscal_year") == "2023"
