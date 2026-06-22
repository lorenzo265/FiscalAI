"""Security headers por response (Marco 3 LGPD/seguranca, 2026-06-22).

Adiciona os headers de seguranca padrao a TODA resposta da API, espelhando o
``CorrelationIdMiddleware``. Defesa em profundidade contra clickjacking,
MIME-sniffing, vazamento de referrer e XSS, com um CSP conservador (a API serve
JSON, nao HTML executavel).

Headers aplicados (via ``setdefault`` -- nunca sobrescreve um header que a rota
ja tenha definido de proposito):

  * ``X-Content-Type-Options: nosniff`` -- impede MIME-sniffing.
  * ``X-Frame-Options: DENY`` -- anti-clickjacking (a API nunca e enquadrada).
  * ``Referrer-Policy: strict-origin-when-cross-origin`` -- limita vazamento de URL.
  * ``X-XSS-Protection: 0`` -- desliga o auditor XSS legado dos browsers
    (recomendacao OWASP atual; o filtro legado introduz vulnerabilidades. A
    defesa real e o CSP abaixo).
  * ``Permissions-Policy`` -- nega features poderosas que a API nao usa.
  * ``Content-Security-Policy: default-src 'none'; ...`` -- API-only. EXCETO os
    paths de documentacao (``/docs``, ``/redoc``, ``/openapi.json``), que servem
    o Swagger UI / ReDoc (HTML + assets de CDN) e quebrariam sob ``default-src
    'none'`` -- esses ficam isentos do CSP (mantem todos os demais headers).
  * ``Strict-Transport-Security`` -- forca HTTPS por 2 anos. So quando
    ``hsts_enabled`` (staging/prod, com TLS no edge); NUNCA em local/dev (http),
    onde brickaria o acesso e o browser memorizaria o pin por 2 anos.

A decisao de HSTS e injetada pelo ``app/main.py`` (que conhece o ENVIRONMENT) --
o middleware fica agnostico de config. Registrado em ``app/main.py``; ver la a
ordem dos middlewares (este precisa rodar OUTERMOST o suficiente para que os
headers caiam tambem nas respostas 429 do rate-limit e nos erros).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# Paths que servem HTML + assets de CDN (Swagger UI, ReDoc, schema OpenAPI):
# isentos do CSP estrito (default-src 'none' bloquearia o carregamento deles).
_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})

# CSP conservador para uma API que so devolve JSON: nada de script, estilo,
# imagem, frame ou conexao -- e nao pode ser enquadrada nem ter <base> trocada.
_CSP_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"

_PERMISSIONS_POLICY = "geolocation=(), microphone=(), camera=()"

# 2 anos, subdominios incluidos, elegivel a lista de preload dos browsers.
_HSTS = "max-age=63072000; includeSubDomains; preload"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injeta os headers de seguranca padrao em toda resposta da API."""

    def __init__(self, app: ASGIApp, *, hsts_enabled: bool = False) -> None:
        super().__init__(app)
        self._hsts_enabled = hsts_enabled

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        headers = response.headers

        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("X-XSS-Protection", "0")
        headers.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)

        # CSP estrito so onde nao servimos a UI de documentacao (HTML + CDN).
        if request.url.path not in _DOCS_PATHS:
            headers.setdefault("Content-Security-Policy", _CSP_API)

        # HSTS so com TLS garantido no edge (staging/prod). Em http brickaria.
        if self._hsts_enabled:
            headers.setdefault("Strict-Transport-Security", _HSTS)

        return response
