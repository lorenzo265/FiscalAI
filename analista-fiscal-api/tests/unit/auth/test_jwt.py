"""Unit tests para criação e verificação de JWT."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.shared.auth.jwt import TenantContext, criar_token, verificar_token
from app.shared.exceptions import TokenInvalido


@pytest.fixture
def ctx() -> TenantContext:
    return TenantContext(tenant_id=uuid4(), usuario_id=uuid4())


def test_criar_e_verificar_token(ctx: TenantContext) -> None:
    token, expires_in = criar_token(ctx)
    resultado = verificar_token(token)
    assert resultado.tenant_id == ctx.tenant_id
    assert resultado.usuario_id == ctx.usuario_id


def test_expires_in_positivo(ctx: TenantContext) -> None:
    _, expires_in = criar_token(ctx)
    assert expires_in > 0


def test_token_invalido_levanta_excecao() -> None:
    with pytest.raises(TokenInvalido):
        verificar_token("token.invalido.mesmo")


def test_token_adulterado_levanta_excecao(ctx: TenantContext) -> None:
    token, _ = criar_token(ctx)
    adulterado = token[:-4] + "XXXX"
    with pytest.raises(TokenInvalido):
        verificar_token(adulterado)


def test_tenant_context_imutavel(ctx: TenantContext) -> None:
    with pytest.raises((AttributeError, TypeError)):
        ctx.tenant_id = uuid4()  # type: ignore[misc]
