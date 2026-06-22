"""Golden -- SecurityHeadersMiddleware (Marco 3 LGPD/seguranca).

Verifica que toda resposta recebe os headers de seguranca padrao; que o HSTS
so aparece quando habilitado (staging/prod); e que o CSP estrito e isento nos
paths de documentacao (Swagger UI / ReDoc). App Starlette minimo + TestClient --
isolado, sem DB.
"""
from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.shared.middleware.security_headers import (
    _CSP_API,
    _HSTS,
    _PERMISSIONS_POLICY,
    SecurityHeadersMiddleware,
)


def _build_app(*, hsts_enabled: bool = False) -> Starlette:
    async def _ok(_request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[
            Route("/ping", _ok),
            # Simula o path da UI de documentacao (isento do CSP estrito).
            Route("/docs", _ok),
        ]
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=hsts_enabled)
    return app


def test_headers_basicos_presentes() -> None:
    resp = TestClient(_build_app()).get("/ping")
    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert resp.headers["X-XSS-Protection"] == "0"
    assert resp.headers["Permissions-Policy"] == _PERMISSIONS_POLICY
    assert resp.headers["Content-Security-Policy"] == _CSP_API


def test_hsts_ausente_quando_desabilitado() -> None:
    # Default (local/dev): nunca emite HSTS sobre http.
    resp = TestClient(_build_app(hsts_enabled=False)).get("/ping")
    assert "Strict-Transport-Security" not in resp.headers


def test_hsts_presente_quando_habilitado() -> None:
    # staging/prod (TLS no edge): emite HSTS de 2 anos.
    resp = TestClient(_build_app(hsts_enabled=True)).get("/ping")
    assert resp.headers["Strict-Transport-Security"] == _HSTS


def test_csp_isento_nos_paths_de_docs() -> None:
    # /docs serve HTML + CDN do Swagger; CSP estrito quebraria os assets.
    resp = TestClient(_build_app()).get("/docs")
    assert "Content-Security-Policy" not in resp.headers
    # Os demais headers de seguranca continuam aplicados mesmo nos docs.
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
