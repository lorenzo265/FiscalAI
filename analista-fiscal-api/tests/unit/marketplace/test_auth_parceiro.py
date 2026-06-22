"""Testes de auth do parceiro — JWT + service login (Sprint 13 PR3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.marketplace.schemas import LoginParceiroIn
from app.modules.marketplace.service import ContadorParceiroService
from app.shared.auth.jwt import (
    ParceiroContext,
    TenantContext,
    criar_token,
    criar_token_parceiro,
    verificar_token,
    verificar_token_parceiro,
)
from app.shared.auth.password import hash_senha
from app.shared.exceptions import (
    CredenciaisParceiroInvalidas,
    ParceiroSemSenhaDefinida,
    TokenInvalido,
)


def _parceiro(
    *,
    ativo: bool = True,
    senha: str | None = "minhasenha123",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        nome="Joana",
        email="joana@x.com",
        telefone="11999990001",
        cpf=None,
        cnpj=None,
        crc_numero="123",
        crc_uf="SP",
        crc_status="ativo",
        crc_status_atualizado_em=None,
        especialidades=["tributario"],
        uf_atuacao=None,
        rating_medio=None,
        total_consultas=0,
        taxa_resposta_horas=None,
        sla_resposta_horas=24,
        oab_numero=None,
        oab_uf=None,
        senha_hash=hash_senha(senha) if senha else None,
        aceitou_nda_lgpd_em=None,
        ativo=ativo,
        created_at=datetime(2026, 5, 21, 10, 0, 0),
    )


# ── JWT helpers ─────────────────────────────────────────────────────────────


def test_criar_e_verificar_token_parceiro_roundtrip() -> None:
    cid = uuid.uuid4()
    token, expires_in = criar_token_parceiro(ParceiroContext(contador_id=cid))
    assert expires_in > 0

    ctx = verificar_token_parceiro(token)
    assert ctx.contador_id == cid


def test_verificar_token_parceiro_rejeita_token_tenant() -> None:
    """Token do cliente PME não pode autenticar como parceiro."""
    tenant_token, _ = criar_token(
        TenantContext(tenant_id=uuid.uuid4(), usuario_id=uuid.uuid4())
    )
    with pytest.raises(TokenInvalido, match="typ"):
        verificar_token_parceiro(tenant_token)


def test_verificar_token_cliente_rejeita_token_parceiro() -> None:
    """Caminho recíproco — token de parceiro não vale em endpoint de cliente."""
    parc_token, _ = criar_token_parceiro(ParceiroContext(contador_id=uuid.uuid4()))
    with pytest.raises(TokenInvalido, match="parceiro"):
        verificar_token(parc_token)


def test_verificar_token_parceiro_lixo_levanta() -> None:
    with pytest.raises(TokenInvalido):
        verificar_token_parceiro("nao-eh-jwt")


# ── ContadorParceiroService.login ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_sucesso_devolve_jwt_parceiro() -> None:
    session = AsyncMock()
    parceiro = _parceiro()
    repo = AsyncMock()
    repo.por_email = AsyncMock(return_value=parceiro)
    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo",
        return_value=repo,
    ):
        token, exp, p = await ContadorParceiroService().login(
            session,
            LoginParceiroIn(email="joana@x.com", senha="minhasenha123"),
        )
    assert token  # não-vazio
    assert exp > 0
    assert p.id == parceiro.id
    # Token verifica como parceiro
    ctx = verificar_token_parceiro(token)
    assert ctx.contador_id == parceiro.id


@pytest.mark.asyncio
async def test_login_senha_errada_levanta() -> None:
    session = AsyncMock()
    parceiro = _parceiro(senha="senhacerta1")
    repo = AsyncMock()
    repo.por_email = AsyncMock(return_value=parceiro)
    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo",
        return_value=repo,
    ), pytest.raises(CredenciaisParceiroInvalidas):
        await ContadorParceiroService().login(
            session,
            LoginParceiroIn(email="joana@x.com", senha="errada123"),
        )


@pytest.mark.asyncio
async def test_login_parceiro_inativo_levanta() -> None:
    session = AsyncMock()
    parceiro = _parceiro(ativo=False)
    repo = AsyncMock()
    repo.por_email = AsyncMock(return_value=parceiro)
    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo",
        return_value=repo,
    ), pytest.raises(CredenciaisParceiroInvalidas, match="inativo"):
        await ContadorParceiroService().login(
            session,
            LoginParceiroIn(email="joana@x.com", senha="minhasenha123"),
        )


@pytest.mark.asyncio
async def test_login_parceiro_sem_senha_levanta() -> None:
    session = AsyncMock()
    parceiro = _parceiro(senha=None)
    repo = AsyncMock()
    repo.por_email = AsyncMock(return_value=parceiro)
    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo",
        return_value=repo,
    ), pytest.raises(ParceiroSemSenhaDefinida):
        await ContadorParceiroService().login(
            session,
            LoginParceiroIn(email="joana@x.com", senha="minhasenha123"),
        )


@pytest.mark.asyncio
async def test_login_email_inexistente_levanta() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_email = AsyncMock(return_value=None)
    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo",
        return_value=repo,
    ), pytest.raises(CredenciaisParceiroInvalidas):
        await ContadorParceiroService().login(
            session,
            LoginParceiroIn(email="ninguem@x.com", senha="senha12345"),
        )


# ── definir_senha ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_definir_senha_grava_hash_bcrypt() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    parceiro = _parceiro(senha=None)
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=parceiro)
    with patch(
        "app.modules.marketplace.service.ContadorParceiroRepo",
        return_value=repo,
    ):
        out = await ContadorParceiroService().definir_senha(
            session, parceiro.id, "novasenha9000"
        )
    assert out.senha_hash is not None
    assert out.senha_hash.startswith("$2b$") or out.senha_hash.startswith("$2a$")
