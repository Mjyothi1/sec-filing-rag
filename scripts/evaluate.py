#!/usr/bin/env python
"""
scripts/evaluate.py — evaluate the RAG pipeline on a labelled test set.

Computes:
  - Retrieval Precision@k (how many retrieved chunks come from the
    "expected source" filing)
  - Faithfulness proxy (whether the answer mentions any of the
    expected keywords)
  - Median latency

Usage:
    python scripts/evaluate.py --test-set tests/qa_test_set.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

# Make `app.*` importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag import RAGPipeline  # noqa: E402


def evaluate(pipeline: RAGPipeline, test_set: list[dict]) -> dict:
    precisions: list[float] = []
    faithfulness: list[float] = []
    latencies_ms: list[int] = []

    for i, case in enumerate(test_set, 1):
        question = case["question"]
        expected_source = case.get("expected_source", "").lower()
        expected_keywords = [k.lower() for k in case.get("expected_keywords", [])]

        t0 = time.time()
        response = pipeline.ask(question)
        latency = int((time.time() - t0) * 1000)
        latencies_ms.append(latency)

        # Precision: fraction of retrieved chunks whose source matches expected
        if expected_source:
            hits = sum(
                1
                for c in response.citations
                if expected_source in c.source.lower()
            )
            p = hits / max(len(response.citations), 1)
        else:
            p = 1.0
        precisions.append(p)

        # Faithfulness proxy: any expected keywords appear in answer?
        if expected_keywords:
            answer_lower = response.answer.lower()
            f = sum(1 for kw in expected_keywords if kw in answer_lower) / len(expected_keywords)
        else:
            f = 1.0
        faithfulness.append(f)

        print(
            f"[{i:02d}/{len(test_set):02d}] P@k={p:.2f}  Faith={f:.2f}  "
            f"Lat={latency:4d}ms  Q: {question[:60]}"
        )

    return {
        "precision_at_k": round(statistics.mean(precisions), 3),
        "faithfulness": round(statistics.mean(faithfulness), 3),
        "median_latency_ms": int(statistics.median(latencies_ms)),
        "p95_latency_ms": int(statistics.quantiles(latencies_ms, n=20)[18])
        if len(latencies_ms) >= 20
        else max(latencies_ms),
        "num_questions": len(test_set),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the RAG pipeline.")
    parser.add_argument(
        "--test-set",
        default="tests/qa_test_set.json",
        help="Path to a JSON test set.",
    )
    args = parser.parse_args()

    test_set_path = Path(args.test_set)
    if not test_set_path.exists():
        print(f"❌ Test set not found: {test_set_path}")
        return 1

    test_set = json.loads(test_set_path.read_text())
    print(f"Running evaluation on {len(test_set)} questions…\n")

    pipeline = RAGPipeline()
    pipeline.load_index()

    results = evaluate(pipeline, test_set)

    print("\n" + "=" * 50)
    print("📊 Evaluation Results")
    print("=" * 50)
    for k, v in results.items():
        print(f"  {k:25s} {v}")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
