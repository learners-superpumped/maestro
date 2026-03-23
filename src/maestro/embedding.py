"""
Gemini Embedding client.

Provides text and file embedding via the Gemini Embedding 2 API.
Gracefully degrades to zero vectors when no API key is configured.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Gemini text-embedding-004 produces 768-dim vectors
EMBEDDING_DIM = 768


class EmbeddingClient:
    """Client for Gemini Embedding API with fallback to zero vectors."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")

    @property
    def available(self) -> bool:
        """Check if API key is configured."""
        return self._api_key is not None

    async def embed_text(self, text: str) -> list[float]:
        """Get embedding vector for text.

        Returns a 768-dim zero vector when no API key is set.
        """
        if not self.available:
            logger.debug("No GEMINI_API_KEY set; returning zero vector for text embedding")
            return [0.0] * EMBEDDING_DIM

        return await self._call_gemini_text(text)

    async def embed_file(self, path: Path) -> list[float]:
        """Get embedding for a file (image, document, etc.).

        For documents (.txt, .md): extracts text and embeds it.
        For images/video: placeholder (returns zero vector).
        Returns a 768-dim zero vector when no API key is set.
        """
        if not self.available:
            logger.debug("No GEMINI_API_KEY set; returning zero vector for file embedding")
            return [0.0] * EMBEDDING_DIM

        suffix = path.suffix.lower()

        # Text-based files: read and embed as text
        if suffix in (".txt", ".md", ".csv"):
            text = path.read_text(encoding="utf-8", errors="replace")
            return await self._call_gemini_text(text)

        # For images, video, PDFs — return zero vector placeholder
        logger.info("File type %s not yet supported for embedding; returning zero vector", suffix)
        return [0.0] * EMBEDDING_DIM

    async def _call_gemini_text(self, text: str) -> list[float]:
        """Call the Gemini embedding API for text.

        Currently a stub that returns zero vectors.
        Replace with actual API call when ready.
        """
        # TODO: Implement actual Gemini API call:
        #   POST https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent
        #   Headers: x-goog-api-key: {api_key}
        #   Body: {"model": "models/text-embedding-004", "content": {"parts": [{"text": text}]}}
        logger.info("Gemini API call stubbed; returning zero vector")
        return [0.0] * EMBEDDING_DIM
