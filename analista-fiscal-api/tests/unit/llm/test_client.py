"""Testes unitários do LLMClient — roteamento, cache e integração com Ollama/Gemini mockados."""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.llm.client import (
    FonteFato,
    LLMClient,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    _extrair_citacoes,
)


@pytest.fixture
def mock_redis() -> AsyncMock:
    r = AsyncMock()
    r.get.return_value = None  # cache miss por padrão
    r.setex.return_value = True
    return r


@pytest.fixture
def mock_settings() -> MagicMock:
    s = MagicMock()
    s.OLLAMA_URL = "http://localhost:11434"
    s.GEMINI_API_KEY = "test-key"
    s.LANGFUSE_HOST = ""  # Langfuse desativado
    return s


@pytest.fixture
def client(mock_settings: MagicMock, mock_redis: AsyncMock) -> LLMClient:
    return LLMClient(settings=mock_settings, redis=mock_redis)


# ── Roteamento ───────────────────────────────────────────────────────────────


def test_roteia_pii_para_ollama(client: LLMClient) -> None:
    req = LLMRequest(prompt="teste", contem_pii=True)
    assert client._rotear(req) == LLMProvider.OLLAMA_GEMMA_3_4B


def test_roteia_sem_pii_para_flash_lite(client: LLMClient) -> None:
    req = LLMRequest(prompt="teste", contem_pii=False)
    assert client._rotear(req) == LLMProvider.GEMINI_2_5_FLASH_LITE


def test_roteia_padrao_sem_pii(client: LLMClient) -> None:
    """Por padrão (contem_pii=False) usa Flash Lite (custo baixo)."""
    req = LLMRequest(prompt="Qual o DAS?")
    assert client._rotear(req) == LLMProvider.GEMINI_2_5_FLASH_LITE


# ── Cache ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_miss_retorna_none(client: LLMClient, mock_redis: AsyncMock) -> None:
    mock_redis.get.return_value = None
    result = await client._get_cache("chave-teste", LLMProvider.GEMINI_2_5_FLASH_LITE)
    assert result is None


@pytest.mark.asyncio
async def test_cache_hit_retorna_resposta(client: LLMClient, mock_redis: AsyncMock) -> None:
    resp = LLMResponse(
        texto="Resposta cacheada",
        citacoes=[],
        tokens_input=10,
        tokens_output=20,
        tokens_cached=5,
        custo_usd=Decimal("0.000005"),
        provider=LLMProvider.GEMINI_2_5_FLASH_LITE,
        latencia_ms=100,
    )
    mock_redis.get.return_value = resp.model_dump_json()

    result = await client._get_cache("chave-teste", LLMProvider.GEMINI_2_5_FLASH_LITE)
    assert result is not None
    assert result.texto == "Resposta cacheada"
    assert result.tokens_input == 10


@pytest.mark.asyncio
async def test_set_cache_grava_redis(client: LLMClient, mock_redis: AsyncMock) -> None:
    resp = LLMResponse(
        texto="Teste",
        citacoes=[],
        tokens_input=5,
        tokens_output=10,
        tokens_cached=0,
        custo_usd=Decimal("0"),
        provider=LLMProvider.OLLAMA_GEMMA_3_4B,
        latencia_ms=50,
    )
    await client._set_cache("chave", LLMProvider.OLLAMA_GEMMA_3_4B, resp, 3600)

    mock_redis.setex.assert_called_once()
    args = mock_redis.setex.call_args
    assert "llm:cache:ollama-gemma3-4b:chave" in args[0][0]
    assert args[0][1] == 3600


@pytest.mark.asyncio
async def test_cache_json_invalido_retorna_none(client: LLMClient, mock_redis: AsyncMock) -> None:
    mock_redis.get.return_value = "json-inválido{"
    result = await client._get_cache("chave", LLMProvider.GEMINI_2_5_FLASH_LITE)
    assert result is None


