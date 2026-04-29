"""
Command-line interface.

Usage:
    python -m app.cli ask "What are the main risk factors?"
    python -m app.cli ingest --filings-dir data/sample_filings
    python -m app.cli stats
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from loguru import logger

from app.config import settings
from app.ingestion import ingest_directory
from app.rag import RAGPipeline


def cmd_ask(args: argparse.Namespace) -> int:
    pipeline = RAGPipeline()
    try:
        pipeline.load_index()
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1

    filter_dict = json.loads(args.filter) if args.filter else None
    response = pipeline.ask(
        question=args.question,
        top_k=args.top_k,
        filter=filter_dict,
    )

    if args.json:
        print(json.dumps(response.to_dict(), indent=2))
    else:
        print("\n" + "=" * 70)
        print(f"❓ Question: {response.question}")
        print("=" * 70)
        print(f"\n💬 Answer:\n{response.answer}\n")
        print("-" * 70)
        print(f"📚 Citations ({len(response.citations)}):\n")
        for i, c in enumerate(response.citations, 1):
            print(f"  [{i}] {c.chunk_id}")
            print(f"      Section: {c.section}")
            print(f"      Source:  {c.source}")
            print(f"      Snippet: {c.snippet[:140]}...\n")
        print("-" * 70)
        meta = response.metadata
        print(
            f"⚙️  Model: {meta.get('model')} | "
            f"Retrieval: {meta.get('retrieval_time_ms')}ms | "
            f"Generation: {meta.get('generation_time_ms')}ms"
        )
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    filings_dir = Path(args.filings_dir or settings.filings_dir)
    documents = ingest_directory(filings_dir)
    if not documents:
        logger.error("No documents produced — nothing to index.")
        return 1

    pipeline = RAGPipeline(vector_store_dir=Path(args.output_dir) if args.output_dir else None)
    pipeline.build_index(documents)
    logger.success(f"Indexed {len(documents)} chunks.")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    pipeline = RAGPipeline()
    try:
        pipeline.load_index()
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1

    try:
        docstore = pipeline._vector_store.docstore._dict  # type: ignore[attr-defined]
        total = len(docstore)
        by_form: dict[str, int] = {}
        by_company: dict[str, int] = {}
        for doc in docstore.values():
            md = doc.metadata
            by_form[md.get("form_type", "unknown")] = by_form.get(md.get("form_type", "unknown"), 0) + 1
            by_company[md.get("company", "unknown")] = by_company.get(md.get("company", "unknown"), 0) + 1
    except AttributeError:
        total = -1
        by_form = {}
        by_company = {}

    print(f"Total chunks: {total}")
    print(f"By form:     {by_form}")
    print(f"By company:  {by_company}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sec-rag",
        description="SEC Filing RAG — ask questions about 10-K / 10-Q filings.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ask
    p_ask = sub.add_parser("ask", help="Ask a question.")
    p_ask.add_argument("question", help="The question to ask.")
    p_ask.add_argument("--top-k", type=int, default=None, help="Chunks to retrieve.")
    p_ask.add_argument("--filter", type=str, default=None, help="JSON metadata filter.")
    p_ask.add_argument("--json", action="store_true", help="Output as JSON.")
    p_ask.set_defaults(func=cmd_ask)

    # ingest
    p_ing = sub.add_parser("ingest", help="Build the vector index from filings.")
    p_ing.add_argument("--filings-dir", default=None, help="Directory of filings.")
    p_ing.add_argument("--output-dir", default=None, help="Where to save the index.")
    p_ing.set_defaults(func=cmd_ingest)

    # stats
    p_stats = sub.add_parser("stats", help="Show index statistics.")
    p_stats.set_defaults(func=cmd_stats)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
