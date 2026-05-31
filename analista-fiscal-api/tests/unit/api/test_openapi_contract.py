"""Golden tests — contrato OpenAPI público (Sprint 22 PR2).

§8.4: testa que o schema OpenAPI gerado pelo FastAPI satisfaz os requisitos
de documentação pública: versão, contato, tags, descrição de autenticação
e que os endpoints críticos estão registrados.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

_client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def openapi_schema() -> dict:  # type: ignore[type-arg]
    resp = _client.get("/openapi.json")
    assert resp.status_code == 200
    return resp.json()  # type: ignore[no-any-return]


# ── Metadados básicos ─────────────────────────────────────────────────────────


def test_openapi_versao_1_0_0(openapi_schema: dict) -> None:  # type: ignore[type-arg]
    assert openapi_schema["info"]["version"] == "1.0.0"


def test_openapi_titulo_presente(openapi_schema: dict) -> None:  # type: ignore[type-arg]
    assert "Analista Fiscal" in openapi_schema["info"]["title"]


def test_openapi_descricao_menciona_autenticacao(openapi_schema: dict) -> None:  # type: ignore[type-arg]
    desc = openapi_schema["info"]["description"]
    assert "Bearer" in desc or "JWT" in desc or "Autenticação" in desc


def test_openapi_descricao_menciona_rate_limiting(openapi_schema: dict) -> None:  # type: ignore[type-arg]
    desc = openapi_schema["info"]["description"]
    assert "Rate Limiting" in desc or "rate" in desc.lower()


def test_openapi_contato_email_presente(openapi_schema: dict) -> None:  # type: ignore[type-arg]
    contact = openapi_schema["info"].get("contact", {})
    assert "email" in contact
    assert "@" in contact["email"]


# ── Tags documentadas ─────────────────────────────────────────────────────────


def test_openapi_tags_incluem_dominios_criticos(openapi_schema: dict) -> None:  # type: ignore[type-arg]
    tag_names = {t["name"] for t in openapi_schema.get("tags", [])}
    dominios_criticos = {"auth", "fiscal", "lucro_presumido", "contabil", "pessoal", "health"}
    assert dominios_criticos.issubset(tag_names), (
        f"Tags faltando: {dominios_criticos - tag_names}"
    )


def test_openapi_tag_health_presente(openapi_schema: dict) -> None:  # type: ignore[type-arg]
    tag_names = {t["name"] for t in openapi_schema.get("tags", [])}
    assert "health" in tag_names


# ── Endpoints críticos presentes ──────────────────────────────────────────────


@pytest.mark.parametrize("path_substr", [
    "/healthz",
    "/readyz",
    "/auth",
    "/empresas",
])
def test_endpoint_critico_no_schema(openapi_schema: dict, path_substr: str) -> None:  # type: ignore[type-arg]
    paths = openapi_schema.get("paths", {})
    assert any(path_substr in p for p in paths), (
        f"Path '{path_substr}' não encontrado no OpenAPI schema"
    )


# ── Healthcheck funcional ─────────────────────────────────────────────────────


def test_healthz_retorna_200() -> None:
    resp = _client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_openapi_json_retorna_200() -> None:
    resp = _client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
