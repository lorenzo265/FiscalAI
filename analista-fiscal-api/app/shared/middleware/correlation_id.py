"""Correlation-ID por request — Marco 1 produção (2026-06-21).

Liga um identificador de correlação a CADA request e o injeta nos
contextvars do structlog. Como o pipeline de log já tem
``structlog.contextvars.merge_contextvars`` (ver ``app/shared/logging.py``),
todo ``log.*`` emitido durante o request passa a carregar ``request_id``
automaticamente — correlação ponta-a-ponta em ambiente multi-tenant, sem
precisar passar o id manualmente em cada chamada de log.

Comportamento:
  * Lê o header ``X-Request-ID`` do cliente/proxy; se ausente, gera um UUID4.
  * Bind de ``request_id`` + ``metodo`` + ``rota`` nos contextvars no início.
  * Ecoa ``X-Request-ID`` no header da resposta (cliente/observabilidade).
  * Limpa os contextvars ao final (evita vazamento entre requests no worker).

Registrado em ``app/main.py`` via ``app.add_middleware(CorrelationIdMiddleware)``.
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_HEADER = "X-Request-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Gera/propaga o ``X-Request-ID`` e o injeta nos logs do request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        fornecido = request.headers.get(_HEADER)
        request_id = fornecido if fornecido else str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            metodo=request.method,
            rota=request.url.path,
        )
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        response.headers[_HEADER] = request_id
        return response
