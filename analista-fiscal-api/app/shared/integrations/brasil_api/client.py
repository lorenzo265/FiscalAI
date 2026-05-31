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
_UF_VALIDA = frozenset(
    {
        "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
        "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
        "RO", "RR", "RS", "SC", "SE", "SP", "TO",
    }
)


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

    @retry(
        wait=wait_exponential_jitter(initial=1, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def listar_municipios_uf(self, uf: str) -> list[JsonObject]:
        """Retorna a lista de municípios de uma UF com código IBGE 7-dígitos.

        Endpoint: ``/api/ibge/municipios/v1/{uf}``. Cache Redis 30 dias.

        Returns:
            Lista de dicts ``{"nome": "São Paulo", "codigo_ibge": "3550308"}``.
            BrasilAPI por vezes devolve nomes em maiúsculas — quem consome
            deve normalizar.

        Raises:
            ValueError: UF inválida (não é uma das 27 UFs do Brasil).
            BrasilApiIndisponivel: falha de rede após 3 tentativas.
        """
        uf_norm = uf.strip().upper()
        if uf_norm not in _UF_VALIDA:
            raise ValueError(f"UF inválida: {uf!r}")

        cache_key = f"brasilapi:ibge:municipios:{uf_norm}"
        cached = await self._redis.get(cache_key)
        if cached:
            municipios_cached: list[JsonObject] = json.loads(cached)
            return municipios_cached

        url = f"{self._base}/api/ibge/municipios/v1/{uf_norm}"
        try:
            resp = await self._http.get(url)
        except httpx.TransportError as exc:
            from app.shared.exceptions import BrasilApiIndisponivel

            raise BrasilApiIndisponivel(
                f"BrasilAPI inacessível ao listar municípios {uf_norm}: {exc}"
            ) from exc

        resp.raise_for_status()
        municipios: list[JsonObject] = resp.json()
        await self._redis.setex(
            cache_key, _CACHE_TTL_SEGUNDOS, json.dumps(municipios)
        )
        log.info("brasilapi.municipios.consultado", uf=uf_norm, total=len(municipios))
        return municipios

    @retry(
        wait=wait_exponential_jitter(initial=1, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def listar_feriados_nacionais(self, ano: int) -> list[JsonObject]:
        """Lista feriados nacionais brasileiros para o ano (Lei 662/49 + 6.802/80).

        Endpoint: ``/api/feriados/v1/{ano}``. Cache Redis 30 dias (feriados
        nacionais são fixos por lei; mudanças extraordinárias raras).

        Returns:
            Lista de dicts ``{"date": "2026-01-01", "name": "Confraternização ..."}``.

        Raises:
            BrasilApiIndisponivel: falha de rede após 3 tentativas.
        """
        cache_key = f"brasilapi:feriados:{ano}"
        cached = await self._redis.get(cache_key)
        if cached:
            feriados_cached: list[JsonObject] = json.loads(cached)
            return feriados_cached

        url = f"{self._base}/api/feriados/v1/{ano}"
        try:
            resp = await self._http.get(url)
        except httpx.TransportError as exc:
            from app.shared.exceptions import BrasilApiIndisponivel

            raise BrasilApiIndisponivel(
                f"BrasilAPI inacessível ao listar feriados {ano}: {exc}"
            ) from exc

        resp.raise_for_status()
        feriados: list[JsonObject] = resp.json()
        await self._redis.setex(cache_key, _CACHE_TTL_SEGUNDOS, json.dumps(feriados))
        log.info("brasilapi.feriados.consultado", ano=ano, total=len(feriados))
        return feriados
