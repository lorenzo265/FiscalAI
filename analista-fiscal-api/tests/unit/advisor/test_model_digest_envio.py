"""Sprint 15.5 PR1 — Smoke tests do model DigestSemanal + exceções de envio."""

from __future__ import annotations

import pytest

from app.shared.db.models import DigestSemanal
from app.shared.exceptions import (
    DigestJaEnviado,
    DomainError,
    EnvioWhatsappFalhou,
)


def test_digest_semanal_tem_colunas_de_auditoria_de_envio() -> None:
    """Migration 0038 adicionou 3 colunas + estendeu CHECK do status."""
    cols = {c.name for c in DigestSemanal.__table__.columns}
    assert "tentativas_envio" in cols
    assert "ultimo_erro_envio" in cols
    assert "enviado_template_name" in cols


def test_digest_status_check_inclui_falhou() -> None:
    """CHECK ck_digest_status deve aceitar 'falhou' (Sprint 15.5)."""
    checks = {
        c.name: c.sqltext.text
        for c in DigestSemanal.__table__.constraints
        if c.name and c.name.startswith("ck_digest_")
    }
    assert "falhou" in checks["ck_digest_status"]


def test_digest_check_tentativas_positivas_existe() -> None:
    nomes = {
        c.name for c in DigestSemanal.__table__.constraints if c.name
    }
    assert "ck_digest_tentativas_positivas" in nomes


def test_digest_ja_enviado_e_dominio_409() -> None:
    exc = DigestJaEnviado("já enviado")
    assert isinstance(exc, DomainError)
    assert exc.http_status == 409
    assert exc.codigo == "DigestJaEnviado"


def test_envio_whatsapp_falhou_e_dominio_502() -> None:
    exc = EnvioWhatsappFalhou("Meta retornou 500")
    assert isinstance(exc, DomainError)
    assert exc.http_status == 502
    assert exc.codigo == "EnvioWhatsappFalhou"
