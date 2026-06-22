"""Golden — CorrelationIdMiddleware (Marco 1 produção).

Verifica que todo request recebe um ``X-Request-ID`` (gerado se ausente,
ecoado se fornecido). App Starlette mínimo + TestClient — isolado, sem DB.
"""
from __future__ import annotations

import uuid

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.shared.middleware.correlation_id import CorrelationIdMiddleware


def _build_app() -> Starlette:
    async def _ok(_request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/ping", _ok)])
    app.add_middleware(CorrelationIdMiddleware)
    return app


def test_gera_request_id_uuid_quando_ausente() -> None:
    resp = TestClient(_build_app()).get("/ping")
    assert resp.status_code == 200
    rid = resp.headers.get("X-Request-ID")
    assert rid is not None
    uuid.UUID(rid)  # levanta se não for um UUID válido


def test_ecoa_request_id_fornecido_pelo_cliente() -> None:
    fornecido = "req-abc-123"
    resp = TestClient(_build_app()).get("/ping", headers={"X-Request-ID": fornecido})
    assert resp.headers.get("X-Request-ID") == fornecido