# ── Chamada Ollama ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chamar_ollama_retorna_resposta(
    mock_settings: MagicMock, mock_redis: AsyncMock
) -> None:
    mock_http = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": "Resposta do Gemma"},
        "eval_count": 50,
        "prompt_eval_count": 100,
    }
    mock_response.raise_for_status = MagicMock()
    mock_http.post.return_value = mock_response

    client = LLMClient(settings=mock_settings, redis=mock_redis, http_client=mock_http)
    req = LLMRequest(prompt="Quanto pago de DAS?", contem_pii=True)

    resp = await client.chamar(req, provider=LLMProvider.OLLAMA_GEMMA_3_4B)

    assert resp.texto == "Resposta do Gemma"
    assert resp.tokens_input == 100
    assert resp.tokens_output == 50
    assert resp.custo_usd == Decimal("0")
    assert resp.provider == LLMProvider.OLLAMA_GEMMA_3_4B


@pytest.mark.asyncio
async def test_chamar_ollama_usa_format_json_quando_schema(
    mock_settings: MagicMock, mock_redis: AsyncMock
) -> None:
    from pydantic import BaseModel

    class MeuSchema(BaseModel):
        campo: str

    mock_http = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": '{"campo": "valor"}'},
        "eval_count": 30,
        "prompt_eval_count": 60,
    }
    mock_response.raise_for_status = MagicMock()
    mock_http.post.return_value = mock_response

    client = LLMClient(settings=mock_settings, redis=mock_redis, http_client=mock_http)
    req = LLMRequest(prompt="extrair", response_schema=MeuSchema, contem_pii=True)

    await client.chamar(req, provider=LLMProvider.OLLAMA_GEMMA_3_4B)

    call_kwargs: dict[str, Any] = mock_http.post.call_args[1]
    payload = call_kwargs.get("json", {})
    assert payload.get("format") == "json"


@pytest.mark.asyncio
async def test_chamar_ollama_http_error_vira_llm_indisponivel(
    mock_settings: MagicMock, mock_redis: AsyncMock
) -> None:
    import httpx

    from app.shared.exceptions import LLMIndisponivel

    mock_http = AsyncMock()
    mock_http.post.side_effect = httpx.ConnectError("conexão recusada")

    client = LLMClient(settings=mock_settings, redis=mock_redis, http_client=mock_http)
    req = LLMRequest(prompt="test")

    with pytest.raises(LLMIndisponivel) as exc_info:
        await client.chamar(req, provider=LLMProvider.OLLAMA_GEMMA_3_4B)

    assert "Ollama indisponível" in str(exc_info.value)


# ── Chamada Gemini ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chamar_gemini_sem_api_key_lanca_llm_indisponivel(
    mock_redis: AsyncMock,
) -> None:
    from app.shared.exceptions import LLMIndisponivel

    settings = MagicMock()
    settings.GEMINI_API_KEY = ""
    settings.OLLAMA_URL = "http://localhost:11434"
    settings.LANGFUSE_HOST = ""

    client = LLMClient(settings=settings, redis=mock_redis)
    req = LLMRequest(prompt="test")

    with pytest.raises(LLMIndisponivel) as exc_info:
        await client.chamar(req, provider=LLMProvider.GEMINI_2_5_FLASH_LITE)

    assert "GEMINI_API_KEY" in str(exc_info.value)


# ── Langfuse ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_langfuse_skip_quando_host_vazio(
    client: LLMClient, mock_redis: AsyncMock
) -> None:
    """Sem LANGFUSE_HOST configurado, não deve tentar importar langfuse."""
    resp = LLMResponse(
        texto="ok",
        citacoes=[],
        tokens_input=1,
        tokens_output=1,
        tokens_cached=0,
        custo_usd=Decimal("0"),
        provider=LLMProvider.GEMINI_2_5_FLASH_LITE,
        latencia_ms=100,
    )
    req = LLMRequest(prompt="test")
    # Não deve levantar exceção mesmo sem langfuse instalado
    await client._registrar_langfuse(req, resp)


# ── aclose ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_aclose_fecha_http(mock_settings: MagicMock, mock_redis: AsyncMock) -> None:
    mock_http = AsyncMock()
    client = LLMClient(settings=mock_settings, redis=mock_redis, http_client=mock_http)
    await client.aclose()
    mock_http.aclose.assert_called_once()


# ── _extrair_citacoes (FIX #4 — §8.5) ───────────────────────────────────────


def _fonte(id_: str, payload: str = "conteudo") -> FonteFato:
    return FonteFato(id=id_, tipo="apuracao_das", payload=payload)


