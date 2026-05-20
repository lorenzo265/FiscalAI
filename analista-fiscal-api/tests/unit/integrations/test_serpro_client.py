"""Testes unitários do SerproClient + SerproOAuthClient (Sprint 6 PR1).

Mockamos a camada httpx para isolar a lógica de OAuth (cache Redis, retry)
e a montagem de payload Integra Contador.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.config import Settings
from app.shared.exceptions import SerproErro, SerproOAuthErro, SerproTimeout
from app.shared.integrations.serpro.client import SerproClient
from app.shared.integrations.serpro.oauth import SerproOAuthClient


def _settings() -> Settings:
    return Settings(
        SERPRO_CONSUMER_KEY="ck-test",
        SERPRO_CONSUMER_SECRET="cs-test",
        SERPRO_BASE_URL="https://serpro.test",
    )


# ── SerproOAuthClient ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_oauth_cache_redis_evita_segunda_chamada() -> None:
    """Token em cache deve ser reutilizado — segundo access_token() não chama HTTP."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value="cached-token")
    redis.setex = AsyncMock()

    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock()

    oauth = SerproOAuthClient(_settings(), redis, http=http)
    token1 = await oauth.access_token()
    token2 = await oauth.access_token()

    assert token1 == "cached-token"
    assert token2 == "cached-token"
    http.post.assert_not_called()


@pytest.mark.asyncio
async def test_oauth_solicita_token_quando_cache_vazio() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json = MagicMock(return_value={"access_token": "novo-tk", "expires_in": 3600})

    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    oauth = SerproOAuthClient(_settings(), redis, http=http)
    token = await oauth.access_token()

    assert token == "novo-tk"
    http.post.assert_awaited_once()
    redis.setex.assert_awaited_once()
    # TTL salvo deve ser < expires_in (margem subtraída)
    ttl_arg = redis.setex.await_args.args[1]
    assert 30 <= ttl_arg < 3600


@pytest.mark.asyncio
async def test_oauth_sem_credenciais_levanta() -> None:
    settings = Settings(SERPRO_CONSUMER_KEY="", SERPRO_CONSUMER_SECRET="")
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)

    http = MagicMock(spec=httpx.AsyncClient)
    oauth = SerproOAuthClient(settings, redis, http=http)

    with pytest.raises(SerproOAuthErro, match="Credenciais SERPRO ausentes"):
        await oauth.access_token()


@pytest.mark.asyncio
async def test_oauth_transport_error_vira_serpro_timeout() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)

    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(side_effect=httpx.ConnectError("boom"))

    oauth = SerproOAuthClient(_settings(), redis, http=http)

    with pytest.raises(SerproTimeout):
        await oauth.access_token()


@pytest.mark.asyncio
async def test_oauth_status_diferente_de_200_levanta() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 401
    response.text = "invalid_credentials"
    response.json = MagicMock(return_value={})

    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    oauth = SerproOAuthClient(_settings(), redis, http=http)

    with pytest.raises(SerproOAuthErro, match="401"):
        await oauth.access_token()


# ── SerproClient ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_emitir_cnd_envia_payload_integra_contador() -> None:
    """O payload enviado deve seguir o formato Integra Contador (contratante, autor, contribuinte)."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value="tk")
    redis.setex = AsyncMock()

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json = MagicMock(
        return_value={"dados": {"numero": "ABC-123", "situacao": "Negativa"}}
    )

    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    client = SerproClient(_settings(), redis, http=http)
    result = await client.emitir_certidao_cnd(
        "12345678000195", idempotency_key="key-1"
    )

    assert result["dados"]["situacao"] == "Negativa"
    chamada = http.post.await_args
    payload = chamada.kwargs["json"]
    assert payload["contratante"]["numero"] == "12345678000195"
    assert payload["pedidoDados"]["idServico"] == "EMITECERTIDAOCND"
    # idempotency_key vai no header
    assert chamada.kwargs["headers"]["X-Request-Tag"] == "key-1"
    assert chamada.kwargs["headers"]["Authorization"] == "Bearer tk"


@pytest.mark.asyncio
async def test_serpro_4xx_levanta_serpro_erro() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value="tk")

    response = MagicMock(spec=httpx.Response)
    response.status_code = 422
    response.text = "validation_failed"

    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    client = SerproClient(_settings(), redis, http=http)
    with pytest.raises(SerproErro, match="422"):
        await client.emitir_certidao_cnd("12345678000195", idempotency_key="x")


@pytest.mark.asyncio
async def test_serpro_401_invalida_cache_token() -> None:
    """Em 401, o cliente invalida o cache OAuth antes de propagar."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value="tk-vencido")
    redis.delete = AsyncMock()

    response = MagicMock(spec=httpx.Response)
    response.status_code = 401
    response.text = "token_expired"

    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    client = SerproClient(_settings(), redis, http=http)
    with pytest.raises(SerproErro):
        await client.emitir_certidao_cnd("12345678000195", idempotency_key="x")

    redis.delete.assert_awaited()


