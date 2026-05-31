"""Invariantes de segurança do JWT (Sprint 21 PR1).

Golden tests — §8.4 bloqueiam merge.
Cobrem: round-trip válido, expiração, assinatura adulterada, secret errado,
separação de tipos de token (PME × parceiro) e claims obrigatórios.
"""
from __future__ import annotations

import time
from unittest.mock import patch
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.config import Settings
from app.shared.auth.jwt import (
    ParceiroContext,
    TenantContext,
    criar_token,
    criar_token_parceiro,
    verificar_token,
    verificar_token_parceiro,
)
from app.shared.exceptions import TokenInvalido

_SETTINGS = Settings()
_MODULE = "app.shared.auth.jwt.get_settings"


@pytest.fixture(autouse=True)
def _patch_settings():
    with patch(_MODULE, return_value=_SETTINGS):
        yield


# ── Round-trip válido ─────────────────────────────────────────────────────────


def test_token_valido_round_trip_pme():
    ctx = TenantContext(tenant_id=uuid4(), usuario_id=uuid4())
    token, expires_in = criar_token(ctx)
    resultado = verificar_token(token)
    assert resultado == ctx
    assert expires_in > 0


def test_token_valido_round_trip_parceiro():
    ctx = ParceiroContext(contador_id=uuid4())
    token, expires_in = criar_token_parceiro(ctx)
    resultado = verificar_token_parceiro(token)
    assert resultado == ctx
    assert expires_in > 0


# ── Expiração ────────────────────────────────────────────────────────────────


def test_token_expirado_rejeita():
    payload: dict[str, str | int] = {
        "sub": str(uuid4()),
        "tid": str(uuid4()),
        "iat": 0,
        "exp": 1,  # expirado em 1970
    }
    token = pyjwt.encode(payload, _SETTINGS.JWT_SECRET, algorithm=_SETTINGS.JWT_ALGORITHM)
    with pytest.raises(TokenInvalido):
        verificar_token(token)


# ── Integridade da assinatura ────────────────────────────────────────────────


def test_assinatura_adulterada_rejeita():
    ctx = TenantContext(tenant_id=uuid4(), usuario_id=uuid4())
    token, _ = criar_token(ctx)
    # Corrompe os últimos 4 chars da assinatura
    adulterado = token[:-4] + ("XXXX" if not token.endswith("XXXX") else "YYYY")
    with pytest.raises(TokenInvalido):
        verificar_token(adulterado)


def test_secret_diferente_rejeita():
    payload: dict[str, str | int] = {
        "sub": str(uuid4()),
        "tid": str(uuid4()),
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    # ≥32 bytes para evitar InsecureKeyLengthWarning (RFC 7518 §3.2)
    token = pyjwt.encode(payload, "chave_totalmente_diferente_32bytes!!", algorithm="HS256")
    with pytest.raises(TokenInvalido):
        verificar_token(token)


# ── Separação de tipos (PME × parceiro) ─────────────────────────────────────


def test_token_parceiro_rejeitado_em_endpoint_pme():
    """Token com typ='parceiro' não deve ser aceito por verificar_token."""
    ctx_parceiro = ParceiroContext(contador_id=uuid4())
    token, _ = criar_token_parceiro(ctx_parceiro)
    with pytest.raises(TokenInvalido, match="parceiro"):
        verificar_token(token)


def test_token_pme_rejeitado_em_endpoint_parceiro():
    """Token PME (sem typ) não deve ser aceito por verificar_token_parceiro."""
    ctx_pme = TenantContext(tenant_id=uuid4(), usuario_id=uuid4())
    token, _ = criar_token(ctx_pme)
    with pytest.raises(TokenInvalido):
        verificar_token_parceiro(token)


# ── Claims obrigatórios ───────────────────────────────────────────────────────


def test_claim_tid_ausente_rejeita():
    payload: dict[str, str | int] = {
        "sub": str(uuid4()),
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    token = pyjwt.encode(payload, _SETTINGS.JWT_SECRET, algorithm=_SETTINGS.JWT_ALGORITHM)
    with pytest.raises(TokenInvalido):
        verificar_token(token)


def test_claim_sub_invalido_uuid_rejeita():
    """Sub que não é UUID válido deve ser rejeitado no parse."""
    payload: dict[str, str | int] = {
        "sub": "nao-e-um-uuid",
        "tid": str(uuid4()),
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    token = pyjwt.encode(payload, _SETTINGS.JWT_SECRET, algorithm=_SETTINGS.JWT_ALGORITHM)
    with pytest.raises(TokenInvalido):
        verificar_token(token)


def test_claim_tid_invalido_uuid_rejeita():
    """Tid que não é UUID válido deve ser rejeitado no parse."""
    payload: dict[str, str | int] = {
        "sub": str(uuid4()),
        "tid": "'; DROP TABLE empresa;--",  # tentativa de SQL injection via JWT
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    token = pyjwt.encode(payload, _SETTINGS.JWT_SECRET, algorithm=_SETTINGS.JWT_ALGORITHM)
    with pytest.raises(TokenInvalido):
        verificar_token(token)
