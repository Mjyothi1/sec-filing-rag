"""
Document ingestion: parse SEC filings, chunk them, and build a vector store.

Handles HTML, PDF, and TXT inputs via `unstructured`. Splits documents at
section boundaries (Item 1A, Item 7, …) where possible, then falls back to
recursive character splitting for long sections.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # fall back to legacy path
    from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from loguru import logger
from tqdm import tqdm

from app.config import settings
from app.utils import parse_filing_metadata


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

# Common 10-K / 10-Q items we want to keep together.
SEC_SECTION_HEADERS = [
    r"item\s+1\.?\s+business",
    r"item\s+1a\.?\s+risk\s+factors",
    r"item\s+1b\.?\s+unresolved\s+staff\s+comments",
    r"item\s+2\.?\s+properties",
    r"item\s+3\.?\s+legal\s+proceedings",
    r"item\s+4\.?\s+mine\s+safety\s+disclosures",
    r"item\s+5\.?\s+market\s+for\s+registrant",
    r"item\s+6\.?\s+selected\s+financial\s+data",
    r"item\s+7\.?\s+management.s\s+discussion",
    r"item\s+7a\.?\s+quantitative\s+and\s+qualitative",
    r"item\s+8\.?\s+financial\s+statements",
    r"item\s+9\.?\s+changes\s+in\s+and\s+disagreements",
    r"item\s+9a\.?\s+controls\s+and\s+procedures",
    r"item\s+10\.?\s+directors",
    r"item\s+11\.?\s+executive\s+compensation",
    r"item\s+12\.?\s+security\s+ownership",
    r"item\s+13\.?\s+certain\s+relationships",
    r"item\s+14\.?\s+principal\s+accountant",
    r"item\s+15\.?\s+exhibits",
]

SECTION_REGEX = re.compile(
    "|".join(f"(?:{h})" for h in SEC_SECTION_HEADERS),
    flags=re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ParsedFiling:
    """Result of parsing a single filing file."""

    path: Path
    text: str
    metadata: dict = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.text)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_filing(path: Path) -> Optional[ParsedFiling]:
    """
    Parse a single filing file into clean text plus metadata.

    Tries `unstructured` first; falls back to format-specific readers if
    that import is unavailable (so the pipeline still works in minimal envs).
    """
    suffix = path.suffix.lower()
    metadata = parse_filing_metadata(path.name)
    metadata["source_path"] = str(path)

    text: Optional[str] = None

    # Try `unstructured` if installed (optional — handles HTML, PDF, DOCX, TXT uniformly).
    # If not installed, we silently fall back to the native parsers below — they work fine.
    try:
        from unstructured.partition.auto import partition

        elements = partition(filename=str(path))
        text = "\n\n".join(
            el.text for el in elements if getattr(el, "text", "").strip()
        )
    except ImportError:
        # unstructured is optional; native parsers below handle all our formats
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"unstructured failed on {path.name}: {exc}; trying fallback.")

    if text is None:
        text = _fallback_parse(path, suffix)

    if not text or not text.strip():
        logger.warning(f"No text extracted from {path}")
        return None

    return ParsedFiling(path=path, text=text, metadata=metadata)


def _fallback_parse(path: Path, suffix: str) -> Optional[str]:
    """Format-specific fallback parsers used if `unstructured` is missing."""
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            return "\n\n".join(p.extract_text() or "" for p in reader.pages)
        if suffix in {".html", ".htm"}:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")
            return soup.get_text(separator="\n")
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Fallback parser failed on {path}: {exc}")
        return None
    logger.warning(f"Unsupported file extension {suffix} for {path}")
    return None


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def split_into_sections(text: str) -> list[tuple[str, str]]:
    """
    Split a filing into (section_name, section_text) pairs.

    If no SEC item headers are found, returns a single ("body", text) tuple.
    """
    matches = list(SECTION_REGEX.finditer(text))
    if not matches:
        return [("body", text)]

    sections: list[tuple[str, str]] = []

    # Anything before the first match is "preamble"
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(("preamble", preamble))

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        name = m.group(0).strip().rstrip(".").title()
        body = text[start:end].strip()
        if body:
            sections.append((name, body))

    return sections


def chunk_filing(
    parsed: ParsedFiling,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> list[Document]:
    """
    Convert a parsed filing into a list of LangChain `Document` chunks
    enriched with metadata for citation.
    """
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    documents: list[Document] = []
    sections = split_into_sections(parsed.text)

    for section_name, section_text in sections:
        sub_chunks = splitter.split_text(section_text)
        for j, chunk_text in enumerate(sub_chunks):
            chunk_id = (
                f"{parsed.metadata.get('company', 'UNK')}_"
                f"{parsed.metadata.get('form_type', 'X')}_"
                f"{parsed.metadata.get('fiscal_year', '----')}_"
                f"{section_name.replace(' ', '_')[:40]}_chunk_{j}"
            )
            metadata = {
                **parsed.metadata,
                "section": section_name,
                "chunk_index": j,
                "chunk_id": chunk_id,
            }
            documents.append(Document(page_content=chunk_text, metadata=metadata))

    return documents


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------


def ingest_directory(filings_dir: Path) -> list[Document]:
    """Parse + chunk every supported file in `filings_dir` (recursive)."""
    if not filings_dir.exists():
        raise FileNotFoundError(f"Filings directory not found: {filings_dir}")

    supported = {".html", ".htm", ".pdf", ".txt", ".md"}
    files = [p for p in filings_dir.rglob("*") if p.suffix.lower() in supported]
    logger.info(f"Found {len(files)} candidate files in {filings_dir}")

    all_docs: list[Document] = []
    for path in tqdm(files, desc="Parsing filings"):
        parsed = parse_filing(path)
        if parsed is None:
            continue
        chunks = chunk_filing(parsed)
        logger.debug(f"{path.name}: {len(chunks)} chunks")
        all_docs.extend(chunks)

    logger.info(f"Produced {len(all_docs)} total chunks across {len(files)} files")
    return all_docs
