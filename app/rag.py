"""
Core RAG pipeline: build vector store, retrieve, and answer.

This is the heart of the application. It exposes a single high-level class,
`RAGPipeline`, with three primary methods:

    pipeline = RAGPipeline()
    pipeline.build_index(documents)   # one-time, after ingestion
    pipeline.load_index()             # for serving
    response = pipeline.ask(question) # query
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from langchain_core.documents import Document
from loguru import logger

from app.config import settings
from app.llm import get_llm
from app.prompts import build_rag_prompt, format_context
from app.utils import truncate


# ---------------------------------------------------------------------------
# Response dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Citation:
    """A single citation returned alongside an answer."""

    chunk_id: str
    source: str
    section: str
    company: Optional[str] = None
    form_type: Optional[str] = None
    fiscal_year: Optional[str] = None
    page: Optional[int] = None
    url: Optional[str] = None
    snippet: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RAGResponse:
    """Structured response returned by `RAGPipeline.ask`."""

    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Embeddings & vector store helpers
# ---------------------------------------------------------------------------


def _get_embeddings():
    """Lazy-load the embedding model (sentence-transformers)."""
    from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": settings.embedding_device},
        encode_kwargs={"normalize_embeddings": True},
    )


# ---------------------------------------------------------------------------
# RAG Pipeline
# ---------------------------------------------------------------------------


class RAGPipeline:
    """
    Retrieval-Augmented Generation pipeline for SEC filings.

    Encapsulates the embedding model, vector store, retriever, and LLM in
    a single object that can be reused across requests.
    """

    def __init__(
        self,
        vector_store_dir: Optional[Path] = None,
        top_k: Optional[int] = None,
    ):
        self.vector_store_dir = Path(vector_store_dir or settings.vector_store_dir)
        self.top_k = top_k or settings.top_k

        self._embeddings = None
        self._vector_store = None
        self._llm = None
        self._prompt = build_rag_prompt()

    # ------------------------------ Index building ------------------------------

    def build_index(self, documents: list[Document]) -> None:
        """Embed `documents` and persist a fresh vector store to disk."""
        if not documents:
            raise ValueError("No documents provided to index.")

        logger.info(f"Embedding {len(documents)} chunks with {settings.embedding_model}")
        embeddings = self._get_embeddings()

        if settings.vector_store == "faiss":
            from langchain_community.vectorstores import FAISS

            self._vector_store = FAISS.from_documents(documents, embeddings)
            self.vector_store_dir.mkdir(parents=True, exist_ok=True)
            self._vector_store.save_local(str(self.vector_store_dir))
            logger.success(f"FAISS index saved to {self.vector_store_dir}")
        elif settings.vector_store == "chroma":
            from langchain_community.vectorstores import Chroma

            self._vector_store = Chroma.from_documents(
                documents,
                embeddings,
                persist_directory=str(self.vector_store_dir),
            )
            self._vector_store.persist()
            logger.success(f"Chroma index saved to {self.vector_store_dir}")
        else:
            raise ValueError(f"Unsupported vector store: {settings.vector_store}")

    # ------------------------------ Index loading ------------------------------

    def load_index(self) -> None:
        """Load a previously-built vector store from disk."""
        if not self.vector_store_dir.exists():
            raise FileNotFoundError(
                f"Vector store directory not found: {self.vector_store_dir}. "
                "Run `python scripts/ingest.py` first."
            )

        embeddings = self._get_embeddings()

        if settings.vector_store == "faiss":
            from langchain_community.vectorstores import FAISS

            self._vector_store = FAISS.load_local(
                str(self.vector_store_dir),
                embeddings,
                allow_dangerous_deserialization=True,
            )
        elif settings.vector_store == "chroma":
            from langchain_community.vectorstores import Chroma

            self._vector_store = Chroma(
                persist_directory=str(self.vector_store_dir),
                embedding_function=embeddings,
            )
        else:
            raise ValueError(f"Unsupported vector store: {settings.vector_store}")

        logger.info(f"Loaded vector store from {self.vector_store_dir}")

    # ------------------------------ Querying ------------------------------

    def ask(
        self,
        question: str,
        top_k: Optional[int] = None,
        filter: Optional[dict] = None,
    ) -> RAGResponse:
        """
        Answer a question using the indexed filings.

        Args:
            question: User's natural-language question.
            top_k:    Number of chunks to retrieve (default: settings.top_k).
            filter:   Metadata filter (e.g. {"company": "AAPL"}).
        """
        if self._vector_store is None:
            self.load_index()

        k = top_k or self.top_k

        # 1. Retrieval
        t0 = time.time()
        retrieved = self._retrieve(question, k=k, filter=filter)
        retrieval_ms = int((time.time() - t0) * 1000)
        logger.info(f"Retrieved {len(retrieved)} chunks in {retrieval_ms}ms")

        if not retrieved:
            return RAGResponse(
                question=question,
                answer="I don't have enough information in the provided filings to answer that.",
                citations=[],
                metadata={"retrieval_time_ms": retrieval_ms, "generation_time_ms": 0},
            )

        # 2. Generation
        t0 = time.time()
        context = format_context(retrieved)
        prompt_text = self._prompt.format(context=context, question=question)

        llm = self._get_llm()
        result = llm.invoke(prompt_text)

        # Normalize result: chat models return objects with `.content`,
        # text-only LLMs (HuggingFacePipeline) return raw strings.
        if hasattr(result, "content"):
            answer = result.content
        elif isinstance(result, str):
            answer = result
        else:
            answer = str(result)

        generation_ms = int((time.time() - t0) * 1000)

        # 3. Citation post-processing
        citations = self._build_citations(retrieved, answer)

        return RAGResponse(
            question=question,
            answer=answer,
            citations=citations,
            metadata={
                "model": self._model_name(),
                "retrieval_time_ms": retrieval_ms,
                "generation_time_ms": generation_ms,
                "num_retrieved": len(retrieved),
                "filter": filter or {},
            },
        )

    # ------------------------------ Internals ------------------------------

    def _retrieve(
        self,
        question: str,
        k: int,
        filter: Optional[dict] = None,
    ) -> list[Document]:
        """Run a similarity search over the vector store."""
        if self._vector_store is None:
            raise RuntimeError("Vector store is not loaded.")

        # Normalize filter; FAISS in LangChain supports dict filters via callable.
        if settings.vector_store == "faiss" and filter:
            def matches(meta: dict) -> bool:
                return all(meta.get(k_) == v for k_, v in filter.items())

            return self._vector_store.similarity_search(question, k=k, filter=matches)

        return self._vector_store.similarity_search(question, k=k, filter=filter)

    def _build_citations(
        self,
        retrieved: list[Document],
        answer: str,
    ) -> list[Citation]:
        """
        Convert retrieved chunks into Citation objects.

        We include every retrieved chunk in the citations list, but mark
        the ones the model actually cited via the inline [chunk_id] tokens.
        """
        cited_ids = set(re.findall(r"\[([\w\-]+)\]", answer))
        citations: list[Citation] = []

        for doc in retrieved:
            md = doc.metadata
            chunk_id = md.get("chunk_id", "unknown")
            cit = Citation(
                chunk_id=chunk_id,
                source=md.get("source_path", md.get("filename", "unknown")),
                section=md.get("section", "unknown"),
                company=md.get("company"),
                form_type=md.get("form_type"),
                fiscal_year=md.get("fiscal_year"),
                page=md.get("page"),
                url=md.get("url"),
                snippet=truncate(doc.page_content, 240),
            )
            # Move cited ones to the front for nicer rendering.
            if chunk_id in cited_ids:
                citations.insert(0, cit)
            else:
                citations.append(cit)

        return citations

    def _get_embeddings(self):
        if self._embeddings is None:
            self._embeddings = _get_embeddings()
        return self._embeddings

    def _get_llm(self):
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    def _model_name(self) -> str:
        return settings.gemini_model


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


_default_pipeline: Optional[RAGPipeline] = None


def ask(question: str, **kwargs) -> RAGResponse:
    """
    Module-level helper matching the problem statement's `ask(question)` signature.

    Lazily initializes a singleton `RAGPipeline` on first call.
    """
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = RAGPipeline()
        _default_pipeline.load_index()
    return _default_pipeline.ask(question, **kwargs)
