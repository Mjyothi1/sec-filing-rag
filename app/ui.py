"""
Streamlit UI for the SEC Filing RAG system.

Run with:
    streamlit run app/ui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable so `from app.* import ...` works
# regardless of which directory streamlit is launched from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from app import __version__
from app.config import settings
from app.rag import RAGPipeline


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SEC Filing RAG",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Cached pipeline (loads once per session)
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner="Loading vector index…")
def get_pipeline() -> RAGPipeline:
    pipeline = RAGPipeline()
    pipeline.load_index()
    return pipeline


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


with st.sidebar:
    st.title("📊 SEC Filing RAG")
    st.caption(f"v{__version__} — Hackathon Edition")

    st.markdown("---")
    st.subheader("Configuration")
    st.write(f"**LLM:** `{settings.llm_provider}`")
    st.write(f"**Embeddings:** `{settings.embedding_model.split('/')[-1]}`")
    st.write(f"**Vector store:** `{settings.vector_store}`")

    st.markdown("---")
    st.subheader("Query options")
    top_k = st.slider("Chunks to retrieve (top-k)", 1, 10, settings.top_k)

    st.markdown("**Optional metadata filter**")
    filter_company = st.text_input("Company ticker", placeholder="e.g. AAPL").strip().upper()
    filter_form = st.selectbox("Form type", options=["", "10-K", "10-Q", "8-K"])
    filter_year = st.text_input("Fiscal year", placeholder="e.g. 2023").strip()

    metadata_filter: dict = {}
    if filter_company:
        metadata_filter["company"] = filter_company
    if filter_form:
        metadata_filter["form_type"] = filter_form
    if filter_year:
        metadata_filter["fiscal_year"] = filter_year

    st.markdown("---")
    st.markdown(
        "**Sample questions**\n"
        "- What are the main risk factors?\n"
        "- How did revenue change YoY?\n"
        "- What does the company say about AI?\n"
        "- Summarize the legal proceedings."
    )

    st.markdown("---")
    st.caption("Built for AI Hackathon @ Vignan University, Jan 2026.")


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------


st.title("📊 SEC Filing Summarizer & Q&A")
st.markdown(
    "Ask questions about indexed 10-K / 10-Q filings. "
    "Every answer is grounded in retrieved excerpts and cites its sources."
)

# Try to load the pipeline; show a helpful error if the index is missing.
try:
    pipeline = get_pipeline()
except FileNotFoundError as e:
    st.error(
        "🚨 **Vector index not found.**\n\n"
        f"{e}\n\n"
        "Build it first by running:\n```bash\npython scripts/ingest.py\n```"
    )
    st.stop()
except Exception as e:  # noqa: BLE001
    st.error(f"Failed to load pipeline: {e}")
    st.stop()


# Question form
with st.form("ask_form", clear_on_submit=False):
    question = st.text_area(
        "Your question",
        placeholder="e.g. What are the main risk factors mentioned in the latest 10-K?",
        height=100,
    )
    submitted = st.form_submit_button("🔍 Ask", type="primary", use_container_width=True)


if submitted and question.strip():
    with st.spinner("Retrieving relevant chunks and generating an answer..."):
        response = pipeline.ask(
            question=question.strip(),
            top_k=top_k,
            filter=metadata_filter or None,
        )

    # Answer
    st.markdown("### 💬 Answer")
    st.markdown(response.answer)

    # Metrics
    meta = response.metadata
    cols = st.columns(4)
    cols[0].metric("Model", meta.get("model", "?"))
    cols[1].metric("Retrieval", f"{meta.get('retrieval_time_ms', 0)} ms")
    cols[2].metric("Generation", f"{meta.get('generation_time_ms', 0)} ms")
    cols[3].metric("Chunks used", meta.get("num_retrieved", 0))

    # Citations
    st.markdown("### 📚 Citations")
    if not response.citations:
        st.info("No citations available.")
    else:
        for i, c in enumerate(response.citations, 1):
            with st.expander(
                f"**[{i}] {c.chunk_id}** — {c.company or '?'} {c.form_type or ''} {c.fiscal_year or ''}",
                expanded=(i == 1),
            ):
                st.markdown(f"**Section:** {c.section}")
                st.markdown(f"**Source:** `{c.source}`")
                if c.url:
                    st.markdown(f"**EDGAR:** {c.url}")
                st.markdown("**Excerpt:**")
                st.markdown(f"> {c.snippet}")

    # Raw JSON (debug)
    with st.expander("🛠️ Raw response (debug)"):
        st.json(response.to_dict())

elif submitted:
    st.warning("Please enter a question.")
