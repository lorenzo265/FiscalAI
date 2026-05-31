"""Rate limiting por tenant — Sprint 21 PR2.

Conforme §14.3 do Plano:
  * 1000 req/hora padrão por tenant.
  * 100 req/hora em endpoints sensíveis (auth, DARF, SPED, pgdas).

Implementação via Redis INCR + EXPIRE:
  * Chave: ``rl:<tenant_id>:<janela_unix_hora>``
  * INCR atômico: sem race condition entre check e increment.
  * EXPIRE setado apenas na primeira requisição da janela (nx=True guard).
  * Fail-open: se Redis estiver indisponível, passa a requisição (evita DoS auto-infligido).

Integração: ``RateLimitMiddleware`` é registrado no ``app/main.py`` via
``app.add_middleware(RateLimitMiddleware)``. Endpoints sensíveis são
identificados por prefixo de path (ver ``SENSITIVE_PREFIXES``).
"""
from __future__ import annotations

import time
from collections.abc import Callable, Awaitable
from dataclasses import dataclass, field

import redis.asyncio as redis_async
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = structlog.get_logger(__name__)

# ── Configuração de limites ────────────────────────────────────────────────────

_LIMITE_PADRAO = 1000      # req/hora — endpoints comuns
_LIMITE_SENSIVEL = 100     # req/hora — endpoints sensíveis (§14.3)
_JANELA_SEG = 3600         # 1 hora em segundos

# Prefixos que ativam o limite reduzido.
SENSITIVE_PREFIXES = (
    "/v1/auth",
    "/v1/pgdas",
    "/v1/sped",
    "/v1/notas",
    "/v1/e-cac",
    "/v1/certidoes",
    "/v1/declaracao",
)


# ── DTO de resultado (puro, testável) ─────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Resultado imutável de uma checagem de rate limit."""

    permitido: bool
    contagem_atual: int
    limite: int
    janela_reset_ts: int       # Unix timestamp em que a janela expira
    tenant_id: str = ""
    motivo_bloqueio: str = ""  # preenchido apenas quando permitido=False
    headers: dict[str, str] = field(default_factory=dict)


# ── Algoritmo puro (testável sem Redis) ──────────────────────────────────────


def calcular_janela_atual(agora_ts: float = 0.0) -> int:
    """Retorna o Unix timestamp do início da janela de 1 hora corrente.

    Ex.: às 14:37 → retorna timestamp de 14:00:00 do mesmo dia.
    """
    ts = int(agora_ts) if agora_ts else int(time.time())
    return ts - (ts % _JANELA_SEG)


def eh_endpoint_sensivel(path: str) -> bool:
    """Retorna True se o path pertence a um endpoint de limite reduzido."""
    return any(path.startswith(p) for p in SENSITIVE_PREFIXES)


def limite_para_path(path: str) -> int:
    """Retorna o limite de requisições por hora para o path dado."""
    return _LIMITE_SENSIVEL if eh_endpoint_sensivel(path) else _LIMITE_PADRAO


def construir_chave_redis(tenant_id: str, janela_ts: int) -> str:
    """Constrói a chave Redis para o sliding window counter."""
    return f"rl:{tenant_id}:{janela_ts}"


def montar_headers_rate_limit(
    result: RateLimitResult,
    *,
    limite: int,
    restante: int,
    reset_ts: int,
) -> dict[str, str]:
    """Headers padrão RFC 6585 / IETF draft-ietf-httpapi-ratelimit-headers."""
    headers = {
        "X-RateLimit-Limit": str(limite),
        "X-RateLimit-Remaining": str(max(0, restante)),
        "X-RateLimit-Reset": str(reset_ts),
    }
    if not result.permitido:
        headers["Retry-After"] = str(reset_ts - int(time.time()))
    return headers


# ── Implementação Redis (I/O) ──────────────────────────────────────────────────


