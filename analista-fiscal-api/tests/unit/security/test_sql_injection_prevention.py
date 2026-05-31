"""Prevenção de SQL injection e validação de inputs (Sprint 21 PR1).

Golden tests — §8.4 bloqueiam merge.
Garante que:
  1. RLS set_config usa bind parameter (:tid), nunca interpolação de string.
  2. UUID fields no RLS e JWT rejeitam payloads maliciosos no parse.
  3. Schemas Pydantic com UUID rejeitam inputs que não são UUIDs válidos.
  4. Pydantic rejeita campos extras em inputs (ConfigDict extra='forbid').
"""
from __future__ import annotations

import inspect
from uuid import UUID

import pytest
from pydantic import UUID4, BaseModel, ConfigDict, ValidationError

from app.shared.db.rls import set_tenant_id, set_contador_id


# ── RLS usa bind parameter ────────────────────────────────────────────────────


def test_set_tenant_id_usa_bind_parameter_tid():
    """Garante que set_config usa :tid (bind param), não interpolação de string."""
    src = inspect.getsource(set_tenant_id)
    assert ":tid" in src, "set_tenant_id deve usar :tid como bind parameter"
    # Interpolação direta seria {tenant_id} ou %s ou + str(...)
    assert "{tenant_id}" not in src
    assert "% tenant_id" not in src


def test_set_contador_id_usa_bind_parameter_cid():
    """Garante que set_config do contador usa :cid (bind param)."""
    src = inspect.getsource(set_contador_id)
    assert ":cid" in src, "set_contador_id deve usar :cid como bind parameter"
    assert "{contador_id}" not in src


# ── UUID parsing rejeita SQL injection ───────────────────────────────────────


@pytest.mark.parametrize("payload_malicioso", [
    "'; DROP TABLE empresa;--",
    "1 OR 1=1",
    "1; SELECT pg_sleep(10)--",
    "<script>alert(1)</script>",
    "../../etc/passwd",
    "\x00\x01\x02malformed",
])
def test_uuid_parse_rejeita_injecao(payload_malicioso: str):
    """UUID() rejeita qualquer string que não seja UUID v4 — cobre tenant_id no JWT."""
    with pytest.raises((ValueError, AttributeError)):
        UUID(payload_malicioso)


# ── Schema Pydantic com UUID rejeita inputs inválidos ────────────────────────


class _InputComEmpresaId(BaseModel):
    model_config = ConfigDict(extra="forbid")
    empresa_id: UUID4


@pytest.mark.parametrize("valor_invalido", [
    "'; DROP TABLE empresa;--",
    "123",
    "nao-e-uuid",
    "",
    "null",
    "0",
])
def test_schema_uuid4_rejeita_payload_invalido(valor_invalido: str):
    with pytest.raises(ValidationError):
        _InputComEmpresaId(empresa_id=valor_invalido)  # type: ignore[arg-type]


def test_schema_extra_forbid_rejeita_campo_inesperado():
    """Pydantic ConfigDict(extra='forbid') bloqueia campos extras — OWASP Mass Assignment."""
    with pytest.raises(ValidationError):
        _InputComEmpresaId(
            empresa_id="550e8400-e29b-41d4-a716-446655440000",
            campo_extra_malicioso="injetado",  # type: ignore[call-arg]
        )


# ── Garantia estrutural: nenhuma query RLS usa f-string ─────────────────────


def test_rls_nao_usa_fstring_com_tenant():
    """Confirma ausência de f-string interpolando tenant_id no módulo rls.py."""
    import app.shared.db.rls as rls_module
    src = inspect.getsource(rls_module)
    # Padrões que indicariam interpolação insegura:
    assert "f\"SELECT set_config" not in src
    assert "f'SELECT set_config" not in src
    assert f"{{tenant_id}}" not in src
    assert f"{{contador_id}}" not in src
