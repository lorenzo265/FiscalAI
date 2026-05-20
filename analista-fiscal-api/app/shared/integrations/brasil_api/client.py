from __future__ import annotations

import json

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
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)

_CACHE_TTL_SEGUNDOS = 60 * 60 * 24 * 30  # 30 dias


class BrasilApiClient:
    """Cliente assíncrono para BrasilAPI — CNPJ lookup com cache Redis 30 dias."""

    def __init__(self, settings: Settings, redis: "redis_async.Redis[str]") -> None:
        self._base = settings.BRASIL_API_URL.rstrip("/")
        self._redis = redis
        self._http = httpx.AsyncClient(timeout=10.0)

    async def aclose(self) -> None:
        await self._http.aclose()

    @retry(
        wait=wait_exponential_jitter(initial=1, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def consultar_cnpj(self, cnpj: str) -> JsonObject:
        """Retorna dados cadastrais do CNPJ com cache Redis de 30 dias.

        Raises:
            CnpjNaoEncontrado: CNPJ inválido ou não consta na Receita Federal.
            BrasilApiIndisponivel: Falha de rede após 3 tentativas.
        """
        cache_key = f"brasilapi:cnpj:{cnpj}"
        cached = await self._redis.get(cache_key)
        if cached:
            dados: JsonObject = json.loads(cached)
            return dados

        url = f"{self._base}/api/cnpj/v1/{cnpj}"
        try:
            resp = await self._http.get(url)
        except httpx.TransportError as exc:
            from app.shared.exceptions import BrasilApiIndisponivel

            raise BrasilApiIndisponivel(f"BrasilAPI inacessível: {exc}") from exc

        if resp.status_code == 404:
            from app.shared.exceptions import CnpjNaoEncontrado

            raise CnpjNaoEncontrado(f"CNPJ {cnpj[:8]}**** não encontrado na Receita Federal")

        resp.raise_for_status()
        data: JsonObject = resp.json()
        await self._redis.setex(cache_key, _CACHE_TTL_SEGUNDOS, json.dumps(data))
        log.info("brasilapi.cnpj.consultado", cnpj_prefixo=cnpj[:8])
        return data
