"""Tests for Gemini Embedding 2 Preview client."""

from unittest.mock import MagicMock, patch

import pytest

from maestro.embedding import EmbeddingClient, _guess_mime


@pytest.fixture
def mock_genai_client():
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.values = [0.1] * 3072
    mock_result.embeddings = [mock_embedding]
    mock_client.models.embed_content.return_value = mock_result
    return mock_client


def test_embedding_dim():
    assert EmbeddingClient.EMBEDDING_DIM == 3072
    assert EmbeddingClient.MODEL == "gemini-embedding-2-preview"


def test_no_api_key_raises():
    with pytest.raises(ValueError, match="API key"):
        EmbeddingClient(api_key="")


def test_guess_mime():
    assert _guess_mime("test.png") == "image/png"
    assert _guess_mime("test.mp4") == "video/mp4"
    assert _guess_mime("test.wav") == "audio/x-wav"
    assert _guess_mime("test.pdf") == "application/pdf"
    assert _guess_mime("test.unknown_ext") == "application/octet-stream"


@pytest.mark.asyncio
async def test_embed_text(mock_genai_client):
    with patch("maestro.embedding.genai") as mock_genai:
        mock_genai.Client.return_value = mock_genai_client
        client = EmbeddingClient(api_key="test-key")
        result = await client.embed_text("hello world")
        assert len(result) == 3072
        assert result[0] == 0.1
        # Verify API was called
        mock_genai_client.models.embed_content.assert_called_once()


@pytest.mark.asyncio
async def test_embed_query_uses_retrieval_query(mock_genai_client):
    with patch("maestro.embedding.genai") as mock_genai:
        mock_genai.Client.return_value = mock_genai_client
        client = EmbeddingClient(api_key="test-key")
        await client.embed_query("search term")
        call_args = mock_genai_client.models.embed_content.call_args
        config = call_args.kwargs.get("config") or call_args[1].get("config")
        assert config.task_type == "RETRIEVAL_QUERY"


@pytest.mark.asyncio
async def test_embed_image(mock_genai_client, tmp_path):
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    with patch("maestro.embedding.genai") as mock_genai:
        mock_genai.Client.return_value = mock_genai_client
        client = EmbeddingClient(api_key="test-key")
        result = await client.embed_image(str(img))
        assert len(result) == 3072


@pytest.mark.asyncio
async def test_embed_asset_text(mock_genai_client):
    with patch("maestro.embedding.genai") as mock_genai:
        mock_genai.Client.return_value = mock_genai_client
        client = EmbeddingClient(api_key="test-key")
        asset = {"content_json": {"text": "hello"}, "media_type": "text/plain"}
        result = await client.embed_asset(asset)
        assert len(result) == 3072


@pytest.mark.asyncio
async def test_embed_asset_description_fallback(mock_genai_client):
    with patch("maestro.embedding.genai") as mock_genai:
        mock_genai.Client.return_value = mock_genai_client
        client = EmbeddingClient(api_key="test-key")
        asset = {"description": "A brand logo"}
        result = await client.embed_asset(asset)
        assert len(result) == 3072


@pytest.mark.asyncio
async def test_embed_asset_no_content_returns_zero():
    with patch("maestro.embedding.genai") as mock_genai:
        mock_genai.Client.return_value = MagicMock()
        client = EmbeddingClient(api_key="test-key")
        result = await client.embed_asset({})
        assert result == [0.0] * 3072
