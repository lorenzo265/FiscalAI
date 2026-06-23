"""Cliente OAuth do Pluggy — obtém + cacheia API key (TTL ~2h).

Pluggy usa POST /auth com `clientId` + `clientSecret` no JSON body, retornando
`apiKey`. Diferente do SERPRO (que segue OAuth2 padrão), o Pluggy não devolve
um `expires_in` — o token expira ~2h, e renovamos com margem de segurança.

Cache: Redis com TTL fixo. Lock asyncio anti-thundering-herd.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import redis.asyncio as redis_async
import structlog

from app.config import Settings
from app.shared.exceptions import PluggyOAuthErro, PluggyTimeout
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)

_API_KEY_REDIS_KEY = "pluggy:api_key"
_AUTH_PATH = "/auth"
# TTL fixo — Pluggy não publica `expires_in` na resposta; documentação diz 2h.
_API_KEY_TTL_SEC = 2 * 60 * 60


class PluggyAuthClient:
    """Obtém + cacheia a API key Pluggy usada como header X-API-KEY."""

    def __init__(
        self,
        settings: Settings,
        redis: redis_async.Redis[str] | None,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = settings.PLUGGY_CLIENT_ID
        self._client_secret = settings.PLUGGY_CLIENT_SECRET
        self._base_url = settings.PLUGGY_BASE_URL.rstrip("/")
        self._ttl_margin_sec = settings.PLUGGY_API_KEY_TTL_MARGIN_SEC
        self._redis = redis
        self._http = http or httpx.AsyncClient(timeout=20.0)
        self._owns_http = http is None
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def api_key(self) -> str:
        """Retorna API key válida; renova se cache vazio."""
        cached = await self._buscar_cache()
        if cached:
            return cached

        async with self._lock:
            cached = await self._buscar_cache()
            if cached:
                return cached
            key = await self._solicitar_nova_key()
            await self._salvar_cache(key)
            return key

    async def invalidar(self) -> None:
        """Força próxima chamada a renovar (uso em retry após 401)."""
        if self._redis is None:
            return
        try:
            await self._redis.delete(_API_KEY_REDIS_KEY)
        except Exception:  # pragma: no cover
            log.warning("pluggy.auth.cache_delete_falhou")

    async def _buscar_cache(self) -> str | None:
        if self._redis is None:
            return None
        try:
            value = await self._redis.get(_API_KEY_REDIS_KEY)
            return value if value else None
        except Exception:  # pragma: no cover
            log.warning("pluggy.auth.cache_read_falhou")
            return None

    async def _salvar_cache(self, key: str) -> None:
        if self._redis is None:
            return
        ttl = max(_API_KEY_TTL_SEC - self._ttl_margin_sec, 60)
        try:
            await self._redis.setex(_API_KEY_REDIS_KEY, ttl, key)
        except Exception:  # pragma: no cover
            log.warning("pluggy.auth.cache_write_falhou")

    async def _solicitar_nova_key(self) -> str:
        if not self._client_id or not self._client_secret:
            raise PluggyOAuthErro(
                "Credenciais Pluggy ausentes — defina PLUGGY_CLIENT_ID/SECRET."
            )

        url = f"{self._base_url}{_AUTH_PATH}"
        inicio = time.monotonic()
        try:
            resp = await self._http.post(
                url,
                json={
                    "clientId": self._client_id,
                    "clientSecret": self._client_secret,
                },
                headers={"Content-Type": "application/json"},
            )
        except httpx.TransportError as exc:
            raise PluggyTimeout(f"Falha ao falar com Pluggy /auth: {exc}") from exc

        latencia_ms = int((time.monotonic() - inicio) * 1000)

        if resp.status_code != 200:
            log.warning(
                "pluggy.auth.falhou",
                status_http=resp.status_code,
                corpo=resp.text[:200],
                latencia_ms=latencia_ms,
            )
            raise PluggyOAuthErro(
                f"Pluggy /auth retornou {resp.status_code}: {resp.text[:300]}"
            )

        body: JsonObject = resp.json()
        key = str(body.get("apiKey", ""))
        if not key:
            raise PluggyOAuthErro("Pluggy /auth respondeu sem apiKey")

        log.info("pluggy.auth.api_key_emitida", latencia_ms=latencia_ms)
        return key
