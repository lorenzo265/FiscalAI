"""Testes unitários PluggyAuthClient + PluggyClient (Sprint 7 PR1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.config import Settings
from app.shared.exceptions import (
    ItemNaoEncontrado,
    PluggyErro,
    PluggyOAuthErro,
    PluggyTimeout,
)
from app.shared.integrations.pluggy.auth import PluggyAuthClient
from app.shared.integrations.pluggy.client import PluggyClient


def _settings() -> Settings:
    return Settings(
        PLUGGY_CLIENT_ID="cid-test",
        PLUGGY_CLIENT_SECRET="csec-test",
        PLUGGY_BASE_URL="https://api.pluggy.test",
    )


# ── PluggyAuthClient ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auth_cache_hit_evita_http() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value="cached-apikey")
    redis.setex = AsyncMock()

    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock()

    auth = PluggyAuthClient(_settings(), redis, http=http)
    key1 = await auth.api_key()
    key2 = await auth.api_key()
    assert key1 == "cached-apikey"
    assert key2 == "cached-apikey"
    http.post.assert_not_called()


@pytest.mark.asyncio
async def test_auth_cache_miss_chama_endpoint() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json = MagicMock(return_value={"apiKey": "new-apikey"})

    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    auth = PluggyAuthClient(_settings(), redis, http=http)
    key = await auth.api_key()

    assert key == "new-apikey"
    http.post.assert_awaited_once()
    chamada = http.post.await_args
    # Pluggy espera JSON body com clientId + clientSecret
    payload = chamada.kwargs["json"]
    assert payload["clientId"] == "cid-test"
    assert payload["clientSecret"] == "csec-test"
    redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_sem_credenciais_levanta() -> None:
    settings = Settings(PLUGGY_CLIENT_ID="", PLUGGY_CLIENT_SECRET="")
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)

    http = MagicMock(spec=httpx.AsyncClient)
    auth = PluggyAuthClient(settings, redis, http=http)

    with pytest.raises(PluggyOAuthErro, match="Credenciais Pluggy ausentes"):
        await auth.api_key()


@pytest.mark.asyncio
async def test_auth_transport_error_vira_timeout() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)

    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(side_effect=httpx.ConnectError("boom"))

    auth = PluggyAuthClient(_settings(), redis, http=http)
    with pytest.raises(PluggyTimeout):
        await auth.api_key()


@pytest.mark.asyncio
async def test_auth_4xx_levanta() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 401
    response.text = "invalid_credentials"
    response.json = MagicMock(return_value={})

    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    auth = PluggyAuthClient(_settings(), redis, http=http)
    with pytest.raises(PluggyOAuthErro, match="401"):
        await auth.api_key()


# ── PluggyClient ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_connect_token_envia_client_user_id() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value="ak")

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json = MagicMock(
        return_value={
            "accessToken": "tk-connect-123",
            "expiresAt": "2026-05-17T15:00:00+00:00",
        }
    )

    http = MagicMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(return_value=response)

    client = PluggyClient(_settings(), redis, http=http)
    result = await client.create_connect_token(client_user_id="empresa-abc")

    assert result["accessToken"] == "tk-connect-123"
    chamada = http.request.await_args
    assert chamada.args[0] == "POST"
    assert chamada.args[1].endswith("/connect_token")
    body = chamada.kwargs["json"]
    assert body["options"]["clientUserId"] == "empresa-abc"
    headers = chamada.kwargs["headers"]
    assert headers["X-API-KEY"] == "ak"


@pytest.mark.asyncio
async def test_create_connect_token_com_webhook_url() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value="ak")
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json = MagicMock(return_value={"accessToken": "tk"})

    http = MagicMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(return_value=response)

    client = PluggyClient(_settings(), redis, http=http)
    await client.create_connect_token(
        client_user_id="x", webhook_url="https://api.test/wh"
    )
    body = http.request.await_args.kwargs["json"]
    assert body["options"]["webhookUrl"] == "https://api.test/wh"


@pytest.mark.asyncio
async def test_get_item_404_levanta_item_nao_encontrado() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value="ak")

    response = MagicMock(spec=httpx.Response)
    response.status_code = 404
    response.text = "not_found"

    http = MagicMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(return_value=response)

    client = PluggyClient(_settings(), redis, http=http)
    with pytest.raises(ItemNaoEncontrado):
        await client.get_item("inexistente")


@pytest.mark.asyncio
async def test_pluggy_401_invalida_cache() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value="ak-vencida")
    redis.delete = AsyncMock()

    response = MagicMock(spec=httpx.Response)
    response.status_code = 401
    response.text = "unauthorized"

    http = MagicMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(return_value=response)

    client = PluggyClient(_settings(), redis, http=http)
    with pytest.raises(PluggyErro):
        await client.get_item("xyz")
    redis.delete.assert_awaited()


@pytest.mark.asyncio
async def test_list_transactions_envia_paginacao() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value="ak")
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json = MagicMock(return_value={"results": [], "total": 0})

    http = MagicMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(return_value=response)

    client = PluggyClient(_settings(), redis, http=http)
    await client.list_transactions(
        account_id="acc-1",
        from_date="2026-04-01",
        to_date="2026-04-30",
        page_size=100,
        page=2,
    )

    params = http.request.await_args.kwargs["params"]
    assert params["accountId"] == "acc-1"
    assert params["pageSize"] == 100
    assert params["page"] == 2
    assert params["from"] == "2026-04-01"
    assert params["to"] == "2026-04-30"


@pytest.mark.asyncio
async def test_list_accounts_envia_item_id() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value="ak")
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json = MagicMock(return_value={"results": []})

    http = MagicMock(spec=httpx.AsyncClient)
    http.request = AsyncMock(return_value=response)

    client = PluggyClient(_settings(), redis, http=http)
    await client.list_accounts("item-abc")
    params = http.request.await_args.kwargs["params"]
    assert params["itemId"] == "item-abc"
