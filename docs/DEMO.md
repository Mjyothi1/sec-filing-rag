# Demo Guide — 100% Free Path

A 5-minute walkthrough using only free, local tools. No API keys, no
paid services.

## Prerequisites

- Python 3.10+
- ~4GB free disk for the embedding model and a small Llama
- An LLM backend — pick **one**:
  - **Ollama** (recommended): install from <https://ollama.com/download>
  - **HuggingFace transformers**: nothing extra, just `pip install`

## 1. Install Ollama and pull a free model (60 seconds)

```bash
# macOS / Linux
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &                # start the local server
ollama pull llama3.2:3b       # ~2GB download, one time
```

Skip this step entirely if you're using the HuggingFace backend —
just edit `.env` later to set `LLM_PROVIDER=huggingface`.

## 2. Set up the project (60 seconds)

```bash
git clone https://github.com/Mjyothi1/sec-filing-rag.git
cd sec-filing-rag
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # default config already uses free Ollama
```

## 3. Build the index (60 seconds)

The repo ships with a sample 10-K so you can demo immediately:

```bash
python scripts/ingest.py
```

Expected output:

```
2026-04-29 12:00:00 | INFO     | Found 1 candidate files in data/sample_filings
Parsing filings: 100%|████████| 1/1
2026-04-29 12:00:01 | INFO     | Produced 14 total chunks across 1 files
2026-04-29 12:00:01 | INFO     | Embedding 14 chunks with sentence-transformers/all-MiniLM-L6-v2
2026-04-29 12:00:05 | SUCCESS  | FAISS index saved to data/vectorstore
```

To use real filings instead:

```bash
python scripts/download_filings.py --tickers AAPL MSFT GOOGL
python scripts/ingest.py
```

## 4. Ask a question via CLI (30 seconds)

```bash
python -m app.cli ask "What are the main risk factors?"
```

Expected output:

```
======================================================================
❓ Question: What are the main risk factors?
======================================================================

💬 Answer:
The main risk factors include:

1. Macroeconomic conditions — inflation, recession, and currency
   fluctuations can adversely affect demand [SAMPLECO_10-K_2023_Item_1A_chunk_0].
2. Supply chain concentration — manufacturing depends on a few
   outsourcing partners primarily in China, India, Japan, South Korea,
   Taiwan, and Vietnam [SAMPLECO_10-K_2023_Item_1A_chunk_1].
3. Cybersecurity — the company is subject to evolving privacy and
   data protection laws worldwide [SAMPLECO_10-K_2023_Item_1A_chunk_2].
4. Artificial intelligence — risks around accuracy, bias, regulation,
   and IP [SAMPLECO_10-K_2023_Item_1A_chunk_3].

Sources:
SAMPLECO_10-K_2023_Item_1A_chunk_0
SAMPLECO_10-K_2023_Item_1A_chunk_1
SAMPLECO_10-K_2023_Item_1A_chunk_2
SAMPLECO_10-K_2023_Item_1A_chunk_3
----------------------------------------------------------------------
📚 Citations (4):
  [1] SAMPLECO_10-K_2023_Item_1A_chunk_0
      Section: Item 1A. Risk Factors
      Source:  data/sample_filings/SAMPLECO_10K_2023.txt
      Snippet: The Company's business, financial condition, operating results...
...
⚙️  Model: llama3.2:3b | Retrieval: 87ms | Generation: 1240ms
```

## 5. Run the FastAPI server (30 seconds)

```bash
uvicorn app.api:app --reload
```

Open <http://localhost:8000/docs> for the Swagger UI.

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the company say about AI?"}' | jq
```

## 6. Launch the Streamlit UI (30 seconds)

```bash
streamlit run app/ui.py
```

Open <http://localhost:8501>. You get:
- Sidebar for filters (company, form type, fiscal year, top-k)
- Main panel for question entry
- Inline answer with expandable citation cards
- Performance metrics (retrieval / generation time)
- Raw JSON debug view

## 7. Run tests (optional)

```bash
pytest tests/ -v
```

You should see 20 tests pass.

---

## Sample queries to demo

| Query | What it shows |
| --- | --- |
| `What are the main risk factors?` | Item 1A retrieval |
| `How did revenue change in 2023?` | MD&A retrieval + numbers |
| `What does the company say about supply chain?` | Cross-section synthesis |
| `Summarize the legal proceedings.` | Item 3 retrieval |
| `What is the company's strategy on AI?` | Forward-looking statements |
| `What was the gross margin?` | Specific financial figures |

## Troubleshooting

**Q: "Vector store directory not found"**
A: Run `python scripts/ingest.py` first to build the index.

**Q: "Connection refused" when querying**
A: Ollama isn't running. Start it: `ollama serve`

**Q: "Model not found" with Ollama**
A: Pull the model: `ollama pull llama3.2:3b`

**Q: First query is slow**
A: The embedding model (~80MB) and Llama (~2GB) load into RAM on first
use. Subsequent queries are fast.

**Q: I can't install Ollama**
A: Switch to HuggingFace — edit `.env`: `LLM_PROVIDER=huggingface`. No
external install needed.

**Q: My laptop only has 4GB RAM**
A: Use a smaller model:
```env
OLLAMA_MODEL=llama3.2:1b
# or
HUGGINGFACE_MODEL=google/flan-t5-small
```

---

## Performance numbers (free-path demo)

| Metric              | Ollama (Llama 3.2 3B) | HF (Flan-T5 base) |
| ------------------- | --------------------- | ----------------- |
| Index size          | 14 chunks             | 14 chunks         |
| First load (cold)   | ~5s (model into RAM)  | ~3s (HF download) |
| Query latency       | 1.5–4s (CPU)          | 1–2s (CPU)        |
| RAM usage           | ~3GB                  | ~1GB              |
| Cost per query      | **$0**                | **$0**            |

Both backends hit the hackathon's quality bar on the bundled sample
filing. Ollama with Llama 3.2 3B gives more natural-sounding answers;
Flan-T5-base is faster and lighter.
