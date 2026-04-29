"""
Configuration management for the SEC Filing RAG application.

Loads settings from environment variables (and optionally a `.env` file)
using Pydantic v2's BaseSettings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root: two parents up from this file (app/config.py -> app -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings — read from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ----- Gemini (free API, no credit card needed) -----
    # Get a free API key at: https://aistudio.google.com/app/apikey
    google_api_key: Optional[str] = Field(default=None)
    gemini_model: str = Field(default="gemini-2.5-flash-lite")

    # ----- Embeddings -----
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    embedding_device: str = Field(default="cpu")

    # ----- Vector store -----
    vector_store: Literal["faiss"] = Field(default="faiss")
    vector_store_dir: Path = Field(default=PROJECT_ROOT / "data" / "vectorstore")

    # ----- Chunking -----
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=200, ge=0)

    # ----- Retrieval -----
    top_k: int = Field(default=4, gt=0)
    similarity_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    # ----- Generation -----
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, gt=0)

    # ----- API -----
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    # ----- Data -----
    filings_dir: Path = Field(default=PROJECT_ROOT / "data" / "sample_filings")

    # ----- Provider info (kept for backward compatibility / metrics) -----
    @property
    def llm_provider(self) -> str:
        return "gemini"

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    def validate_provider_credentials(self) -> None:
        """Raise a clear error if the Gemini API key is missing."""
        if not self.google_api_key or self.google_api_key.strip() in {
            "",
            "paste_your_free_gemini_key_here",
        }:
            raise ValueError(
                "GOOGLE_API_KEY is not set. "
                "Get a free API key (no credit card needed) at "
                "https://aistudio.google.com/app/apikey, "
                "then add it to your .env file as GOOGLE_API_KEY=..."
            )


# Module-level singleton — imported elsewhere as `from app.config import settings`
settings = Settings()
