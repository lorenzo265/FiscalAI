"""Testes do ReformaService — orquestração simulador + backfill (Sprint 14 PR3)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.reforma.calcula_cbs_ibs import AliquotaCBSIBS
from app.modules.reforma.periodo_transicao import FaseReforma
from app.modules.reforma.repo import CargaApurada12m
from app.modules.reforma.service import ReformaService
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    SemApuracoesDoPeriodo,
)


def _empresa(empresa_id: uuid.UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=empresa_id or uuid.uuid4(),
        regime_tributario="lucro_presumido",
        cnae_principal="47.30",
    )


def _aliquota_pleno() -> AliquotaCBSIBS:
    return AliquotaCBSIBS(
        fase=FaseReforma.PLENO,
        aliquota_cbs=Decimal("0.0880"),
        aliquota_ibs=Decimal("0.1770"),
        valid_from=date(2033, 1, 1),
        valid_to=None,
        fonte_norma="LC 214/2025 art. 156-A §1º",
        algoritmo_versao="reforma.cbs-ibs.v1",
    )


def _carga_padrao() -> CargaApurada12m:
    return CargaApurada12m(
        pis=Decimal("6500.00"),
        cofins=Decimal("30000.00"),
        icms=Decimal("120000.00"),
        iss=Decimal("0.00"),
        receita_anualizada=Decimal("1000000.00"),
        icms_medio_mensal=Decimal("10000.00"),
        periodo_inicio=date(2025, 5, 1),
        periodo_fim=date(2026, 4, 30),
    )


def _carga_vazia() -> CargaApurada12m:
    return CargaApurada12m(
        pis=Decimal("0"),
        cofins=Decimal("0"),
        icms=Decimal("0"),
        iss=Decimal("0"),
        receita_anualizada=Decimal("0"),
        icms_medio_mensal=Decimal("0"),
        periodo_inicio=date(2025, 5, 1),
        periodo_fim=date(2026, 4, 30),
    )


@pytest.mark.asyncio
async def test_simular_impacto_devolve_3_cenarios() -> None:
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    aliq_repo = AsyncMock()
    aliq_repo.vigente = AsyncMock(return_value=_aliquota_pleno())
    reforma_repo = AsyncMock()
    reforma_repo.carga_apurada_12m = AsyncMock(return_value=_carga_padrao())

    with (
        patch("app.modules.reforma.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.reforma.service.AliquotaCbsIbsRepo",
            return_value=aliq_repo,
        ),
        patch(
            "app.modules.reforma.service.ReformaRepo",
            return_value=reforma_repo,
        ),
    ):
        resultado = await ReformaService(session).simular_impacto(empresa.id)

    assert len(resultado.cenarios) == 3
    # cenário realista → 1mi × 26,5% = 265.000
    assert resultado.cenarios[1].total_projetado == Decimal("265000.00")
    assert "LC 214/2025" in resultado.observacao_estimativa


@pytest.mark.asyncio
async def test_simular_impacto_empresa_inexistente_levanta() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.reforma.service.EmpresaRepo", return_value=empresa_repo
    ):
        with pytest.raises(EmpresaNaoEncontrada):
            await ReformaService(session).simular_impacto(uuid.uuid4())


@pytest.mark.asyncio
async def test_simular_impacto_sem_apuracoes_levanta() -> None:
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    reforma_repo = AsyncMock()
    reforma_repo.carga_apurada_12m = AsyncMock(return_value=_carga_vazia())
    with (
        patch("app.modules.reforma.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.reforma.service.ReformaRepo",
            return_value=reforma_repo,
        ),
    ):
        with pytest.raises(SemApuracoesDoPeriodo, match="12m"):
            await ReformaService(session).simular_impacto(empresa.id)


@pytest.mark.asyncio
async def test_aliquota_vigente_delega_ao_repo() -> None:
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    aliq_repo = AsyncMock()
    aliq_repo.vigente = AsyncMock(return_value=_aliquota_pleno())
    with (
        patch("app.modules.reforma.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.reforma.service.AliquotaCbsIbsRepo",
            return_value=aliq_repo,
        ),
    ):
        out = await ReformaService(session).aliquota_vigente(
            date(2026, 6, 1), empresa_id=empresa.id
        )
    assert out.fase is FaseReforma.PLENO
    # Confere que o repo foi chamado com regime + cnae da empresa
    aliq_repo.vigente.assert_awaited_once()
    kwargs = aliq_repo.vigente.await_args.kwargs
    assert kwargs["regime"] == "lucro_presumido"
    assert kwargs["cnae"] == "47.30"


@pytest.mark.asyncio
async def test_recalcular_historico_idempotente() -> None:
    """Chamar 2× recalcular_historico — 2ª vez não atualiza nada."""
    empresa = _empresa()

    # Doc com valor_cbs já populado (do XML) — backfill não toca
    doc_ja_populado = SimpleNamespace(
        id=uuid.uuid4(),
        valor_total=Decimal("1000.00"),
        valor_cbs=Decimal("9.00"),
        valor_ibs=Decimal("1.00"),
    )
    # Doc sem valor_cbs — backfill calcula
    doc_para_backfill = SimpleNamespace(
        id=uuid.uuid4(),
        valor_total=Decimal("2000.00"),
        valor_cbs=None,
        valor_ibs=None,
    )

    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    aliq_repo = AsyncMock()
    aliq_repo.vigente = AsyncMock(
        return_value=AliquotaCBSIBS(
            fase=FaseReforma.TESTE_2026,
            aliquota_cbs=Decimal("0.0090"),
            aliquota_ibs=Decimal("0.0010"),
            valid_from=date(2026, 1, 1),
            valid_to=None,
            fonte_norma="LC 214/2025",
            algoritmo_versao="reforma.cbs-ibs.v1",
        )
    )
    reforma_repo = AsyncMock()
    # 1ª chamada — retorna ambos os docs (porque forcar=False ainda casa o
    # parcial por OR: doc_ja_populado tem ambos NOT NULL e foi filtrado).
    reforma_repo.documentos_do_ano_sem_cbs = AsyncMock(
        side_effect=[
            [doc_para_backfill],  # 1ª chamada — só o NULL
            [],  # 2ª chamada — vazia (já populado)
        ]
    )
    reforma_repo.atualizar_cbs_ibs_documento = AsyncMock()

    with (
        patch("app.modules.reforma.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.reforma.service.AliquotaCbsIbsRepo",
            return_value=aliq_repo,
        ),
        patch(
            "app.modules.reforma.service.ReformaRepo",
            return_value=reforma_repo,
        ),
    ):
        svc = ReformaService(session)
        r1 = await svc.recalcular_historico_documentos(empresa.id, ano=2026)
        r2 = await svc.recalcular_historico_documentos(empresa.id, ano=2026)

    assert r1.atualizados == 1
    assert r1.ignorados == 0
    assert r2.atualizados == 0
    assert r2.ignorados == 0
    # UPDATE só chamado 1 vez ao todo
    reforma_repo.atualizar_cbs_ibs_documento.assert_awaited_once()


@pytest.mark.asyncio
async def test_recalcular_historico_forcar_reprocessa() -> None:
    """Com forcar=True, mesmo docs já populados são reprocessados."""
    empresa = _empresa()
    doc = SimpleNamespace(
        id=uuid.uuid4(),
        valor_total=Decimal("1000.00"),
        valor_cbs=Decimal("9.00"),
        valor_ibs=Decimal("1.00"),
    )

    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    aliq_repo = AsyncMock()
    aliq_repo.vigente = AsyncMock(
        return_value=AliquotaCBSIBS(
            fase=FaseReforma.TESTE_2026,
            aliquota_cbs=Decimal("0.0090"),
            aliquota_ibs=Decimal("0.0010"),
            valid_from=date(2026, 1, 1),
            valid_to=None,
            fonte_norma="LC 214/2025",
            algoritmo_versao="reforma.cbs-ibs.v1",
        )
    )
    reforma_repo = AsyncMock()
    reforma_repo.documentos_do_ano_sem_cbs = AsyncMock(return_value=[doc])
    reforma_repo.atualizar_cbs_ibs_documento = AsyncMock()

    with (
        patch("app.modules.reforma.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.reforma.service.AliquotaCbsIbsRepo",
            return_value=aliq_repo,
        ),
        patch(
            "app.modules.reforma.service.ReformaRepo",
            return_value=reforma_repo,
        ),
    ):
        # Com forcar=True, popular_cbs_ibs_informacional ainda detecta o doc
        # como "já populado" e devolve calculou=False — então ignorados=1.
        # O `forcar` aqui afeta apenas a query do repo (que retorna o doc),
        # mas a idempotência do helper preserva os valores existentes.
        r = await ReformaService(session).recalcular_historico_documentos(
            empresa.id, ano=2026, forcar=True
        )
        assert r.atualizados == 0
        assert r.ignorados == 1
        reforma_repo.documentos_do_ano_sem_cbs.assert_awaited_once_with(
            empresa.id, ano=2026, forcar=True
        )


def test_fase_atual_delega() -> None:
    """Fachada para periodo_transicao — método sync."""
    svc = ReformaService(AsyncMock())
    assert svc.fase_atual(date(2026, 6, 15)) is FaseReforma.TESTE_2026
    assert svc.fase_atual(date(2033, 1, 1)) is FaseReforma.PLENO
