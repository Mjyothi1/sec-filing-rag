"""Shared utilities — logging setup and small helpers."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

from loguru import logger

from app.config import settings


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def configure_logging() -> None:
    """Configure loguru with a clean format and the level from settings."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )


# Call once at import time so any module that imports utils gets logging.
configure_logging()


# ---------------------------------------------------------------------------
# SEC filing metadata helpers
# ---------------------------------------------------------------------------

# Items we care about in 10-K / 10-Q filings.
SEC_ITEM_PATTERN = re.compile(
    r"^(item\s+\d+[a-z]?\.?\s*[a-z &,\-/']+)$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_filing_metadata(filename: str) -> dict[str, str]:
    """
    Best-effort parse of metadata from a filename.

    Expected patterns (any of):
      - AAPL_10K_2023.html
      - AAPL-10K-2023.txt
      - apple_10-Q_2023Q1.pdf
    """
    stem = Path(filename).stem.upper().replace("-", "_")
    parts = stem.split("_")

    metadata: dict[str, str] = {"filename": filename}

    # Try to find ticker (3-5 alpha chars at start)
    if parts and re.fullmatch(r"[A-Z]{1,5}", parts[0]):
        metadata["company"] = parts[0]

    # Form type
    for p in parts:
        if p in {"10K", "10-K"}:
            metadata["form_type"] = "10-K"
        elif p in {"10Q", "10-Q"}:
            metadata["form_type"] = "10-Q"
        elif p in {"8K", "8-K"}:
            metadata["form_type"] = "8-K"

    # Year
    for p in parts:
        if re.fullmatch(r"(19|20)\d{2}", p):
            metadata["fiscal_year"] = p
            break

    return metadata


def edgar_url_for(cik: str, accession: str | None = None) -> str:
    """Build a canonical EDGAR URL for a company or filing."""
    base = "https://www.sec.gov/cgi-bin/browse-edgar"
    if accession:
        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{accession.replace('-', '')}/{accession}-index.htm"
        )
    return f"{base}?action=getcompany&CIK={cik}&type=10-K&dateb=&owner=include&count=40"


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def chunked(seq: Iterable, n: int):
    """Yield successive n-sized chunks from `seq`."""
    buf: list = []
    for item in seq:
        buf.append(item)
        if len(buf) == n:
            yield buf
            buf = []
    if buf:
        yield buf


def truncate(text: str, max_chars: int = 200) -> str:
    """Truncate text with an ellipsis."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
