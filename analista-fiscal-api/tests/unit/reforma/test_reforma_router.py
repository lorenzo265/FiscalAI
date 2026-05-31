"""Testes do router /v1/empresas/{eid}/reforma/* (Sprint 14 PR3).

Usa ``dependency_overrides`` para bypassar JWT + sessão real do DB.
Patcha ``ReformaService`` para devolver resultados controlados — foco no
contrato HTTP (validação Pydantic + serialização).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Generator
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.reforma.calcula_cbs_ibs import (
    OBSERVACAO_ESTIMATIVA,
    AliquotaCBSIBS,
)
from app.modules.reforma.periodo_transicao import FaseReforma
from app.modules.reforma.service import RecalculoResultado
from app.modules.reforma.simulador import (
    ALGORITMO_VERSAO as SIMULADOR_VERSAO,
    Cenario,
    CargaTributariaAnualizada,
    ImpactoFluxoCaixa,
    ResultadoSimulacao,
    SimulacaoCenario,
)
from app.shared.auth.jwt import TenantContext
from app.shared.db.deps import get_session, get_tenant_context


def _fake_tenant_ctx() -> TenantContext:
    return TenantContext(
        tenant_id=uuid.uuid4(),
        usuario_id=uuid.uuid4(),
        email="teste@fiscalai.local",
    )


async def _fake_session() -> AsyncIterator[None]:
    yield None  # type: ignore[misc]


@pytest.fixture
def _overrides() -> Generator[None, None, None]:
    """Overrides minimal — substitui JWT + sessão por stubs."""
    app.dependency_overrides[get_tenant_context] = _fake_tenant_ctx
    app.dependency_overrides[get_session] = _fake_session
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def _client(_overrides: None) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer fake"},
    ) as ac:
        yield ac


def _resultado_simulacao() -> ResultadoSimulacao:
    return ResultadoSimulacao(
        empresa_id=uuid.uuid4(),
        periodo_base=(date(2025, 5, 1), date(2026, 4, 30)),
        fase_atual=FaseReforma.TESTE_2026,
        receita_anualizada=Decimal("1000000.00"),
        carga_atual=CargaTributariaAnualizada(
            pis=Decimal("6500.00"),
            cofins=Decimal("30000.00"),
            icms=Decimal("120000.00"),
            iss=Decimal("0.00"),
        ),
        cenarios=[
            SimulacaoCenario(
                cenario=Cenario.PESSIMISTA,
                aliquota_total=Decimal("0.2850"),
                cbs_projetada=Decimal("94800.00"),
                ibs_projetada=Decimal("190200.00"),
                total_projetado=Decimal("285000.00"),
                delta_absoluto=Decimal("128500.00"),
                delta_percentual=Decimal("0.8211"),
            ),
            SimulacaoCenario(
                cenario=Cenario.REALISTA,
                aliquota_total=Decimal("0.2650"),
                cbs_projetada=Decimal("88000.00"),
                ibs_projetada=Decimal("177000.00"),
                total_projetado=Decimal("265000.00"),
                delta_absoluto=Decimal("108500.00"),
                delta_percentual=Decimal("0.6932"),
            ),
            SimulacaoCenario(
                cenario=Cenario.OTIMISTA,
                aliquota_total=Decimal("0.2450"),
                cbs_projetada=Decimal("81200.00"),
                ibs_projetada=Decimal("163800.00"),
                total_projetado=Decimal("245000.00"),
                delta_absoluto=Decimal("88500.00"),
                delta_percentual=Decimal("0.5654"),
            ),
        ],
        impacto_fluxo_caixa_2027=ImpactoFluxoCaixa(
            media_icms_mensal=Decimal("10000.00"),
            prazo_medio_recolhimento_dias=20,
            capital_giro_perdido=Decimal("6666.67"),
        ),
        observacao_estimativa=OBSERVACAO_ESTIMATIVA,
        fontes_norma=[
            "LC 214/2025 art. 156-A §1º",
            "EC 132/2023 art. 7º",
        ],
        algoritmo_versao=SIMULADOR_VERSAO,
    )


@pytest.mark.asyncio
async def test_get_simulacao_devolve_3_cenarios(_client: AsyncClient) -> None:
    empresa_id = uuid.uuid4()
    with patch(
        "app.modules.reforma.router.ReformaService"
    ) as mock_service_cls:
        mock_service = mock_service_cls.return_value
        mock_service.simular_impacto = pytest.importorskip("unittest.mock").AsyncMock(
            return_value=_resultado_simulacao()
        )
        resp = await _client.get(
            f"/v1/empresas/{empresa_id}/reforma/simulacao",
        )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["cenarios"]) == 3
    assert body["cenarios"][0]["cenario"] == "pessimista"
    assert body["cenarios"][1]["cenario"] == "realista"
    assert body["cenarios"][2]["cenario"] == "otimista"
    assert "LC 214/2025" in body["observacao_estimativa"]
    assert body["algoritmo_versao"] == SIMULADOR_VERSAO


@pytest.mark.asyncio
async def test_get_fase_atual_2026_retorna_teste(_client: AsyncClient) -> None:
    empresa_id = uuid.uuid4()
    resp = await _client.get(
        f"/v1/empresas/{empresa_id}/reforma/fase-atual",
        params={"competencia": "2026-06-15"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fase"] == "teste_2026"
    assert "LC 214/2025" in body["fonte_norma"]
    assert "LC 214/2025" in body["observacao_estimativa"]


@pytest.mark.asyncio
async def test_get_aliquota_vigente_serializa_corretamente(
    _client: AsyncClient,
) -> None:
    from unittest.mock import AsyncMock

    empresa_id = uuid.uuid4()
    aliquota = AliquotaCBSIBS(
        fase=FaseReforma.TESTE_2026,
        aliquota_cbs=Decimal("0.0090"),
        aliquota_ibs=Decimal("0.0010"),
        valid_from=date(2026, 1, 1),
        valid_to=None,
        fonte_norma="LC 214/2025 art. 348 §3º",
        algoritmo_versao="reforma.cbs-ibs.v1",
    )
    with patch("app.modules.reforma.router.ReformaService") as mock_cls:
        mock_cls.return_value.aliquota_vigente = AsyncMock(return_value=aliquota)
        resp = await _client.get(
            f"/v1/empresas/{empresa_id}/reforma/aliquota-vigente",
            params={"competencia": "2026-06-01"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fase"] == "teste_2026"
    assert body["aliquota_cbs"] == "0.0090"
    assert body["aliquota_ibs"] == "0.0010"
    assert "LC 214/2025" in body["observacao_estimativa"]


@pytest.mark.asyncio
async def test_post_recalcular_historico_devolve_contagem(
    _client: AsyncClient,
) -> None:
    from unittest.mock import AsyncMock

    empresa_id = uuid.uuid4()
    with patch("app.modules.reforma.router.ReformaService") as mock_cls:
        mock_cls.return_value.recalcular_historico_documentos = AsyncMock(
            return_value=RecalculoResultado(ano=2026, atualizados=7, ignorados=3)
        )
        # session.commit() é chamado dentro do handler — precisamos mockar
        # o yield do _fake_session com algo que tenha commit. Para esse caso,
        # criamos override específico no escopo do teste.

        # Override local de get_session que devolve sessão com commit AsyncMock
        async def _session_com_commit() -> AsyncIterator[object]:
            from types import SimpleNamespace

            yield SimpleNamespace(commit=AsyncMock())

        app.dependency_overrides[get_session] = _session_com_commit
        try:
            resp = await _client.post(
                f"/v1/empresas/{empresa_id}/reforma/recalcular-historico",
                json={"ano": 2026, "forcar": False},
            )
        finally:
            app.dependency_overrides[get_session] = _fake_session

    assert resp.status_code == 200
    body = resp.json()
    assert body["ano"] == 2026
    assert body["atualizados"] == 7
    assert body["ignorados"] == 3
    assert "LC 214/2025" in body["observacao_estimativa"]
