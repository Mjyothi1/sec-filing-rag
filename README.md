# SEC Filing Summarizer & Q&A (RAG)

> **SEC_FILING_RAG**
> Query 10‑K / 10‑Q SEC filings and answer investor questions with
> source citations using Retrieval-Augmented Generation (RAG).
>
> **🆓 Runs end-to-end on Google's free Gemini API. No paid services. No credit card.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688)]()
[![LangChain](https://img.shields.io/badge/LangChain-0.2-yellow)]()
[![100% Free](https://img.shields.io/badge/cost-%240-brightgreen)]()

---

## ✨ Why this project is fully free

| Component | Free choice used |
| --- | --- |
| **LLM** | Google Gemini API (free tier — 1,000 requests/day, no credit card) |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` (free, runs locally) |
| **Vector store** | FAISS (free, file-based) |
| **Document parsing** | `pypdf` + `beautifulsoup4` (open-source) |
| **API server** | FastAPI + Uvicorn (free) |
| **UI** | Streamlit (free) |
| **Sample data** | EDGAR — public-domain filings from sec.gov |

**Total cost to run: ₹0 / $0**

---

## 📋 Table of Contents

1. [Problem Statement](#problem-statement)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Tech Stack](#tech-stack)
5. [Usage](#usage)
6. [API Reference](#api-reference)
7. [Project Structure](#project-structure)
8. [How It Works](#how-it-works)
9. [Sample Queries](#sample-queries)
10. [License](#license)

---

## Problem Statement

** SEC Filing Summarizer & Q&A (RAG)**

- **Problem:** Query 10‑K/10‑Q filings and answer investor questions with source citations.
- **Sample data:** SEC Filings dataset (Kaggle / EDGAR).
- **Outcome:** Index a small subset; implement `ask(question)` returning answer + chunk URLs.
- **Stack:** Python, LangChain, embeddings + vector store, FastAPI `/ask`.

---

## Quick Start

### Step 1 — Get a free Gemini API key (30 seconds)

1. Visit <https://aistudio.google.com/app/apikey>
2. Sign in with any Google account (no credit card required)
3. Click **"Create API key"**
4. Copy the key (looks like `AIzaSy...`)

### Step 2 — Set up the project

```bash
# Clone and enter the project
git clone https://github.com/Mjyothi1/sec-filing-rag.git
cd sec-filing-rag

# Create virtual environment
python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure your free key
cp .env.example .env
# Open .env and paste your key into GOOGLE_API_KEY=...
```

### Step 3 — Build the index and ask questions

```bash
# Build vector index from the bundled sample 10-K
python scripts/ingest.py

# Ask a question
python -m app.cli ask "What are the main risk factors?"
```

### Step 4 (optional) — Use real SEC filings

You have **three free options** to get real SEC filings:

**Option A — Bundled Kaggle dataset** *(the one specified in the hackathon problem)*

The Kaggle SEC Filings dataset (`data/kaggle/sec_filings.csv`, ~2 MB) is
**bundled with this repo** so you don't need a Kaggle account. The script
reads the metadata and pulls the actual filings directly from sec.gov.

```bash
# Default: download 10 random primary filings from the dataset
python scripts/download_from_kaggle_csv.py

# Or be more specific:
python scripts/download_from_kaggle_csv.py --form-type 10-K --include-exhibits --count 15
python scripts/download_from_kaggle_csv.py --tickers AAPL MSFT --count 5
python scripts/download_from_kaggle_csv.py --year 2022 --count 20

# Then re-build the index
python scripts/ingest.py
```

The bundled CSV is the same one from
<https://www.kaggle.com/datasets/kharanshuvalangar/sec-filings>.
It contains metadata for 10,000 SEC filings (10-Ks, 10-Qs, 8-Ks, S-1s,
exhibits) spanning 2004–2023 with 103 unique filing URLs.

**Option B — SEC EDGAR live download (no Kaggle data needed)**

```bash
python scripts/download_filings.py --tickers AAPL MSFT GOOGL
python scripts/ingest.py
```

**Option C — Bring your own**

Drop any `.html`, `.htm`, `.pdf`, or `.txt` SEC filings into
`data/sample_filings/` and run `python scripts/ingest.py`.

### Step 5 (optional) — Run the API or UI

```bash
# REST API on http://localhost:8000/docs
uvicorn app.api:app --reload

# Web UI on http://localhost:8501
streamlit run app/ui.py
```

---

## Architecture

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  SEC Filings     │      │   Ingestion      │      │  FAISS Vector    │
│  (10-K / 10-Q)   ├─────▶│   (parse +       ├─────▶│  Store (free,    │
│   HTML/PDF/TXT   │      │    chunk)        │      │   local)         │
└──────────────────┘      └──────────────────┘      └────────┬─────────┘
                                                              │
                                                              ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   User Query     │      │   Retriever      │      │  Top-k Chunks    │
│   "What are      ├─────▶│   (similarity    ├─────▶│  + metadata      │
│   risks?"        │      │    search)       │      │                  │
└──────────────────┘      └──────────────────┘      └────────┬─────────┘
                                                              │
                                                              ▼
                          ┌──────────────────┐      ┌──────────────────┐
                          │   Final Answer   │◀─────│  Google Gemini   │
                          │   + Citations    │      │  (free API)      │
                          └──────────────────┘      └──────────────────┘
```

---

## Tech Stack

| Layer            | Technology                                                  | Cost |
| ---------------- | ----------------------------------------------------------- | ---- |
| **Language**     | Python 3.10+                                                | Free |
| **Parsing**      | `beautifulsoup4` + `pypdf`                                  | Free |
| **Orchestration**| `langchain` + `langchain-community`                         | Free |
| **Embeddings**   | `sentence-transformers/all-MiniLM-L6-v2`                    | Free |
| **Vector Store** | FAISS                                                       | Free |
| **LLM**          | Google Gemini 2.5 Flash-Lite (free API tier)                | Free |
| **API**          | FastAPI + Uvicorn                                           | Free |
| **UI**           | Streamlit                                                   | Free |
| **Testing**      | pytest                                                      | Free |
| **Sample data**  | SEC EDGAR (public domain)                                   | Free |

---

## Usage

### CLI

```bash
python -m app.cli ask "What are the main risk factors?"
python -m app.cli ask "How did revenue change YoY?" --top-k 6
python -m app.cli ask "Risk factors" --filter '{"company":"AAPL","form_type":"10-K"}'
python -m app.cli stats
```

### REST API

```bash
uvicorn app.api:app --reload
# Visit http://localhost:8000/docs for interactive Swagger UI
```

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the main risk factors?"}'
```

### Streamlit UI

```bash
streamlit run app/ui.py
# Open http://localhost:8501
```

---

## API Reference

### `POST /ask`

```json
{
  "question": "What are the main risk factors mentioned in the latest 10-K?",
  "top_k": 4,
  "filter": { "company": "AAPL", "form_type": "10-K" }
}
```

**Response:**
```json
{
  "answer": "The main risk factors include macroeconomic conditions, supply chain concentration, cybersecurity, and AI risks [SAMPLECO_10-K_2023_Item_1A_chunk_0]...",
  "citations": [
    {
      "chunk_id": "SAMPLECO_10-K_2023_Item_1A_chunk_0",
      "source": "data/sample_filings/SAMPLECO_10K_2023.txt",
      "section": "Item 1A. Risk Factors",
      "company": "SAMPLECO",
      "form_type": "10-K",
      "fiscal_year": "2023",
      "snippet": "The Company's business, financial condition..."
    }
  ],
  "metadata": {
    "model": "gemini-2.5-flash-lite",
    "retrieval_time_ms": 87,
    "generation_time_ms": 1432
  }
}
```

### Other endpoints

- `GET /health` — service status + index stats
- `GET /filings` — list indexed filings

---

## Project Structure

```
sec-filing-rag/
├── app/
│   ├── api.py              # FastAPI server (/ask)
│   ├── cli.py              # CLI: ask | ingest | stats
│   ├── config.py           # Pydantic settings
│   ├── ingestion.py        # Parsing & section-aware chunking
│   ├── llm.py              # Gemini LLM factory
│   ├── prompts.py          # Citation-enforcing prompt templates
│   ├── rag.py              # Core RAG pipeline + ask()
│   ├── ui.py               # Streamlit UI
│   └── utils.py            # Logging, metadata, helpers
├── scripts/
│   ├── ingest.py           # Build the vector index
│   ├── download_filings.py # Pull free 10-Ks from SEC EDGAR
│   └── evaluate.py         # Precision@k + faithfulness metrics
├── tests/                  # 20 unit/integration tests (all passing)
├── data/sample_filings/    # Bundled synthetic 10-K
├── docs/                   # Architecture, demo, evaluation guides
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## How It Works

1. **Parse** — `beautifulsoup4` (HTML) + `pypdf` (PDF) extract clean text.
2. **Section split** — regex finds SEC item headers (`Item 1A. Risk Factors`,
   `Item 7. MD&A`, …) so chunks stay semantically coherent.
3. **Chunk** — recursive character splitter (1000 tokens, 200 overlap) within sections.
4. **Embed** — `all-MiniLM-L6-v2` produces 384-dim vectors locally on CPU.
5. **Index** — FAISS builds an in-memory + on-disk similarity index.
6. **Retrieve** — embed the query, run top-k similarity search.
7. **Generate** — stuff retrieved chunks into a citation-enforcing prompt; call Gemini.
8. **Cite** — regex extracts `[chunk_id]` references from the answer and
   maps them back to chunk metadata for the response payload.

---

## Sample Queries

| Question | Behavior |
| --- | --- |
| *"What are the main risk factors?"* | Returns top risks from Item 1A with chunk-level citations. |
| *"How did revenue change YoY?"* | Pulls revenue numbers from MD&A. |
| *"What does the company say about supply chain?"* | Locates supply-chain disclosures across sections. |
| *"Summarize the legal proceedings."* | Synthesizes Item 3 content. |
| *"What is the company's outlook on AI?"* | Searches forward-looking statements. |

---

## Free Gemini Models

Edit `.env` to switch models:

```env
GEMINI_MODEL=gemini-2.5-flash-lite      # 15 RPM / 1000 RPD (default)
GEMINI_MODEL=gemini-2.5-flash           # 10 RPM / 250 RPD (more capable)
GEMINI_MODEL=gemini-2.5-pro             # 5 RPM / 100 RPD (best quality)
```

All three are free.

---

## License

**MIT** — see [LICENSE](LICENSE).

Built for the AI Hackathon at Vignan University, January 2026.
Organized by *Python Guru | Supervity | Vignan's*.

**Contact:** [github.com/Mjyothi1](https://github.com/Mjyothi1)

> *"AI Hackathon — Where ideas meet intelligence."*
