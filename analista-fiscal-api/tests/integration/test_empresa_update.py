"""Testes de integração — PUT /v1/empresas/{id} (edição cadastral).

Requer Postgres real + `alembic upgrade head` (CI provisiona).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _slug() -> str:
    return f"t{uuid.uuid4().hex[:10]}"


async def _registrar(client: AsyncClient) -> str:
    slug = _slug()
    r = await client.post(
        "/auth/register",
        json={
            "tenant_nome": "Tenant PUT",
            "tenant_slug": slug,
            "usuario_nome": "Admin",
            "usuario_email": f"admin@{slug}.com",
            "usuario_senha": "S3nh@Forte!",
        },
    )
    assert r.status_code == 201, r.text
    token: str = r.json()["access_token"]
    return token


async def _criar_empresa(client: AsyncClient, token: str) -> str:
    r = await client.post(
        "/v1/empresas",
        json={
            "cnpj": "11222333000181",
            "razao_social": "Razão Original Ltda",
            "regime_tributario": "simples_nacional",
            "anexo_simples": "I",
            "municipio": "São Paulo",
            "codigo_municipio_ibge": "3550308",
            "uf": "SP",
            "faturamento_12m": "680000.00",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["perfil_ui"] == "sn_sem_funcionarios"
    empresa_id: str = data["id"]
    return empresa_id


async def test_put_atualiza_campos_e_persiste(live_client: AsyncClient) -> None:
    token = await _registrar(live_client)
    empresa_id = await _criar_empresa(live_client, token)
    h = {"Authorization": f"Bearer {token}"}

    r = await live_client.put(
        f"/v1/empresas/{empresa_id}",
        json={
            "razao_social": "Razão Atualizada Ltda",
            "nome_fantasia": "Fantasia Nova",
            "faturamento_12m": "1250000.00",
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["razao_social"] == "Razão Atualizada Ltda"
    assert data["nome_fantasia"] == "Fantasia Nova"
    assert data["faturamento_12m"] == "1250000.00"
    # campos não enviados ficam inalterados
    assert data["cnpj"] == "11222333000181"
    assert data["regime_tributario"] == "simples_nacional"
    assert data["anexo_simples"] == "I"

    # persistiu: GET reflete a edição
    g = await live_client.get(f"/v1/empresas/{empresa_id}", headers=h)
    assert g.status_code == 200
    assert g.json()["razao_social"] == "Razão Atualizada Ltda"


async def test_put_mudanca_de_regime_rederiva_perfil_ui(live_client: AsyncClient) -> None:
    token = await _registrar(live_client)
    empresa_id = await _criar_empresa(live_client, token)
    h = {"Authorization": f"Bearer {token}"}

    r = await live_client.put(
        f"/v1/empresas/{empresa_id}",
        json={"regime_tributario": "lucro_presumido"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["regime_tributario"] == "lucro_presumido"
    assert data["perfil_ui"] == "lucro_presumido"


async def test_put_rejeita_cnpj_extra_forbid(live_client: AsyncClient) -> None:
    token = await _registrar(live_client)
    empresa_id = await _criar_empresa(live_client, token)
    h = {"Authorization": f"Bearer {token}"}

    r = await live_client.put(
        f"/v1/empresas/{empresa_id}",
        json={"cnpj": "99888777000166"},
        headers=h,
    )
    assert r.status_code == 422, r.text


async def test_put_nao_limpa_ibge_not_null(live_client: AsyncClient) -> None:
    """Enviar codigo_municipio_ibge=null não deve estourar NOT NULL (0049) —
    o valor anterior é preservado."""
    token = await _registrar(live_client)
    empresa_id = await _criar_empresa(live_client, token)
    h = {"Authorization": f"Bearer {token}"}

    r = await live_client.put(
        f"/v1/empresas/{empresa_id}",
        json={"codigo_municipio_ibge": None, "nome_fantasia": "Só Fantasia"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["codigo_municipio_ibge"] == "3550308"  # preservado
    assert data["nome_fantasia"] == "Só Fantasia"


async def test_put_empresa_inexistente_retorna_404(live_client: AsyncClient) -> None:
    token = await _registrar(live_client)
    h = {"Authorization": f"Bearer {token}"}

    r = await live_client.put(
        f"/v1/empresas/{uuid.uuid4()}",
        json={"razao_social": "Qualquer Coisa Ltda"},
        headers=h,
    )
    assert r.status_code == 404, r.text
    assert r.json()["codigo"] == "EmpresaNaoEncontrada"
