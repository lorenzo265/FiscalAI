"""Testes do ProvisoesService (Sprint 8 PR2)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.provisoes.schemas import GerarProvisaoIn
from app.modules.provisoes.service import ProvisoesService
from app.shared.exceptions import EmpresaNaoEncontrada


def _empresa(
    regime: str = "lucro_presumido",
    anexo_simples: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        regime_tributario=regime,
        anexo_simples=anexo_simples,
    )


@pytest.mark.asyncio
async def test_empresa_inexistente_levanta() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.provisoes.service.EmpresaRepo", return_value=empresa_repo
    ):
        with pytest.raises(EmpresaNaoEncontrada):
            await ProvisoesService().gerar_provisao_mensal(
                session,
                uuid.uuid4(),
                uuid.uuid4(),
                date(2026, 5, 1),
                GerarProvisaoIn(folha_mes_total=Decimal("1000")),
            )


@pytest.mark.asyncio
async def test_lote_lp_gera_6_linhas() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa("lucro_presumido")

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    chamadas: list[dict[str, object]] = []

    async def upsert_capturando(**kwargs: object) -> bool:
        chamadas.append(kwargs)
        return True

    repo = AsyncMock()
    repo.upsert_agregada = AsyncMock(side_effect=upsert_capturando)

    with (
        patch("app.modules.provisoes.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.provisoes.service.ProvisoesRepo", return_value=repo),
    ):
        out = await ProvisoesService().gerar_provisao_mensal(
            session,
            uuid.uuid4(),
            empresa.id,
            date(2026, 5, 1),
            GerarProvisaoIn(folha_mes_total=Decimal("10000.00")),
        )

    assert out.linhas_geradas == 6
    assert out.linhas_existentes == 0
    assert out.inss_aplicavel is True
    # valor_total = 1111,11 + 833,33 + 222,22 + 166,67 + 88,89 + 66,67 = 2488,89
    assert out.valor_total_provisionado == Decimal("2488.89")

    tipos_gerados = {c["tipo"] for c in chamadas}
    assert tipos_gerados == {
        "ferias",
        "13_salario",
        "inss_ferias",
        "inss_13",
        "fgts_ferias",
        "fgts_13",
    }


@pytest.mark.asyncio
async def test_lote_sn_inss_zero_mas_persiste_todas() -> None:
    """SN persiste as 6 linhas — INSS com valor 0."""
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa("simples_nacional")

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    chamadas: list[dict[str, object]] = []

    async def upsert_capturando(**kwargs: object) -> bool:
        chamadas.append(kwargs)
        return True

    repo = AsyncMock()
    repo.upsert_agregada = AsyncMock(side_effect=upsert_capturando)

    with (
        patch("app.modules.provisoes.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.provisoes.service.ProvisoesRepo", return_value=repo),
    ):
        out = await ProvisoesService().gerar_provisao_mensal(
            session,
            uuid.uuid4(),
            empresa.id,
            date(2026, 5, 1),
            GerarProvisaoIn(folha_mes_total=Decimal("10000.00")),
        )

    assert out.linhas_geradas == 6
    assert out.inss_aplicavel is False
    # INSS zerado nas duas linhas
    inss_chamadas = [c for c in chamadas if c["tipo"].startswith("inss")]
    assert len(inss_chamadas) == 2
    for c in inss_chamadas:
        assert c["valor_provisao"] == Decimal("0.00")
        assert c["aliquota"] == Decimal("0")


@pytest.mark.asyncio
async def test_lote_idempotente_segunda_execucao() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa("lucro_presumido")

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    repo = AsyncMock()
    repo.upsert_agregada = AsyncMock(return_value=False)  # tudo já existia

    with (
        patch("app.modules.provisoes.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.provisoes.service.ProvisoesRepo", return_value=repo),
    ):
        out = await ProvisoesService().gerar_provisao_mensal(
            session,
            uuid.uuid4(),
            empresa.id,
            date(2026, 5, 1),
            GerarProvisaoIn(folha_mes_total=Decimal("10000.00")),
        )

    assert out.linhas_geradas == 0
    assert out.linhas_existentes == 6
    assert out.valor_total_provisionado == Decimal("0.00")


@pytest.mark.asyncio
async def test_competencia_normalizada_para_dia_1() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa("lucro_presumido")
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    repo = AsyncMock()
    repo.upsert_agregada = AsyncMock(return_value=True)

    with (
        patch("app.modules.provisoes.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.provisoes.service.ProvisoesRepo", return_value=repo),
    ):
        out = await ProvisoesService().gerar_provisao_mensal(
            session,
            uuid.uuid4(),
            empresa.id,
            date(2026, 5, 15),  # dia diferente de 1
            GerarProvisaoIn(folha_mes_total=Decimal("1000")),
        )

    assert out.competencia == date(2026, 5, 1)
    # Todas as chamadas usaram dia 1
    for call in repo.upsert_agregada.await_args_list:
        assert call.kwargs["competencia"] == date(2026, 5, 1)
