"""Golden tests — rate_limit.py algoritmo puro (Sprint 21 PR2).

§8.4: testa as funções puras sem Redis real. Cobre:
  * limite padrão (1000) vs sensível (100)
  * construção de chave por janela horária
  * cálculo de janela (alinhada à hora)
  * headers RFC 6585
  * resultado permitido / bloqueado
  * fail-open sem Redis
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.shared.middleware.rate_limit import (
    RateLimitResult,
    _LIMITE_PADRAO,
    _LIMITE_SENSIVEL,
    _JANELA_SEG,
    SENSITIVE_PREFIXES,
    calcular_janela_atual,
    checar_rate_limit,
    construir_chave_redis,
    eh_endpoint_sensivel,
    limite_para_path,
    montar_headers_rate_limit,
)


# ── calcular_janela_atual ─────────────────────────────────────────────────────


def test_janela_alinhada_ao_inicio_da_hora():
    # ts = 14h37m42s em unix → janela = 14h00m00s
    ts_37min = 1_748_000_000 + 37 * 60 + 42  # dentro de uma hora
    janela = calcular_janela_atual(float(ts_37min))
    assert janela % _JANELA_SEG == 0


def test_janela_começo_exato_da_hora():
    # Calcula o próximo múltiplo de 3600 após um ts de referência
    ts_ref = 1_748_000_000
    ts_exato = (ts_ref // 3600) * 3600  # 485555 * 3600 = 1748001600... garantidamente múltiplo
    assert ts_exato % 3600 == 0
    assert calcular_janela_atual(float(ts_exato)) == ts_exato


def test_janelas_consecutivas_diferem_por_uma_hora():
    ts1 = 1_748_000_000
    ts2 = ts1 + _JANELA_SEG
    j1 = calcular_janela_atual(float(ts1))
    j2 = calcular_janela_atual(float(ts2))
    assert j2 - j1 == _JANELA_SEG


# ── eh_endpoint_sensivel + limite_para_path ───────────────────────────────────


@pytest.mark.parametrize("path", [
    "/v1/auth/login",
    "/v1/auth/register",
    "/v1/pgdas/transmitir",
    "/v1/sped/ecd/gerar",
    "/v1/notas/emitir",
    "/v1/certidoes/buscar",
])
def test_endpoints_sensiveis_reconhecidos(path: str):
    assert eh_endpoint_sensivel(path) is True
    assert limite_para_path(path) == _LIMITE_SENSIVEL


@pytest.mark.parametrize("path", [
    "/v1/empresas/lista",
    "/v1/fiscal/apuracoes",
    "/v1/lucro_presumido/irpj",
    "/healthz",
    "/v1/relatorios/dre",
])
def test_endpoints_padrão_nao_sensiveis(path: str):
    assert eh_endpoint_sensivel(path) is False
    assert limite_para_path(path) == _LIMITE_PADRAO


# ── construir_chave_redis ─────────────────────────────────────────────────────


def test_chave_redis_formato_correto():
    tenant = str(uuid4())
    janela = 1_748_000_000
    chave = construir_chave_redis(tenant, janela)
    assert chave == f"rl:{tenant}:{janela}"


def test_chave_redis_difere_por_tenant():
    t1, t2 = str(uuid4()), str(uuid4())
    janela = 1_748_000_000
    assert construir_chave_redis(t1, janela) != construir_chave_redis(t2, janela)


def test_chave_redis_difere_por_janela():
    tenant = str(uuid4())
    j1, j2 = 1_748_000_000, 1_748_003_600
    assert construir_chave_redis(tenant, j1) != construir_chave_redis(tenant, j2)


# ── montar_headers_rate_limit ─────────────────────────────────────────────────


def test_headers_contém_campos_rfc6585():
    result = RateLimitResult(
        permitido=True, contagem_atual=5, limite=1000,
        janela_reset_ts=int(time.time()) + 3600
    )
    headers = montar_headers_rate_limit(result, limite=1000, restante=995, reset_ts=result.janela_reset_ts)
    assert "X-RateLimit-Limit" in headers
    assert "X-RateLimit-Remaining" in headers
    assert "X-RateLimit-Reset" in headers
    assert headers["X-RateLimit-Limit"] == "1000"
    assert headers["X-RateLimit-Remaining"] == "995"


def test_headers_bloqueado_inclui_retry_after():
    result = RateLimitResult(
        permitido=False, contagem_atual=101, limite=100,
        janela_reset_ts=int(time.time()) + 1800
    )
    headers = montar_headers_rate_limit(result, limite=100, restante=0, reset_ts=result.janela_reset_ts)
    assert "Retry-After" in headers
    assert int(headers["Retry-After"]) > 0


def test_headers_restante_nunca_negativo():
    result = RateLimitResult(
        permitido=False, contagem_atual=200, limite=100,
        janela_reset_ts=int(time.time()) + 3600
    )
    headers = montar_headers_rate_limit(result, limite=100, restante=-100, reset_ts=result.janela_reset_ts)
    assert headers["X-RateLimit-Remaining"] == "0"


# ── checar_rate_limit (com Redis mockado) ────────────────────────────────────


@pytest.mark.asyncio
async def test_primeira_requisicao_permitida():
    redis_mock = AsyncMock()
    redis_mock.incr.return_value = 1
    redis_mock.expire = AsyncMock()

    tenant = str(uuid4())
    result = await checar_rate_limit(redis_mock, tenant, "/v1/relatorios/dre")

    assert result.permitido is True
    assert result.contagem_atual == 1
    assert result.limite == _LIMITE_PADRAO
    redis_mock.expire.assert_called_once()


@pytest.mark.asyncio
async def test_dentro_do_limite_padrao_permitido():
    redis_mock = AsyncMock()
    redis_mock.incr.return_value = 999
    redis_mock.expire = AsyncMock()

    result = await checar_rate_limit(redis_mock, str(uuid4()), "/v1/fiscal/apuracoes")
    assert result.permitido is True


@pytest.mark.asyncio
async def test_acima_do_limite_padrao_bloqueado():
    redis_mock = AsyncMock()
    redis_mock.incr.return_value = 1001
    redis_mock.expire = AsyncMock()

    result = await checar_rate_limit(redis_mock, str(uuid4()), "/v1/relatorios/dre")
    assert result.permitido is False
    assert result.motivo_bloqueio != ""


@pytest.mark.asyncio
async def test_acima_do_limite_sensivel_bloqueado():
    redis_mock = AsyncMock()
    redis_mock.incr.return_value = 101
    redis_mock.expire = AsyncMock()

    result = await checar_rate_limit(redis_mock, str(uuid4()), "/v1/pgdas/transmitir")
    assert result.permitido is False
    assert result.limite == _LIMITE_SENSIVEL


@pytest.mark.asyncio
async def test_redis_indisponivel_fail_open():
    """Se Redis levanta RedisError → fail-open (permite a requisição)."""
    import redis.asyncio as redis_async
    redis_mock = AsyncMock()
    redis_mock.incr.side_effect = redis_async.RedisError("connection refused")

    result = await checar_rate_limit(redis_mock, str(uuid4()), "/v1/relatorios/dre")
    assert result.permitido is True


@pytest.mark.asyncio
async def test_expire_chamado_somente_na_primeira_requisicao():
    """EXPIRE deve ser setado apenas quando contagem == 1 (primeira req da janela)."""
    redis_mock = AsyncMock()
    redis_mock.expire = AsyncMock()

    # Segunda requisição (contagem=2) — expire NÃO deve ser chamado
    redis_mock.incr.return_value = 2
    await checar_rate_limit(redis_mock, str(uuid4()), "/v1/relatorios/dre")
    redis_mock.expire.assert_not_called()

    # Primeira requisição (contagem=1) — expire DEVE ser chamado
    redis_mock.incr.return_value = 1
    await checar_rate_limit(redis_mock, str(uuid4()), "/v1/relatorios/dre")
    redis_mock.expire.assert_called_once()
