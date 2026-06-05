from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

import httpx
import redis.asyncio as aioredis
import structlog
from pydantic import BaseModel, ConfigDict

from app.config import Settings
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)

# Regex para capturar IDs citados pelo LLM na forma [ID]
# Exemplo: "O DAS foi R$ 1.234,56 [ap-2026-05-001]." → ["ap-2026-05-001"]
_RE_CITACAO = re.compile(r"\[([^\]]+)\]")


def _extrair_citacoes(texto: str, fontes: list["FonteFato"]) -> list["Citacao"]:
    """Parseia referências ``[ID]`` do texto e valida contra as fontes fornecidas.

    Princípio §8.5: só gera Citacao para IDs que o modelo *realmente* usou
    (apareceram no texto) E que existem entre as ``fontes_disponiveis`` passadas
    no request. IDs inventados pelo modelo (não presentes nas fontes) são
    silenciosamente descartados — o re-check de §8.6 cuidará da rejeição.

    O ``trecho_citado`` é o início do payload da fonte (máx. 120 chars) que
    serve de âncora de rastreabilidade para auditoria. Não é o trecho literal
    extraído do texto do LLM, pois o modelo pode parafrasear; o ID já garante
    a ligação ao fato.
    """
    if not fontes:
        return []

    ids_validos: dict[str, "FonteFato"] = {f.id: f for f in fontes}
    vistos: set[str] = set()
    citacoes: list[Citacao] = []

    for m in _RE_CITACAO.finditer(texto):
        id_referenciado = m.group(1).strip()
        if id_referenciado in vistos:
            continue  # deduplica múltiplas menções ao mesmo ID
        vistos.add(id_referenciado)
        fonte = ids_validos.get(id_referenciado)
        if fonte is None:
            # ID não existe nas fontes fornecidas → descartar (não inventar)
            log.debug(
                "llm.citacao_id_invalido",
                id_referenciado=id_referenciado,
            )
            continue
        trecho = fonte.payload[:120]
        citacoes.append(Citacao(fato_id=id_referenciado, trecho_citado=trecho))

    return citacoes


# Custo por token (USD) para providers Gemini — atualizar conforme pricing
_CUSTO_POR_TOKEN: dict[str, tuple[Decimal, Decimal]] = {
    "gemini-2.5-flash-lite": (Decimal("1E-7"), Decimal("4E-7")),   # $0.10 / $0.40 por M
    "gemini-2.5-flash": (Decimal("3E-7"), Decimal("2.5E-6")),      # $0.30 / $2.50 por M
    "gemini-2.5-pro": (Decimal("1.25E-6"), Decimal("1E-5")),       # $1.25 / $10.00 por M
}

# Mapeamento provider → model ID da API do Google AI
# Verificar nomes exatos em ai.google.dev/models antes de ir a produção
_PROVIDER_PARA_MODELO: dict[str, str] = {
    "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.5-pro": "gemini-2.5-pro",
}


class LLMProvider(StrEnum):
    OLLAMA_GEMMA_3_4B = "ollama-gemma3-4b"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_PRO = "gemini-2.5-pro"


class FonteFato(BaseModel):
    """Fato verificável que o LLM pode citar na resposta."""

    model_config = ConfigDict(frozen=True)

    id: str
    tipo: str  # "apuracao_das", "documento_fiscal", "nota_fiscal", etc.
    payload: str  # conteúdo que deve aparecer literalmente se citado
    data: str | None = None


class Citacao(BaseModel):
    """Referência que o LLM faz a um fato verificável."""

    model_config = ConfigDict(frozen=True)

    fato_id: str
    trecho_citado: str


class LLMResponse(BaseModel):
    """Resposta normalizada do LLM, independente de provider."""

    model_config = ConfigDict(frozen=True)

    texto: str
    citacoes: list[Citacao]
    tokens_input: int
    tokens_output: int
    tokens_cached: int
    custo_usd: Decimal
    provider: LLMProvider
    latencia_ms: int
    encaminhar_marketplace: bool = False
    categoria_marketplace: str | None = None


