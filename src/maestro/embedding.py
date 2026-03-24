"""Gemini Embedding 2 Preview client for multimodal asset embedding."""

from __future__ import annotations

import asyncio
import json
import mimetypes
from pathlib import Path

from google import genai
from google.genai import types


def _guess_mime(file_path: str) -> str:
    """Guess MIME type from file extension."""
    mime, _ = mimetypes.guess_type(file_path)
    return mime or "application/octet-stream"


class EmbeddingClient:
    """Gemini Embedding 2 Preview client.

    Supports: text, image, video, audio, PDF — all natively.
    Output: 3072-dimensional vectors in a single shared vector space.
    """

    MODEL = "gemini-embedding-2-preview"
    EMBEDDING_DIM = 3072

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required for EmbeddingClient")
        self._client = genai.Client(api_key=api_key)

    async def embed_text(
        self, text: str, task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[float]:
        result = await asyncio.to_thread(
            self._client.models.embed_content,
            model=self.MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=self.EMBEDDING_DIM,
                task_type=task_type,
            ),
        )
        return list(result.embeddings[0].values)

    async def embed_query(self, query: str) -> list[float]:
        return await self.embed_text(query, task_type="RETRIEVAL_QUERY")

    async def embed_image(self, image_path: str) -> list[float]:
        data = Path(image_path).read_bytes()
        mime = _guess_mime(image_path)
        return await self._embed_bytes(data, mime)

    async def embed_video(self, video_path: str) -> list[float]:
        data = Path(video_path).read_bytes()
        mime = _guess_mime(video_path)
        return await self._embed_bytes(data, mime)

    async def embed_audio(self, audio_path: str) -> list[float]:
        data = Path(audio_path).read_bytes()
        mime = _guess_mime(audio_path)
        return await self._embed_bytes(data, mime)

    async def embed_asset(self, asset: dict) -> list[float]:
        media = asset.get("media_type", "")

        if asset.get("file_path"):
            if media.startswith("image/"):
                return await self.embed_image(asset["file_path"])
            if media.startswith("video/"):
                return await self.embed_video(asset["file_path"])
            if media.startswith("audio/"):
                return await self.embed_audio(asset["file_path"])
            if media == "application/pdf":
                return await self._embed_bytes(
                    Path(asset["file_path"]).read_bytes(), media
                )

        if asset.get("content_json"):
            text = asset["content_json"]
            if not isinstance(text, str):
                text = json.dumps(text, ensure_ascii=False)
            return await self.embed_text(text)

        if asset.get("description"):
            return await self.embed_text(asset["description"])

        return [0.0] * self.EMBEDDING_DIM

    async def _embed_bytes(self, data: bytes, mime_type: str) -> list[float]:
        result = await asyncio.to_thread(
            self._client.models.embed_content,
            model=self.MODEL,
            contents=[types.Part.from_bytes(data=data, mime_type=mime_type)],
            config=types.EmbedContentConfig(
                output_dimensionality=self.EMBEDDING_DIM,
            ),
        )
        return list(result.embeddings[0].values)