async def checar_rate_limit(
    redis: redis_async.Redis[str],
    tenant_id: str,
    path: str,
    *,
    agora_ts: float = 0.0,
) -> RateLimitResult:
    """Incrementa o counter e retorna o resultado.

    Algoritmo INCR + EXPIRE (atomic per-key):
      1. INCR da chave  → retorna novo valor.
      2. Se valor == 1 (primeira req da janela) → EXPIRE _JANELA_SEG.
      3. Compara com limite → decide se bloqueia.
    """
    limite = limite_para_path(path)
    janela = calcular_janela_atual(agora_ts)
    chave = construir_chave_redis(tenant_id, janela)
    reset_ts = janela + _JANELA_SEG

    try:
        contagem = int(await redis.incr(chave))
        if contagem == 1:
            await redis.expire(chave, _JANELA_SEG)
    except redis_async.RedisError as exc:
        log.warning("rate_limit.redis_error", tenant_id=tenant_id, error=str(exc))
        return RateLimitResult(
            permitido=True,
            contagem_atual=0,
            limite=limite,
            janela_reset_ts=reset_ts,
            tenant_id=tenant_id,
        )

    permitido = contagem <= limite
    restante = max(0, limite - contagem)
    result = RateLimitResult(
        permitido=permitido,
        contagem_atual=contagem,
        limite=limite,
        janela_reset_ts=reset_ts,
        tenant_id=tenant_id,
        motivo_bloqueio="" if permitido else f"limite de {limite} req/h atingido",
    )
    headers = montar_headers_rate_limit(result, limite=limite, restante=restante, reset_ts=reset_ts)
    return RateLimitResult(
        permitido=result.permitido,
        contagem_atual=result.contagem_atual,
        limite=result.limite,
        janela_reset_ts=result.janela_reset_ts,
        tenant_id=result.tenant_id,
        motivo_bloqueio=result.motivo_bloqueio,
        headers=headers,
    )


# ── Middleware FastAPI/Starlette ───────────────────────────────────────────────


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware de rate limiting por tenant via JWT sub.

    Extrai o tenant_id do JWT no header ``Authorization``. Endpoints públicos
    (sem JWT) são ignorados — rate limiting não se aplica a /healthz, /readyz,
    /v1/auth/login, /v1/auth/register.

    Se Redis estiver indisponível, a requisição passa (fail-open).
    """

    _PUBLIC_PATHS = frozenset({"/healthz", "/readyz", "/openapi.json", "/docs", "/redoc"})
    _AUTH_PATHS = frozenset({"/v1/auth/login", "/v1/auth/register"})

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path

        # Endpoints completamente públicos — sem rate limiting
        if path in self._PUBLIC_PATHS or path in self._AUTH_PATHS:
            return await call_next(request)

        # Tenta extrair tenant_id do JWT (sem re-validar — só lê o sub/tid)
        tenant_id = _extrair_tenant_id_sem_validar(request)
        if not tenant_id:
            return await call_next(request)

        redis: redis_async.Redis[str] | None = getattr(request.app.state, "redis", None)
        if redis is None:
            return await call_next(request)

        result = await checar_rate_limit(redis, tenant_id, path)

        if not result.permitido:
            log.warning(
                "rate_limit.blocked",
                tenant_id=tenant_id,
                path=path,
                contagem=result.contagem_atual,
                limite=result.limite,
            )
            resp = JSONResponse(
                status_code=429,
                content={
                    "codigo": "rate_limit_excedido",
                    "mensagem": result.motivo_bloqueio,
                },
                headers=result.headers,
            )
            return resp

        response = await call_next(request)
        for k, v in result.headers.items():
            response.headers[k] = v
        return response


def _extrair_tenant_id_sem_validar(request: Request) -> str | None:
    """Extrai o claim 'tid' do JWT sem verificar assinatura.

    Usado APENAS para identificar o tenant para rate limiting.
    A validação real da assinatura acontece em ``get_tenant_context``.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        import base64, json
        payload_b64 = parts[1]
        # Adiciona padding se necessário
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        tid = payload.get("tid")
        return str(tid) if tid else None
    except Exception:
        return None