@dataclass
class LLMRequest:
    """Parâmetros de uma chamada LLM.

    Usa dataclass (não BaseModel) para suportar type[BaseModel] em response_schema
    sem que o Pydantic tente serializar/validar o tipo Python.
    """

    prompt: str
    system: str | None = None
    response_schema: type[BaseModel] | None = None  # para structured output via JSON mode
    cache_key: str | None = None
    cache_ttl_seconds: int = 3600  # 1h default; system prompts usam 604800 (7d)
    temperature: float = 0.0
    fontes_disponiveis: list[FonteFato] = field(default_factory=list)
    contem_pii: bool = False  # True → força roteamento para Ollama local


class LLMClient:
    """
    Cliente LLM unificado: Ollama (local, privacy-first) + Gemini (cloud).

    Política de roteamento:
    - contem_pii=True → OLLAMA_GEMMA_3_4B (dados sensíveis nunca saem da máquina)
    - padrão → GEMINI_2_5_FLASH_LITE (custo baixo para perguntas simples)
    - caller pode forçar provider passando explicitamente

    Cache Redis por cache_key (TTL configurável por request).
    Trace opcional via Langfuse (desativado se LANGFUSE_HOST não configurado).
    """

    def __init__(
        self,
        settings: Settings,
        redis: aioredis.Redis[str],
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._redis = redis
        self._http = http_client or httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        # Lazy init — `genai.Client` é importado dentro de `_chamar_gemini` para
        # não exigir google-genai em ambientes que só usam Ollama.
        self._gemini: Any = None  # noqa: ANN401

    async def chamar(
        self,
        request: LLMRequest,
        provider: LLMProvider | None = None,
    ) -> LLMResponse:
        """Despacha para o provider correto, gerencia cache e grava trace."""
        if provider is None:
            provider = self._rotear(request)

        if request.cache_key:
            cached = await self._get_cache(request.cache_key, provider)
            if cached is not None:
                log.debug("llm.cache_hit", cache_key=request.cache_key, provider=provider.value)
                return cached

        t0 = time.monotonic()
        if provider == LLMProvider.OLLAMA_GEMMA_3_4B:
            resp = await self._chamar_ollama(request)
        else:
            resp = await self._chamar_gemini(request, provider)

        latencia_ms = int((time.monotonic() - t0) * 1000)
        resp = resp.model_copy(update={"latencia_ms": latencia_ms})

        if request.cache_key:
            await self._set_cache(request.cache_key, provider, resp, request.cache_ttl_seconds)

        await self._registrar_langfuse(request, resp)
        log.info(
            "llm.chamou",
            provider=provider.value,
            tokens_input=resp.tokens_input,
            tokens_output=resp.tokens_output,
            tokens_cached=resp.tokens_cached,
            custo_usd=str(resp.custo_usd),
            latencia_ms=latencia_ms,
        )
        return resp

    def _rotear(self, request: LLMRequest) -> LLMProvider:
        if request.contem_pii:
            return LLMProvider.OLLAMA_GEMMA_3_4B
        return LLMProvider.GEMINI_2_5_FLASH_LITE

    async def _get_cache(self, cache_key: str, provider: LLMProvider) -> LLMResponse | None:
        key = f"llm:cache:{provider.value}:{cache_key}"
        raw = await self._redis.get(key)
        if raw is None:
            return None
        try:
            return LLMResponse.model_validate_json(raw)
        except Exception:
            return None

    async def _set_cache(
        self,
        cache_key: str,
        provider: LLMProvider,
        resp: LLMResponse,
        ttl: int,
    ) -> None:
        key = f"llm:cache:{provider.value}:{cache_key}"
        await self._redis.setex(key, ttl, resp.model_dump_json())

    async def _chamar_ollama(self, request: LLMRequest) -> LLMResponse:
        from app.shared.exceptions import LLMIndisponivel

        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})

        payload: JsonObject = {
            "model": "gemma3:4b",
            "messages": messages,
            "stream": False,
            "options": {"temperature": request.temperature},
        }
        if request.response_schema is not None:
            payload["format"] = "json"

        try:
            r = await self._http.post(
                f"{self._settings.OLLAMA_URL}/api/chat",
                json=payload,
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMIndisponivel(f"Ollama indisponível: {e}") from e

        data: JsonObject = r.json()
        texto = str(data.get("message", {}).get("content", ""))
        tokens_input = int(data.get("prompt_eval_count", 0))
        tokens_output = int(data.get("eval_count", 0))

        citacoes = _extrair_citacoes(texto, request.fontes_disponiveis)

        return LLMResponse(
            texto=texto,
            citacoes=citacoes,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tokens_cached=0,
            custo_usd=Decimal("0"),
            provider=LLMProvider.OLLAMA_GEMMA_3_4B,
            latencia_ms=0,
        )

    async def _chamar_gemini(self, request: LLMRequest, provider: LLMProvider) -> LLMResponse:
        from app.shared.exceptions import LLMIndisponivel, LLMRespostaInvalida

        api_key = getattr(self._settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise LLMIndisponivel("GEMINI_API_KEY não configurada")

        try:
            from google import genai
            from google.genai import types as gtypes
        except ImportError as e:
            raise LLMIndisponivel("google-genai não instalado: poetry add google-genai") from e

        if self._gemini is None:
            self._gemini = genai.Client(api_key=api_key)

        model_name = _PROVIDER_PARA_MODELO[provider.value]
        cfg_kwargs: JsonObject = {"temperature": request.temperature}
        if request.system:
            cfg_kwargs["system_instruction"] = request.system
        if request.response_schema is not None:
            cfg_kwargs["response_mime_type"] = "application/json"
            cfg_kwargs["response_schema"] = request.response_schema

        try:
            response = await self._gemini.aio.models.generate_content(
                model=model_name,
                contents=request.prompt,
                config=gtypes.GenerateContentConfig(**cfg_kwargs),
            )
        except Exception as e:
            raise LLMRespostaInvalida(f"Gemini retornou erro: {e}") from e

        usage = response.usage_metadata
        tokens_input = int(getattr(usage, "prompt_token_count", 0) or 0)
        tokens_output = int(getattr(usage, "candidates_token_count", 0) or 0)
        tokens_cached = int(getattr(usage, "cached_content_token_count", 0) or 0)

        custo_input, custo_output = _CUSTO_POR_TOKEN[provider.value]
        custo_usd = (
            Decimal(tokens_input) * custo_input + Decimal(tokens_output) * custo_output
        )

        texto_gemini = response.text or ""
        citacoes = _extrair_citacoes(texto_gemini, request.fontes_disponiveis)

        return LLMResponse(
            texto=texto_gemini,
            citacoes=citacoes,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tokens_cached=tokens_cached,
            custo_usd=custo_usd,
            provider=provider,
            latencia_ms=0,
        )

    async def _registrar_langfuse(self, request: LLMRequest, resp: LLMResponse) -> None:
        host = getattr(self._settings, "LANGFUSE_HOST", None)
        if not host:
            return
        try:
            from langfuse import Langfuse

            lf = Langfuse(
                host=host,
                public_key=getattr(self._settings, "LANGFUSE_PUBLIC_KEY", ""),
                secret_key=getattr(self._settings, "LANGFUSE_SECRET_KEY", ""),
            )
            # API v2/v3 do Langfuse divergiu (v3 usa start_observation).
            # Migração planejada — por ora, o try/except externo cobre AttributeError.
            trace = lf.trace(name="llm.chamar")  # type: ignore[attr-defined]
            trace.generation(
                name=resp.provider.value,
                model=resp.provider.value,
                input=request.prompt[:200],  # não logar payload completo
                output=resp.texto[:500],
                usage={"input": resp.tokens_input, "output": resp.tokens_output},
            )
            lf.flush()
        except Exception as e:
            log.warning("langfuse.erro_trace", erro=str(e))

    async def aclose(self) -> None:
        await self._http.aclose()
