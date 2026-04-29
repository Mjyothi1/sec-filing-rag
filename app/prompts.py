"""Prompt templates for the RAG pipeline."""

from __future__ import annotations

try:
    from langchain_core.prompts import PromptTemplate
except ImportError:  # legacy fallback
    from langchain.prompts import PromptTemplate


# ---------------------------------------------------------------------------
# RAG answer-generation prompt
# ---------------------------------------------------------------------------

RAG_SYSTEM_INSTRUCTIONS = """\
You are a meticulous financial analyst answering investor questions about \
SEC filings (10-K, 10-Q). You answer ONLY based on the provided context. \
You ALWAYS cite the source of each claim using the chunk identifiers given.

Rules:
1. If the answer cannot be found in the context, reply: "I don't have enough information in the provided filings to answer that."
2. Quote sparingly. Paraphrase in your own words.
3. After each factual claim, add an inline citation in the form [chunk_id].
4. End your answer with a "Sources:" section listing every chunk_id you cited, one per line.
5. Keep the answer concise and well-structured.
6. Never invent numbers, dates, or company names that are not in the context.
"""


RAG_PROMPT_TEMPLATE = """\
{system}

----- CONTEXT -----
{context}
----- END CONTEXT -----

Question: {question}

Answer (with inline [chunk_id] citations and a final "Sources:" section):
"""


def build_rag_prompt() -> PromptTemplate:
    """Build the LangChain PromptTemplate used by the RAG chain."""
    return PromptTemplate(
        template=RAG_PROMPT_TEMPLATE,
        input_variables=["context", "question"],
        partial_variables={"system": RAG_SYSTEM_INSTRUCTIONS},
    )


# ---------------------------------------------------------------------------
# Context formatting helper
# ---------------------------------------------------------------------------


def format_context(documents) -> str:
    """
    Render retrieved documents into a numbered, citation-friendly block.

    Each chunk is prefixed with its chunk_id so the LLM can cite it directly.
    """
    parts = []
    for doc in documents:
        chunk_id = doc.metadata.get("chunk_id", "unknown")
        section = doc.metadata.get("section", "?")
        company = doc.metadata.get("company", "?")
        form = doc.metadata.get("form_type", "?")
        year = doc.metadata.get("fiscal_year", "?")
        header = f"[{chunk_id}] ({company} {form} {year} — {section})"
        parts.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)
