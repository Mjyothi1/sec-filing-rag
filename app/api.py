"""
FastAPI server exposing the RAG pipeline.

Endpoints:
    POST /ask      — submit a question, get an answer + citations
    GET  /health   — liveness/readiness probe
    GET  /filings  — list indexed filings
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field

from app import __version__
from app.config import settings
from app.rag import RAGPipeline


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    filter: Optional[dict[str, Any]] = Field(
        default=None,
        description="Metadata filter, e.g. {\"company\": \"AAPL\", \"form_type\": \"10-K\"}",
    )


class CitationModel(BaseModel):
    chunk_id: str
    source: str
    section: str
    company: Optional[str] = None
    form_type: Optional[str] = None
    fiscal_year: Optional[str] = None
    page: Optional[int] = None
    url: Optional[str] = None
    snippet: str


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[CitationModel]
    metadata: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_provider: str
    vector_store: str
    index_loaded: bool


class FilingsResponse(BaseModel):
    count: int
    filings: list[dict]


# ---------------------------------------------------------------------------
# Lifespan: load the RAG pipeline once at startup
# ---------------------------------------------------------------------------


pipeline: Optional[RAGPipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    logger.info(f"Starting SEC Filing RAG API v{__version__}")
    pipeline = RAGPipeline()
    try:
        pipeline.load_index()
        logger.success("Vector index loaded successfully.")
    except FileNotFoundError as e:
        logger.error(str(e))
        # Server still starts — /ask will return a clear error.
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Failed to load index: {e}")
    yield
    logger.info("Shutting down SEC Filing RAG API.")


app = FastAPI(
    title="SEC Filing Summarizer & Q&A (RAG)",
    description=(
        "Query 10-K and 10-Q SEC filings and get answers with source citations. "
        "Built for the AI Hackathon at Vignan University, Jan 2026."
    ),
    version=__version__,
    lifespan=lifespan,
)

# CORS — open by default for the hackathon demo. Lock down for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "SEC Filing RAG",
        "version": __version__,
        "docs": "/docs",
        "endpoints": ["/ask", "/health", "/filings"],
    }


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        llm_provider=settings.llm_provider,
        vector_store=settings.vector_store,
        index_loaded=pipeline is not None and pipeline._vector_store is not None,
    )


@app.post("/ask", response_model=AskResponse)
async def ask_endpoint(request: AskRequest) -> AskResponse:
    if pipeline is None or pipeline._vector_store is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Vector index is not loaded. Run "
                "`python scripts/ingest.py` to build it first."
            ),
        )

    try:
        response = pipeline.ask(
            question=request.question,
            top_k=request.top_k,
            filter=request.filter,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Error while answering question")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return AskResponse(**response.to_dict())


@app.get("/filings", response_model=FilingsResponse)
async def list_filings() -> FilingsResponse:
    """List unique source filings present in the loaded index."""
    if pipeline is None or pipeline._vector_store is None:
        raise HTTPException(status_code=503, detail="Index not loaded.")

    seen: dict[str, dict] = {}

    # FAISS exposes docstore at `_vector_store.docstore._dict`
    try:
        docstore = pipeline._vector_store.docstore._dict  # type: ignore[attr-defined]
        for doc in docstore.values():
            md = doc.metadata
            key = md.get("source_path") or md.get("filename") or "unknown"
            if key not in seen:
                seen[key] = {
                    "source": key,
                    "company": md.get("company"),
                    "form_type": md.get("form_type"),
                    "fiscal_year": md.get("fiscal_year"),
                }
    except AttributeError:
        # Chroma layout differs — fall back to a count-only response.
        return FilingsResponse(count=0, filings=[])

    return FilingsResponse(count=len(seen), filings=list(seen.values()))


# ---------------------------------------------------------------------------
# Local entry point
# ---------------------------------------------------------------------------


def main():
    import uvicorn

    uvicorn.run(
        "app.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
