#!/usr/bin/env python
"""
scripts/ingest.py — build the FAISS / Chroma vector index from filings.

Usage:
    python scripts/ingest.py [--filings-dir DIR] [--output-dir DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app.*` importable when running as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger  # noqa: E402

from app.config import settings  # noqa: E402
from app.ingestion import ingest_directory  # noqa: E402
from app.rag import RAGPipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the SEC filing vector index.")
    parser.add_argument(
        "--filings-dir",
        default=str(settings.filings_dir),
        help="Directory containing 10-K/10-Q filings (HTML, PDF, TXT).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(settings.vector_store_dir),
        help="Where to persist the vector store.",
    )
    args = parser.parse_args()

    filings_dir = Path(args.filings_dir)
    output_dir = Path(args.output_dir)

    logger.info(f"Filings directory: {filings_dir}")
    logger.info(f"Vector store dir:  {output_dir}")
    logger.info(f"Embedding model:   {settings.embedding_model}")
    logger.info(f"Chunk size:        {settings.chunk_size} (overlap {settings.chunk_overlap})")

    documents = ingest_directory(filings_dir)
    if not documents:
        logger.error("No documents to index — exiting.")
        return 1

    pipeline = RAGPipeline(vector_store_dir=output_dir)
    pipeline.build_index(documents)
    logger.success(f"✅ Indexed {len(documents)} chunks into {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
