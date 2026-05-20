"""Testes unitários do módulo de embeddings — mock do Ollama."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.memoria.embeddings import _EMBED_DIM, gerar_embedding


@pytest.fixture
def mock_client_ok() -> AsyncMock:
    """Mock que retorna embedding de 768 dimensões."""
    client = AsyncMock()
    resp = MagicMock()
    resp.json.return_value = {"embeddings": [[0.1] * _EMBED_DIM]}
    resp.raise_for_status = MagicMock()
    client.post.return_value = resp
    return client


@pytest.fixture
def mock_client_dim_errada() -> AsyncMock:
    """Mock que retorna embedding de dimensão incorreta."""
    client = AsyncMock()
    resp = MagicMock()
    resp.json.return_value = {"embeddings": [[0.1] * 512]}  # dimensão errada
    resp.raise_for_status = MagicMock()
    client.post.return_value = resp
    return client


async def test_gerar_embedding_retorna_768_dims(mock_client_ok: AsyncMock) -> None:
    result = await gerar_embedding("Texto de teste", "http://localhost:11434", mock_client_ok)
    assert len(result) == _EMBED_DIM
    assert all(isinstance(f, float) for f in result)


async def test_gerar_embedding_chama_endpoint_correto(mock_client_ok: AsyncMock) -> None:
    await gerar_embedding("teste", "http://ollama:11434", mock_client_ok)
    mock_client_ok.post.assert_called_once()
    call_url = mock_client_ok.post.call_args[0][0]
    assert "/api/embed" in call_url


async def test_gerar_embedding_passa_modelo_correto(mock_client_ok: AsyncMock) -> None:
    await gerar_embedding("teste", "http://localhost:11434", mock_client_ok)
    call_json = mock_client_ok.post.call_args[1]["json"]
    assert call_json["model"] == "nomic-embed-text"
    assert call_json["input"] == "teste"


async def test_gerar_embedding_levanta_erro_dim_incorreta(mock_client_dim_errada: AsyncMock) -> None:
    with pytest.raises(ValueError, match="768"):
        await gerar_embedding("teste", "http://localhost:11434", mock_client_dim_errada)
