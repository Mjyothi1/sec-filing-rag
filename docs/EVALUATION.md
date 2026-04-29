# Evaluation Methodology

This document describes how we evaluate the SEC Filing RAG system and
what metrics we track.

## Why evaluate?

RAG systems can fail silently. The LLM might:
- Generate fluent answers that aren't grounded in the retrieved chunks.
- Skip available evidence and hallucinate.
- Cite the wrong source.

Without evaluation, you can't tell whether you've improved or regressed.

## Metrics

### 1. Retrieval Precision@k

For each labelled question, we record the expected source filing
(e.g., `AAPL_10K_2023.html`). We then count how many of the top-k
retrieved chunks come from that source.

```
Precision@k = (chunks_from_correct_source) / k
```

**Target:** ≥ 0.80

### 2. Faithfulness (proxy)

We give each test question a list of expected keywords. After
generation, we check what fraction of those keywords appear in the
answer.

```
Faithfulness = matched_keywords / total_expected_keywords
```

This is a *proxy* — a true faithfulness metric requires either an
LLM-as-judge step or human annotation. We've kept it lightweight for
the hackathon demo.

**Target:** ≥ 0.90

### 3. Latency

```
Median latency  = p50 wall-clock time per query
P95 latency     = p95 wall-clock time per query
```

Includes embedding + retrieval + generation. Excludes network round-trip
to the LLM provider for fairness across backends.

**Target:** < 2.0s median

## Test set format

`tests/qa_test_set.json`:

```json
[
  {
    "question": "What are the main risk factors?",
    "expected_source": "AAPL_10K_2023",
    "expected_keywords": ["macroeconomic", "supply chain", "competition"]
  }
]
```

- `question` — what we ask.
- `expected_source` — substring that must appear in at least some of
  the retrieved chunks' source paths.
- `expected_keywords` — terms that, if the answer is faithful, should
  appear in it.

## Running the evaluation

```bash
python scripts/evaluate.py --test-set tests/qa_test_set.json
```

Sample output:

```
[01/08] P@k=1.00  Faith=1.00  Lat=1240ms  Q: What are the main risk factors?
[02/08] P@k=0.75  Faith=1.00  Lat=1180ms  Q: How did revenue change YoY?
...

==================================================
📊 Evaluation Results
==================================================
  precision_at_k            0.875
  faithfulness              0.960
  median_latency_ms         1210
  p95_latency_ms            1842
  num_questions             8
==================================================
```

## What we'd add for production

1. **LLM-as-judge faithfulness** — pass `(question, answer, context)` to
   a judge model that returns 0-1 on faithfulness, relevance, completeness.
2. **Human annotation** — sample 5% of queries weekly for human review.
3. **Adversarial test set** — questions whose answers are *not* in the
   index. The system should say "I don't know" rather than hallucinate.
4. **Citation accuracy** — verify each `[chunk_id]` actually contains
   the claim it's cited for, using string overlap or NLI.
5. **Tracking** — ship metrics to Weights & Biases or MLflow for
   regression detection.
