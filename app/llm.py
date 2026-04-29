"""
LLM provider — Google Gemini (free API, no credit card needed).

Get a free API key at: https://aistudio.google.com/app/apikey

Free-tier limits (as of 2026):
  - gemini-2.5-flash-lite: 15 RPM, 1000 requests/day  (default)
  - gemini-2.5-flash:      10 RPM, 250  requests/day
  - gemini-2.5-pro:         5 RPM, 100  requests/day
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.config import settings


def get_llm() -> Any:
    """Return a LangChain-compatible Gemini chat model."""
    settings.validate_provider_credentials()

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as e:
        raise ImportError(
            "langchain-google-genai is required. "
            "Install it via: pip install langchain-google-genai"
        ) from e

    logger.info(
        f"Using Gemini model: {settings.gemini_model} "
        "(free tier — get a key at https://aistudio.google.com/app/apikey)"
    )

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=settings.temperature,
        max_output_tokens=settings.max_tokens,
    )