def test_extrair_citacoes_parseia_id_valido() -> None:
    """LLM referencia [ap-001] que está nas fontes → Citacao populada."""
    texto = "O DAS foi R$ 1.234,56 conforme apuração [ap-001]."
    fontes = [_fonte("ap-001", "DAS: R$ 1.234,56")]
    resultado = _extrair_citacoes(texto, fontes)
    assert len(resultado) == 1
    assert resultado[0].fato_id == "ap-001"
    assert "DAS: R$ 1.234,56" in resultado[0].trecho_citado


def test_extrair_citacoes_descarta_id_inexistente() -> None:
    """LLM inventa [id-fantasma] que não existe nas fontes → descartado."""
    texto = "Resposta fabricada [id-fantasma]."
    fontes = [_fonte("ap-001", "DAS: R$ 1.234,56")]
    resultado = _extrair_citacoes(texto, fontes)
    assert resultado == []


def test_extrair_citacoes_sem_fontes_retorna_vazio() -> None:
    """Sem fontes disponíveis, nenhuma citação pode ser válida."""
    texto = "Resposta [ap-001]."
    resultado = _extrair_citacoes(texto, [])
    assert resultado == []


def test_extrair_citacoes_multiplos_ids() -> None:
    """Múltiplos IDs válidos → uma Citacao por ID."""
    texto = "Faturamento [mov-01] e DAS [ap-01]."
    fontes = [_fonte("mov-01", "Faturamento: R$ 35.000"), _fonte("ap-01", "DAS: R$ 1.200")]
    resultado = _extrair_citacoes(texto, fontes)
    ids = {c.fato_id for c in resultado}
    assert ids == {"mov-01", "ap-01"}


def test_extrair_citacoes_deduplica_mesmo_id() -> None:
    """ID repetido no texto → apenas uma Citacao."""
    texto = "O DAS [ap-001] foi pago [ap-001]."
    fontes = [_fonte("ap-001", "DAS pago")]
    resultado = _extrair_citacoes(texto, fontes)
    assert len(resultado) == 1


def test_extrair_citacoes_id_parcialmente_invalido() -> None:
    """Mistura de IDs válidos e inválidos → só os válidos."""
    texto = "Dados [real-001] e imaginado [fake-999]."
    fontes = [_fonte("real-001", "Dado real")]
    resultado = _extrair_citacoes(texto, fontes)
    assert len(resultado) == 1
    assert resultado[0].fato_id == "real-001"


@pytest.mark.asyncio
async def test_chamar_ollama_popula_citacoes_de_fontes(
    mock_settings: MagicMock, mock_redis: AsyncMock
) -> None:
    """_chamar_ollama deve popular citacoes quando o modelo cita IDs válidos."""
    mock_http = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": "O DAS foi R$ 1.234,56 [ap-2026-05] conforme apuração."},
        "eval_count": 50,
        "prompt_eval_count": 100,
    }
    mock_response.raise_for_status = MagicMock()
    mock_http.post.return_value = mock_response

    client = LLMClient(settings=mock_settings, redis=mock_redis, http_client=mock_http)
    fonte = FonteFato(id="ap-2026-05", tipo="apuracao_das", payload="DAS: R$ 1.234,56")
    req = LLMRequest(
        prompt="Qual meu DAS?",
        contem_pii=True,
        fontes_disponiveis=[fonte],
    )

    resp = await client.chamar(req, provider=LLMProvider.OLLAMA_GEMMA_3_4B)

    assert len(resp.citacoes) == 1
    assert resp.citacoes[0].fato_id == "ap-2026-05"


@pytest.mark.asyncio
async def test_chamar_ollama_descarta_citacao_id_invalido(
    mock_settings: MagicMock, mock_redis: AsyncMock
) -> None:
    """_chamar_ollama deve descartar IDs que não existem nas fontes."""
    mock_http = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": "Resposta inventada [id-nao-existe]."},
        "eval_count": 20,
        "prompt_eval_count": 40,
    }
    mock_response.raise_for_status = MagicMock()
    mock_http.post.return_value = mock_response

    client = LLMClient(settings=mock_settings, redis=mock_redis, http_client=mock_http)
    fonte = FonteFato(id="ap-001", tipo="apuracao_das", payload="DAS real")
    req = LLMRequest(
        prompt="Qual meu DAS?",
        contem_pii=True,
        fontes_disponiveis=[fonte],
    )

    resp = await client.chamar(req, provider=LLMProvider.OLLAMA_GEMMA_3_4B)

    assert resp.citacoes == []
