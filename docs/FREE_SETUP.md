# Zero-Cost Setup Guide

This guide walks you through running the SEC Filing RAG system **without
spending any money**. Everything below uses free, open-source software,
free hosted APIs, and public-domain data.

## Cost summary

| Item | Cost | Notes |
| --- | --- | --- |
| Python + libraries | $0 | All open-source |
| LLM (Gemini, default) | $0 | Free Google API — 1,000 requests/day, no card |
| LLM (Ollama, alt) | $0 | Local — Llama 3, Mistral, Phi-3 |
| LLM (HuggingFace, alt) | $0 | Local — runs in `pip install` |
| Embedding model | $0 | sentence-transformers (local) |
| Vector store | $0 | FAISS — runs on disk |
| SEC filings | $0 | Public-domain via EDGAR |
| Hosting | $0 | Runs on your laptop |
| **Total** | **$0** | |

---

## Step 1 — Install Python (free)

You need Python **3.10 or newer**.

- macOS: `brew install python@3.11`
- Linux: usually pre-installed; otherwise `sudo apt install python3.11 python3.11-venv`
- Windows: download from <https://python.org>

Verify:
```bash
python --version   # or python3 --version
```

---

## Step 2 — Pick a free LLM backend

### Option A — Gemini API (recommended, 2-minute setup)

Google's Gemini API has a free tier with **no credit card required**.
For a hackathon RAG demo, this is the fastest path.

**Get a free key:**
1. Go to <https://aistudio.google.com/app/apikey>
2. Sign in with any Google account
3. Click **Create API key**
4. Copy the key — you'll paste it into `.env` shortly

**Free-tier limits (as of 2026):**

| Model | Per minute | Per day |
| --- | --- | --- |
| `gemini-2.5-flash-lite` *(default — best for this project)* | 15 | **1,000** |
| `gemini-2.5-flash` | 10 | 250 |
| `gemini-2.5-pro` | 5 | 100 |

1,000 daily requests is far more than a hackathon demo will ever need.

### Option B — Ollama (fully local, no internet, no API at all)

Ollama is a free, open-source tool that runs LLMs locally. Best if you
prefer no external service involved at all.

**Install:**
- macOS: `brew install ollama`
- Linux: `curl -fsSL https://ollama.com/install.sh | sh`
- Windows: download installer from <https://ollama.com/download>

**Start the server:**
```bash
ollama serve
```

**Pull a free model** (one-time, ~2GB download):
```bash
ollama pull llama3.2:3b
```

**Verify:**
```bash
ollama run llama3.2:3b "Hello"
```

### Option C — HuggingFace transformers (zero install)

If you can't install Ollama and don't want to use any hosted API, use
the HuggingFace backend. The model weights (~250MB for `flan-t5-base`)
download automatically on the first query — everything else is in
`pip install`.

Just edit `.env` to set `LLM_PROVIDER=huggingface` and you're done.

---

## Step 3 — Set up the project

```bash
git clone https://github.com/Mjyothi1/sec-filing-rag.git
cd sec-filing-rag

# Virtual environment
python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# Install dependencies (all free)
pip install -r requirements.txt

# Copy default config
cp .env.example .env
```

Now edit `.env` based on which option you chose:

**Option A (Gemini)** — paste your free key:
```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=AIzaSy...your_free_key_here...
```

**Option B (Ollama)** — switch the provider:
```env
LLM_PROVIDER=ollama
```

**Option C (HuggingFace)** — switch the provider:
```env
LLM_PROVIDER=huggingface
```

---

## Step 4 — Get free SEC filings

The repo ships with a small synthetic 10-K (`SAMPLECO_10K_2023.txt`)
in `data/sample_filings/`. To use real public filings:

```bash
# Free, official SEC EDGAR API — no key needed
python scripts/download_filings.py --tickers AAPL MSFT GOOGL
```

You can also drop your own HTML/PDF/TXT filings into
`data/sample_filings/`.

---

## Step 5 — Build the vector index

```bash
python scripts/ingest.py
```

First run downloads the embedding model (`all-MiniLM-L6-v2`, ~80MB)
once. Indexing the bundled sample filing takes ~10 seconds.

---

## Step 6 — Ask questions

### CLI
```bash
python -m app.cli ask "What are the main risk factors?"
```

### REST API
```bash
uvicorn app.api:app --reload
# Open http://localhost:8000/docs
```

### Streamlit UI
```bash
streamlit run app/ui.py
# Open http://localhost:8501
```

---

## Hardware requirements

| Backend | RAM | Disk | Internet |
| --- | --- | --- | --- |
| Gemini (default) | 2 GB | 1 GB | Required (calls API) |
| Ollama (Llama 3.2 3B) | 4 GB | 4 GB | Only for setup |
| HuggingFace (flan-t5-base) | 2 GB | 1 GB | Only for first run |

**If you have less than 4 GB RAM and want a local backend**, use:
```env
HUGGINGFACE_MODEL=google/flan-t5-small   # ~80MB
# or
OLLAMA_MODEL=llama3.2:1b                  # ~1GB
```

---

## Troubleshooting

**"GOOGLE_API_KEY is not set" with Gemini**
→ Get a free key at <https://aistudio.google.com/app/apikey> and paste
it into `.env`.

**"429 Resource exhausted" with Gemini**
→ You hit the free-tier rate limit. Wait a minute (RPM) or until
midnight Pacific (RPD). Or switch to Ollama for unlimited local use.

**"Connection refused" when querying with Ollama**
→ The Ollama server isn't running. Start it: `ollama serve`

**"Model not found" with Ollama**
→ Pull it first: `ollama pull llama3.2:3b`

**HuggingFace downloads are slow**
→ First run downloads weights; subsequent calls use the cache. Use
`HUGGINGFACE_MODEL=google/flan-t5-small` for a faster start.

**`pip install` errors on Windows**
→ Install Microsoft C++ Build Tools, or use WSL2.

**Out of memory**
→ Switch to Gemini (offloads to Google's servers) or a smaller local model.

---

## Going beyond free

The system also supports paid backends if you want:

```env
# Anthropic Claude (paid)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI GPT-4 (paid)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

But this is **strictly optional** — Gemini, Ollama, and HuggingFace are
fully functional and what we use for the hackathon demo.
