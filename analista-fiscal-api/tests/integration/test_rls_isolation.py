"""Testes de isolamento RLS — barreira de merge conforme §8.1 do Plano.

Verifica que tenant A não consegue ver dados de tenant B, mesmo fazendo
chamadas válidas autenticadas. O isolamento é garantido pelo Postgres RLS
via SET LOCAL app.tenant_id aplicado em cada sessão.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.shared.db.rls import set_tenant_id

pytestmark = pytest.mark.asyncio

CNPJ_EMPRESA_A = "12345678000195"
CNPJ_EMPRESA_B = "11222333000181"


def _slug() -> str:
    return f"t{uuid.uuid4().hex[:10]}"


async def _criar_tenant_e_empresa(
    client: AsyncClient,
    cnpj: str,
) -> tuple[str, str]:
    """Cria tenant + empresa. Retorna (token, empresa_id)."""
    slug = _slug()
    payload = {
        "tenant_nome": f"Tenant {slug}",
        "tenant_slug": slug,
        "usuario_nome": "Admin",
        "usuario_email": f"admin@{slug}.com",
        "usuario_senha": "S3nh@Forte!",
    }
    r = await client.post("/auth/register", json=payload)
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]

    r2 = await client.post(
        "/v1/empresas",
        json={
            "cnpj": cnpj,
            "razao_social": f"Empresa {cnpj}",
            "regime_tributario": "simples_nacional",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 201, r2.text
    empresa_id = r2.json()["id"]
    return token, empresa_id


async def test_listagem_retorna_apenas_empresas_do_proprio_tenant(
    live_client: AsyncClient,
) -> None:
    """GET /v1/empresas deve retornar apenas as empresas do tenant autenticado."""
    token_a, _ = await _criar_tenant_e_empresa(live_client, CNPJ_EMPRESA_A)
    token_b, _ = await _criar_tenant_e_empresa(live_client, CNPJ_EMPRESA_B)

    # Tenant A vê somente a empresa A
    r_a = await live_client.get("/v1/empresas", headers={"Authorization": f"Bearer {token_a}"})
    assert r_a.status_code == 200
    cnpjs_a = [e["cnpj"] for e in r_a.json()]
    assert CNPJ_EMPRESA_A in cnpjs_a
    assert CNPJ_EMPRESA_B not in cnpjs_a

    # Tenant B vê somente a empresa B
    r_b = await live_client.get("/v1/empresas", headers={"Authorization": f"Bearer {token_b}"})
    assert r_b.status_code == 200
    cnpjs_b = [e["cnpj"] for e in r_b.json()]
    assert CNPJ_EMPRESA_B in cnpjs_b
    assert CNPJ_EMPRESA_A not in cnpjs_b


async def test_busca_por_id_de_outro_tenant_retorna_404(
    live_client: AsyncClient,
) -> None:
    """GET /v1/empresas/{id} com ID de outro tenant deve retornar 404 (RLS oculta a linha)."""
    token_a, _ = await _criar_tenant_e_empresa(live_client, CNPJ_EMPRESA_A)
    token_b, empresa_id_b = await _criar_tenant_e_empresa(live_client, CNPJ_EMPRESA_B)

    # Tenant A tenta buscar empresa de Tenant B pelo ID
    resp = await live_client.get(
        f"/v1/empresas/{empresa_id_b}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    # RLS faz a linha sumir — serviço lança EmpresaNaoEncontrada → 404
    assert (
        resp.status_code == 404
    ), f"RLS falhou: tenant A conseguiu ver empresa de tenant B (id={empresa_id_b})"


async def test_cnpj_duplicado_dentro_do_mesmo_tenant_retorna_409(
    live_client: AsyncClient,
) -> None:
    """Mesmo CNPJ não pode ser cadastrado duas vezes no mesmo tenant."""
    token, _ = await _criar_tenant_e_empresa(live_client, CNPJ_EMPRESA_A)

    resp = await live_client.post(
        "/v1/empresas",
        json={"cnpj": CNPJ_EMPRESA_A, "razao_social": "Duplicada Ltda", "regime_tributario": "mei"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


async def test_mesmo_cnpj_pode_existir_em_tenants_diferentes(
    live_client: AsyncClient,
) -> None:
    """CNPJ pode ser cadastrado em tenants distintos (unicidade é por tenant_id)."""
    token_a, _ = await _criar_tenant_e_empresa(live_client, CNPJ_EMPRESA_A)
    token_b, _ = await _criar_tenant_e_empresa(live_client, CNPJ_EMPRESA_A)

    # Ambos cadastraram o mesmo CNPJ — constraint é (tenant_id, cnpj)
    r_a = await live_client.get("/v1/empresas", headers={"Authorization": f"Bearer {token_a}"})
    r_b = await live_client.get("/v1/empresas", headers={"Authorization": f"Bearer {token_b}"})
    assert len(r_a.json()) == 1
    assert len(r_b.json()) == 1
    assert r_a.json()[0]["cnpj"] == CNPJ_EMPRESA_A
    assert r_b.json()[0]["cnpj"] == CNPJ_EMPRESA_A


async def test_sem_token_retorna_401(live_client: AsyncClient) -> None:
    """Endpoint autenticado sem token deve retornar 401."""
    resp = await live_client.get("/v1/empresas")
    assert resp.status_code == 401


async def test_token_invalido_retorna_401(live_client: AsyncClient) -> None:
    """Token malformado deve retornar 401."""
    resp = await live_client.get(
        "/v1/empresas", headers={"Authorization": "Bearer token.invalido.mesmo"}
    )
    assert resp.status_code == 401


async def test_with_check_bloqueia_insert_cross_tenant(
    live_client: AsyncClient,
) -> None:
    """Policy WITH CHECK do RLS impede INSERT de linha com tenant_id de outro tenant.

    Garante o segundo lado da policy de isolamento — não basta filtrar SELECT,
    também precisa bloquear escrita cross-tenant mesmo que o atacante tente
    forjar tenant_id direto na sessão. §8.1 do Plano.
    """
    # Cria dois tenants reais via API para ter IDs válidos
    token_a, _ = await _criar_tenant_e_empresa(live_client, CNPJ_EMPRESA_A)
    token_b, _ = await _criar_tenant_e_empresa(live_client, CNPJ_EMPRESA_B)

    # Recupera os tenant_ids via JWT decode (ou seja, da própria API)
    r_a = await live_client.get("/v1/empresas", headers={"Authorization": f"Bearer {token_a}"})
    r_b = await live_client.get("/v1/empresas", headers={"Authorization": f"Bearer {token_b}"})
    tenant_id_a = uuid.UUID(r_a.json()[0]["tenant_id"])
    tenant_id_b = uuid.UUID(r_b.json()[0]["tenant_id"])

    # Acessa a session_factory exposta no app state pelo lifespan
    from app.main import app

    factory: async_sessionmaker = app.state.session_factory  # type: ignore[assignment]

    async with factory() as session:
        await session.execute(text("SET LOCAL ROLE fiscal_app"))
        # Contexto da sessão é o tenant A — tentar inserir empresa com tenant B
        # deve falhar pela policy WITH CHECK do Postgres
        await set_tenant_id(session, tenant_id_a)
        with pytest.raises((IntegrityError, ProgrammingError)):
            await session.execute(
                text(
                    "INSERT INTO empresa (tenant_id, cnpj, razao_social, regime_tributario, perfil_ui) "
                    "VALUES (:tid, :cnpj, :rs, 'simples_nacional', 'sn_sem_funcionarios')"
                ),
                {
                    "tid": str(tenant_id_b),
                    "cnpj": "99888777000166",
                    "rs": "Tentativa cross-tenant",
                },
            )
            await session.flush()
