"""Cliente OAuth2 do API Gateway SERPRO (client_credentials).

A SERPRO usa o padrão OAuth2 Client Credentials Grant. O token tem TTL típico
de 3600 segundos. Cacheamos no Redis com TTL = token_ttl - margem, evitando
chamadas repetidas a /oauth2/token a cada request.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import redis.asyncio as redis_async
import structlog

from app.config import Settings
from app.shared.exceptions import SerproOAuthErro, SerproTimeout
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)

_TOKEN_REDIS_KEY = "serpro:oauth2:access_token"  # nosec B105 — chave Redis, não credencial
_TOKEN_PATH = "/oauth2/token"  # nosec B105 — caminho de URL, não credencial


class SerproOAuthClient:
    """Obtém + cacheia o access_token OAuth2 do SERPRO via Client Credentials."""

    def __init__(
        self,
        settings: Settings,
        redis: redis_async.Redis[str] | None,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._consumer_key = settings.SERPRO_CONSUMER_KEY
        self._consumer_secret = settings.SERPRO_CONSUMER_SECRET
        self._base_url = settings.SERPRO_BASE_URL.rstrip("/")
        self._ttl_margin_sec = settings.SERPRO_OAUTH_TTL_MARGIN_SEC
        self._redis = redis
        self._http = http or httpx.AsyncClient(timeout=20.0)
        self._owns_http = http is None
        # Lock local — evita N requisições paralelas refazendo OAuth quando o
        # cache expira sob carga (thundering herd).
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def access_token(self) -> str:
        """Retorna access_token válido. Usa cache Redis; renova se faltar."""
        cached = await self._buscar_cache()
        if cached:
            return cached

        async with self._lock:
            # Re-check após adquirir lock — outra task pode ter renovado.
            cached = await self._buscar_cache()
            if cached:
                return cached
            token, ttl = await self._solicitar_novo_token()
            await self._salvar_cache(token, ttl)
            return token

    async def invalidar(self) -> None:
        """Força próxima chamada a obter token novo (uso em retry 401)."""
        if self._redis is None:
            return
        try:
            await self._redis.delete(_TOKEN_REDIS_KEY)
        except Exception:  # pragma: no cover
            log.warning("serpro.oauth.cache_delete_falhou")

    async def _buscar_cache(self) -> str | None:
        if self._redis is None:
            return None
        try:
            value = await self._redis.get(_TOKEN_REDIS_KEY)
            return value if value else None
        except Exception:  # pragma: no cover
            log.warning("serpro.oauth.cache_read_falhou")
            return None

    async def _salvar_cache(self, token: str, ttl_seconds: int) -> None:
        if self._redis is None:
            return
        ttl = max(ttl_seconds - self._ttl_margin_sec, 30)
        try:
            await self._redis.setex(_TOKEN_REDIS_KEY, ttl, token)
        except Exception:  # pragma: no cover
            log.warning("serpro.oauth.cache_write_falhou")

    async def _solicitar_novo_token(self) -> tuple[str, int]:
        if not self._consumer_key or not self._consumer_secret:
            raise SerproOAuthErro(
                "Credenciais SERPRO ausentes — defina SERPRO_CONSUMER_KEY/SECRET."
            )

        url = f"{self._base_url}{_TOKEN_PATH}"
        inicio = time.monotonic()
        try:
            resp = await self._http.post(
                url,
                data={"grant_type": "client_credentials"},
                auth=(self._consumer_key, self._consumer_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.TransportError as exc:
            raise SerproTimeout(f"Falha ao falar com SERPRO OAuth: {exc}") from exc

        latencia_ms = int((time.monotonic() - inicio) * 1000)

        if resp.status_code != 200:
            log.warning(
                "serpro.oauth.token_falhou",
                status_http=resp.status_code,
                corpo=resp.text[:200],
                latencia_ms=latencia_ms,
            )
            raise SerproOAuthErro(
                f"SERPRO OAuth retornou {resp.status_code}: {resp.text[:300]}"
            )

        body: JsonObject = resp.json()
        token = str(body.get("access_token", ""))
        ttl = int(body.get("expires_in", 3600))
        if not token:
            raise SerproOAuthErro("SERPRO OAuth respondeu sem access_token")

        log.info("serpro.oauth.token_emitido", ttl_seg=ttl, latencia_ms=latencia_ms)
        return token, ttl
