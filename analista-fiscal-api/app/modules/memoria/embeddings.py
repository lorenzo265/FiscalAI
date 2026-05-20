"""Geração de embeddings via Ollama nomic-embed-text (768 dimensões).

Dados com PII (CPF, valores, CNPJ real) NUNCA vão para Gemini — ficam locais (§8.7).
Este módulo gera embeddings sempre via Ollama independente do provider LLM configurado.
"""
from __future__ import annotations

import httpx
import structlog

log = structlog.get_logger(__name__)

_OLLAMA_EMBED_MODEL = "nomic-embed-text"
_EMBED_DIM = 768


async def gerar_embedding(
    texto: str,
    ollama_url: str,
    http_client: httpx.AsyncClient | None = None,
) -> list[float]:
    """Gera embedding de 768 dimensões via nomic-embed-text no Ollama local.

    Args:
        texto: Texto a ser vetorizado.
        ollama_url: URL base do Ollama (ex: http://localhost:11434).
        http_client: Cliente HTTP reutilizável (opcional — cria um temporário se None).

    Returns:
        Lista de 768 floats (vetor de embedding).

    Raises:
        httpx.HTTPError: Se Ollama não estiver acessível.
        ValueError: Se a dimensão do embedding retornado for diferente de 768.
    """
    payload = {"model": _OLLAMA_EMBED_MODEL, "input": texto}

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=30.0)

    try:
        response = await client.post(f"{ollama_url}/api/embed", json=payload)
        response.raise_for_status()
        data = response.json()
        # Ollama retorna {"embeddings": [[float, ...]]}
        embedding: list[float] = data["embeddings"][0]
    finally:
        if owns_client:
            await client.aclose()

    if len(embedding) != _EMBED_DIM:
        raise ValueError(
            f"nomic-embed-text retornou {len(embedding)} dims, esperado {_EMBED_DIM}. "
            f"Verifique se o modelo está instalado: ollama pull {_OLLAMA_EMBED_MODEL}"
        )

    log.debug("embedding.gerado", dim=len(embedding), texto_len=len(texto))
    return embedding