# ── PGDAS-D + e-CAC (PR2) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transmitir_pgdas_d_envia_dados_em_json_compacto() -> None:
    """O subobjeto `pedidoDados.dados` deve ser JSON string compactado."""
    import json

    redis = MagicMock()
    redis.get = AsyncMock(return_value="tk")
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json = MagicMock(return_value={"dados": {"numeroDeclaracao": "0001"}})
    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    client = SerproClient(_settings(), redis, http=http)
    await client.transmitir_pgdas_d(
        cnpj="12345678000195",
        periodo_apuracao="202604",
        dados_declaracao={
            "receitaBrutaTotal": "10000.00",
            "estabelecimentos": [{"cnpj": "12345678000195", "tributada": "10000.00"}],
        },
        idempotency_key="pgdas-2026-04",
    )

    payload = http.post.await_args.kwargs["json"]
    assert payload["pedidoDados"]["idSistema"] == "PGDASD"
    assert payload["pedidoDados"]["idServico"] == "TRANSDECLARACAO11"
    # dados é string JSON
    dados_str = payload["pedidoDados"]["dados"]
    assert isinstance(dados_str, str)
    parsed = json.loads(dados_str)
    assert parsed["periodoApuracao"] == "202604"
    assert parsed["receitaBrutaTotal"] == "10000.00"
    # JSON compactado (sem espaços supérfluos)
    assert ", " not in dados_str
    assert ": " not in dados_str


@pytest.mark.asyncio
async def test_transmitir_defis_payload_pgdasd_defis21() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value="tk")
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json = MagicMock(return_value={"dados": {"numeroDeclaracao": "DEFIS-1"}})
    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    client = SerproClient(_settings(), redis, http=http)
    await client.transmitir_defis(
        cnpj="12345678000195",
        ano_base=2025,
        dados_declaracao={"receitaBrutaAnual": "120000.00"},
        idempotency_key="key-defis-2025",
    )

    payload = http.post.await_args.kwargs["json"]
    assert payload["pedidoDados"]["idSistema"] == "PGDASD"
    assert payload["pedidoDados"]["idServico"] == "TRANSDECLDEFIS21"


@pytest.mark.asyncio
async def test_transmitir_dasn_simei_payload_dasnsimei() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value="tk")
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json = MagicMock(return_value={"dados": {"numeroDeclaracao": "DASN-1"}})
    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    client = SerproClient(_settings(), redis, http=http)
    await client.transmitir_dasn_simei(
        cnpj="12345678000195",
        ano_base=2025,
        dados_declaracao={"receitaBrutaAnual": "50000.00"},
        idempotency_key="key-dasn-2025",
    )

    payload = http.post.await_args.kwargs["json"]
    assert payload["pedidoDados"]["idSistema"] == "DASNSIMEI"
    assert payload["pedidoDados"]["idServico"] == "TRANSDECLARACAO13"


@pytest.mark.asyncio
async def test_listar_caixa_postal_envia_payload_consulta() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value="tk")
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json = MagicMock(return_value={"dados": {"mensagens": []}})
    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    client = SerproClient(_settings(), redis, http=http)
    await client.listar_caixa_postal_e_cac(
        cnpj="12345678000195",
        idempotency_key="ecac-2026-05-16",
        somente_nao_lidas=True,
    )

    chamada = http.post.await_args
    assert chamada.args[0].endswith("/Consultar")
    payload = chamada.kwargs["json"]
    assert payload["pedidoDados"]["idSistema"] == "CAIXAPOSTAL"
    assert payload["pedidoDados"]["idServico"] == "MSGCONTRIBUINTE51"
