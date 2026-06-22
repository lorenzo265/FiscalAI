"""Cliente HTTP Pluggy — connect token, contas, transações, item status.

Princípios (§7.3, §8.9, §8.10):
* API key obtida via :class:`PluggyAuthClient` (cache Redis) e enviada no
  header ``X-API-KEY``.
* Retry exponencial só em ``httpx.TransportError``; 4xx/5xx sobem como
  ``PluggyErro``.
* 401 invalida o cache da API key (token pode ter vencido antes do TTL).
* Idempotência: o ``connect_token`` carrega ``clientUserId`` derivado do
  empresa_id — chamadas repetidas para o mesmo cliente são determinísticas.
"""

from __future__ import annotations

import time
from typing import cast

import httpx
import redis.asyncio as redis_async
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import Settings
from app.shared.exceptions import ItemNaoEncontrado, PluggyErro, PluggyTimeout
from app.shared.integrations.pluggy.auth import PluggyAuthClient
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)

_PATH_CONNECT_TOKEN = "/connect_token"  # nosec B105 — caminho de URL, não credencial
_PATH_ITEMS = "/items"
_PATH_ACCOUNTS = "/accounts"
_PATH_TRANSACTIONS = "/transactions"


class PluggyClient:
    """Cliente assíncrono do Pluggy — métodos retornam o dict bruto da API."""

    def __init__(
        self,
        settings: Settings,
        redis: redis_async.Redis[str] | None,
        *,
        http: httpx.AsyncClient | None = None,
        auth: PluggyAuthClient | None = None,
    ) -> None:
        self._base_url = settings.PLUGGY_BASE_URL.rstrip("/")
        self._http = http or httpx.AsyncClient(timeout=45.0)
        self._owns_http = http is None
        self._auth = auth or PluggyAuthClient(settings, redis, http=self._http)
        self._owns_auth = auth is None

    async def aclose(self) -> None:
        if self._owns_auth:
            await self._auth.aclose()
        if self._owns_http:
            await self._http.aclose()

    # ── Connect token (widget) ───────────────────────────────────────────────

    async def create_connect_token(
        self,
        *,
        client_user_id: str,
        webhook_url: str | None = None,
    ) -> JsonObject:
        """Cria connect_token para o widget JS do frontend.

        Args:
            client_user_id: Identificador estável do usuário/empresa (usamos
                ``empresa_id`` em string). Pluggy o passa de volta nos
                callbacks, permitindo correlacionar o item criado.
            webhook_url: URL pública opcional para callbacks pós-conexão.

        Returns:
            dict com ``{accessToken, expiresAt}``. O frontend usa
            ``accessToken`` para inicializar o widget.
        """
        body: JsonObject = {
            "options": {
                "clientUserId": client_user_id,
            }
        }
        if webhook_url:
            body["options"]["webhookUrl"] = webhook_url
        return await self._post_json(_PATH_CONNECT_TOKEN, body)

    # ── Items / Accounts / Transactions ──────────────────────────────────────

    async def get_item(self, item_id: str) -> JsonObject:
        """GET /items/{id} — retorna status e metadados do item."""
        return await self._get_json(f"{_PATH_ITEMS}/{item_id}")

    async def list_accounts(self, item_id: str) -> JsonObject:
        """GET /accounts?itemId={id} — lista contas vinculadas ao item."""
        return await self._get_json(_PATH_ACCOUNTS, params={"itemId": item_id})

    async def list_transactions(
        self,
        *,
        account_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
        page_size: int = 200,
        page: int = 1,
    ) -> JsonObject:
        """GET /transactions — paginação Pluggy via ``page`` + ``pageSize``.

        Args:
            account_id: ID Pluggy da conta.
            from_date: ISO 8601 (YYYY-MM-DD). Pluggy ignora horas.
            to_date: ISO 8601.
            page_size: Pluggy aceita até 500 por página; default 200.
        """
        params: dict[str, str | int] = {
            "accountId": account_id,
            "pageSize": page_size,
            "page": page,
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return await self._get_json(_PATH_TRANSACTIONS, params=params)

    # ── HTTP base ────────────────────────────────────────────────────────────

    @retry(
        wait=wait_exponential_jitter(initial=2, max=30),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def _post_json(self, path: str, payload: JsonObject) -> JsonObject:
        return await self._call("POST", path, json=payload)

    @retry(
        wait=wait_exponential_jitter(initial=2, max=30),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def _get_json(
        self, path: str, params: JsonObject | None = None
    ) -> JsonObject:
        return await self._call("GET", path, params=params)

    async def _call(
        self,
        method: str,
        path: str,
        *,
        json: JsonObject | None = None,
        params: JsonObject | None = None,
    ) -> JsonObject:
        api_key = await self._auth.api_key()
        url = f"{self._base_url}{path}"
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }
        inicio = time.monotonic()
        try:
            resp = await self._http.request(
                method, url, headers=headers, json=json, params=params
            )
        except httpx.TransportError as exc:
            raise PluggyTimeout(f"Timeout Pluggy em {path}: {exc}") from exc

        latencia_ms = int((time.monotonic() - inicio) * 1000)

        if resp.status_code == 401:
            await self._auth.invalidar()
            raise PluggyErro(
                f"Pluggy {path} retornou 401 (API key vencida ou inválida)",
                status_upstream=401,
            )

        if resp.status_code == 404 and path.startswith(_PATH_ITEMS):
            raise ItemNaoEncontrado(f"Pluggy item não encontrado em {path}")

        if resp.status_code >= 400:
            log.warning(
                "pluggy.call.erro",
                method=method,
                path=path,
                status_http=resp.status_code,
                latencia_ms=latencia_ms,
                corpo=resp.text[:300],
            )
            raise PluggyErro(
                f"Pluggy {path} retornou {resp.status_code}: {resp.text[:300]}",
                status_upstream=resp.status_code,
            )

        log.info(
            "pluggy.call.ok",
            method=method,
            path=path,
            status_http=resp.status_code,
            latencia_ms=latencia_ms,
        )
        return cast(JsonObject, resp.json())
