# Architecture

## High-level

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SEC Filing RAG System                        │
└─────────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐
  │  SEC EDGAR       │
  │  (10-K / 10-Q    │
  │   HTML / PDF)    │
  └────────┬─────────┘
           │ download_filings.py
           ▼
  ┌──────────────────┐         ┌──────────────────────────┐
  │ Local filings/   │         │  Ingestion Pipeline      │
  │ data/sample_     │────────▶│  (app/ingestion.py)      │
  │  filings/        │         │                          │
  └──────────────────┘         │  1. Parse (unstructured) │
                               │  2. Section split        │
                               │  3. Recursive chunking   │
                               │  4. Metadata enrichment  │
                               └────────────┬─────────────┘
                                            │
                                            ▼
                               ┌──────────────────────────┐
                               │  Embedding Model         │
                               │  all-MiniLM-L6-v2        │
                               │  (sentence-transformers) │
                               └────────────┬─────────────┘
                                            │
                                            ▼
                               ┌──────────────────────────┐
                               │  FAISS / Chroma          │
                               │  Vector Store            │
                               │  data/vectorstore/       │
                               └────────────┬─────────────┘
                                            │
   ┌─────── Query Path ──────────────────────┤
   │                                         │
   ▼                                         ▼
  ┌──────────────────┐             ┌──────────────────────────┐
  │  User question   │             │  RAG Pipeline            │
  │  via:            │             │  (app/rag.py)            │
  │   - REST API     │────────────▶│                          │
  │   - CLI          │             │  1. Embed question       │
  │   - Streamlit    │             │  2. Top-k similarity     │
  └──────────────────┘             │  3. Build prompt         │
                                   │  4. LLM call             │
                                   │  5. Citation extraction  │
                                   └────────────┬─────────────┘
                                                │
                                                ▼
                                   ┌──────────────────────────┐
                                   │  LLM (pluggable)         │
                                   │   Anthropic / OpenAI /   │
                                   │   Ollama (local)         │
                                   └────────────┬─────────────┘
                                                │
                                                ▼
                                   ┌──────────────────────────┐
                                   │  Structured response     │
                                   │   - answer (text)        │
                                   │   - citations[]          │
                                   │   - metadata             │
                                   └──────────────────────────┘
```

## Why these choices?

### Why `unstructured`?

SEC filings come in multiple formats — HTML EDGAR exports, PDFs of paper
filings, plain text. `unstructured` is the only library that handles all
of them with a consistent API while preserving structural cues (titles,
list items, tables) that we use for citation.

### Why section-aware chunking?

A pure 1000-token rolling window would cut the "Risk Factors" section
mid-sentence and mix it with "Properties". By detecting `Item 1A`,
`Item 7`, etc. first and chunking *within* each section, we keep
semantic coherence — which directly improves retrieval quality.

### Why `all-MiniLM-L6-v2`?

- **Small:** 80MB on disk, fits in any laptop's RAM.
- **Fast:** ~14k sentences/sec on CPU.
- **Good enough:** retrieves financial text well in our evaluation.
- **No GPU required:** demo runs anywhere.

For production, you might swap in a finance-tuned model like
`FinBERT` or upgrade to `all-mpnet-base-v2` for a precision boost.

### Why FAISS as default?

- **Local & file-based:** no separate server to run.
- **Fast:** sub-millisecond search at our scale.
- **Mature:** Meta-supported, billions of vectors in production elsewhere.

Chroma is offered as an alternative for users who want metadata
filtering with richer query semantics.

### Why pluggable LLM backends, with Ollama as the free default?

The hackathon explicitly allows any LLM. We default to **Ollama**
running **Llama 3.2 3B** because:

- **Free.** No API keys, no usage caps, no monthly bills.
- **Private.** Filings never leave the user's machine.
- **Reproducible.** Works without internet once installed.
- **Good enough.** Llama 3.2 handles SEC filings well at this scale.

A second free option — HuggingFace `flan-t5-base` via the local
`transformers` pipeline — is built in for users who can't install
Ollama (corporate machines, sandboxed environments). Paid backends
(Anthropic / OpenAI) are still available behind a config flag for
users who happen to have keys.

We picked an interface (LangChain's chat-model abstraction) that
supports all of them through a single `get_llm()` factory.

## Module dependencies

```
app/api.py    ─┐
app/cli.py    ─┼─▶ app/rag.py ─▶ app/ingestion.py ─▶ app/utils.py
app/ui.py     ─┘     │
                     ├─▶ app/llm.py ─▶ app/config.py
                     └─▶ app/prompts.py
```

## Data flow at query time

1. **Receive question** (REST POST, CLI arg, or Streamlit input).
2. **Validate** (Pydantic for API, argparse for CLI).
3. **Embed** the question with the same model used for indexing.
4. **Retrieve** top-k chunks (default 4) from the vector store,
   optionally filtered by `{company, form_type, fiscal_year}`.
5. **Build prompt**: system instructions + numbered context chunks
   (each prefixed with its `chunk_id`) + the question.
6. **Call LLM** with `temperature=0.1` for grounded, deterministic answers.
7. **Extract citations**: regex-match `[chunk_id]` tokens in the
   answer, map back to the retrieved Documents.
8. **Return** structured response: `{question, answer, citations[], metadata}`.

## Latency budget (free local stack)

| Stage           | Target  | Notes                                      |
| --------------- | ------- | ------------------------------------------ |
| Embed query     | < 30ms  | `all-MiniLM-L6-v2` on CPU                  |
| FAISS search    | < 10ms  | At our scale (~1k chunks)                  |
| Prompt assembly | < 5ms   | Pure Python                                |
| LLM call        | 1–4s    | Ollama (Llama 3.2 3B) on CPU; faster on GPU|
| Citation parse  | < 5ms   | Regex                                      |
| **Total**       | < 5s    | p95 — free local stack on a laptop CPU     |

Hosted LLMs (Claude, GPT-4) bring this down to ~1–2s but cost money.

## Scaling considerations

| Bottleneck         | Mitigation                                              |
| ------------------ | ------------------------------------------------------- |
| Index size         | Switch FAISS index type (IVF, HNSW) for >10M vectors    |
| Concurrent queries | Run multiple uvicorn workers behind a load balancer     |
| LLM cost           | Cache common queries; use a smaller model for retrieval |
| Cold start         | Pre-warm the embedding model on container start         |
| Multi-user         | Move vector store to a shared service (Pinecone, Qdrant)|
