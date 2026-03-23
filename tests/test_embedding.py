"""Tests for maestro.embedding — Gemini Embedding client."""

from __future__ import annotations

import pathlib

import pytest

from maestro.embedding import EMBEDDING_DIM, EmbeddingClient


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def test_client_available_false_when_no_key() -> None:
    client = EmbeddingClient(api_key=None)
    assert client.available is False


def test_client_available_true_when_key_set() -> None:
    client = EmbeddingClient(api_key="test-key-123")
    assert client.available is True


# ---------------------------------------------------------------------------
# Fallback behavior (no API key)
# ---------------------------------------------------------------------------


async def test_embed_text_fallback() -> None:
    """Returns zero vector when no API key is set."""
    client = EmbeddingClient(api_key=None)
    result = await client.embed_text("Hello, world!")

    assert len(result) == EMBEDDING_DIM
    assert all(v == 0.0 for v in result)


async def test_embed_file_fallback(tmp_path: pathlib.Path) -> None:
    """Returns zero vector when no API key is set."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Some content")

    client = EmbeddingClient(api_key=None)
    result = await client.embed_file(test_file)

    assert len(result) == EMBEDDING_DIM
    assert all(v == 0.0 for v in result)


# ---------------------------------------------------------------------------
# Stub behavior (with API key, but API call is stubbed)
# ---------------------------------------------------------------------------


async def test_embed_text_stub_with_key() -> None:
    """Even with a key, the stub returns zero vectors."""
    client = EmbeddingClient(api_key="fake-key")
    result = await client.embed_text("Test text")

    assert len(result) == EMBEDDING_DIM
    # Stub returns zeros
    assert all(v == 0.0 for v in result)


async def test_embed_file_text_document(tmp_path: pathlib.Path) -> None:
    """Text files (.txt, .md) should attempt text embedding."""
    md_file = tmp_path / "readme.md"
    md_file.write_text("# Title\nSome content")

    client = EmbeddingClient(api_key="fake-key")
    result = await client.embed_file(md_file)

    assert len(result) == EMBEDDING_DIM


async def test_embed_file_unsupported_type(tmp_path: pathlib.Path) -> None:
    """Unsupported file types return zero vectors."""
    img_file = tmp_path / "photo.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n")  # Minimal PNG header

    client = EmbeddingClient(api_key="fake-key")
    result = await client.embed_file(img_file)

    assert len(result) == EMBEDDING_DIM
    assert all(v == 0.0 for v in result)
