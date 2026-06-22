"""Testes do EfdContribuicoesService — orquestração + idempotência (Sprint 17 PR1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.modules.sped.efd.repo import ApuracaoPisCofinsAgregada
from app.modules.sped.efd.service import EfdContribuicoesService
from app.shared.exceptions import (
    EmpresaNaoElegivelEfd,
    EmpresaNaoEncontrada,
    SemDadosParaSped,
    SpedJaGerado,
)

# ── Fixtures de stub ──────────────────────────────────────────────────────


def _empresa_lp() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        regime_tributario="lucro_presumido",
        cnpj="12345678000190",
        razao_social="Comércio Modelo LTDA",
        nome_fantasia="Modelo",
        uf="SP",
        municipio="São Paulo",
        codigo_municipio_ibge="3550308",
        ie="111222333",
        im="987654",
    )


def _empresa_sn() -> SimpleNamespace:
    e = _empresa_lp()
    e.regime_tributario = "simples_nacional"
    return e


def _empresa_mei() -> SimpleNamespace:
    e = _empresa_lp()
    e.regime_tributario = "mei"
    return e


def _apuracao_canonica() -> ApuracaoPisCofinsAgregada:
    return ApuracaoPisCofinsAgregada(
        base_calculo_pis=Decimal("100000.00"),
        aliquota_pis=Decimal("0.0065"),  # fração — service converte
        valor_pis=Decimal("650.00"),
        base_calculo_cofins=Decimal("100000.00"),
        aliquota_cofins=Decimal("0.03"),
        valor_cofins=Decimal("3000.00"),
    )


def _doc_nfe_saida(empresa_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        tipo="nfe",
        direcao="saida",
        chave="35260612345678000190550010000010011000000010",
        numero="1001",
        serie="1",
        status="autorizada",
        emitida_em=datetime(2026, 3, 5, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo")),
        cnpj_emitente="12345678000190",
        cnpj_destinatario="99887766000155",
        valor_total=Decimal("100000.00"),
        valor_pis=Decimal("650.00"),
        valor_cofins=Decimal("3000.00"),
        valor_icms=Decimal("18000.00"),
        valor_ipi=Decimal("0"),
        valor_iss=Decimal("0"),
        cfop="5102",
        cst="00",
        ncm="22030000",
        evento=None,
    )


def _arquivo_sped_ativo(empresa_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        tipo="efd_contribuicoes",
        periodo_inicio=date(2026, 3, 1),
        periodo_fim=date(2026, 3, 31),
        superseded_by=None,
        hash_arquivo="0" * 64,
        algoritmo_versao="sped.efd_contribuicoes.v1",
        gerado_em=datetime(2026, 4, 5),
        status="gerado",
    )


# ── Patches helper ────────────────────────────────────────────────────────


def _patch_repos(
    *,
    empresa,
    apuracao,
    documentos=(),
    ativo=None,
):
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    apur_repo = AsyncMock()
    apur_repo.por_competencia = AsyncMock(return_value=apuracao)

    docs_repo = AsyncMock()
    docs_repo.por_periodo = AsyncMock(return_value=list(documentos))

    sped_repo = AsyncMock()
    sped_repo.ativo = AsyncMock(return_value=ativo)
    sped_repo.criar = AsyncMock(side_effect=lambda x: x)
    sped_repo.marcar_superseded = AsyncMock()

    return (
        patch(
            "app.modules.sped.efd.service.EmpresaRepo",
            return_value=empresa_repo,
        ),
        patch(
            "app.modules.sped.efd.service.ApuracoesPisCofinsRepo",
            return_value=apur_repo,
        ),
        patch(
            "app.modules.sped.efd.service.DocumentosParaEfdRepo",
            return_value=docs_repo,
        ),
        patch(
            "app.modules.sped.efd.service.ArquivoSpedRepo",
            return_value=sped_repo,
        ),
        sped_repo,
        apur_repo,
        docs_repo,
    )


# ── Testes de orquestração ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gera_efd_contribuicoes_persiste_arquivo_com_hash() -> None:
    empresa = _empresa_lp()
    docs = [_doc_nfe_saida(empresa.id)]
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, sped_repo, *_ = _patch_repos(
        empresa=empresa,
        apuracao=_apuracao_canonica(),
        documentos=docs,
    )
    with p_emp, p_apur, p_docs, p_sped:
        gerada = await EfdContribuicoesService().gerar(
            session, uuid.uuid4(), empresa.id, competencia=date(2026, 3, 15),
        )

    assert gerada.conteudo.startswith(b"|0000|")
    assert gerada.arquivo.tipo == "efd_contribuicoes"
    assert gerada.arquivo.periodo_inicio == date(2026, 3, 1)
    assert gerada.arquivo.periodo_fim == date(2026, 3, 31)
    assert gerada.arquivo.algoritmo_versao == "sped.efd_contribuicoes.v4"
    assert len(gerada.arquivo.hash_arquivo) == 64
    sped_repo.criar.assert_awaited_once()
    sped_repo.marcar_superseded.assert_not_awaited()
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_mei_rejeitado() -> None:
    empresa = _empresa_mei()
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, sped_repo, *_ = _patch_repos(
        empresa=empresa, apuracao=_apuracao_canonica(),
    )
    with p_emp, p_apur, p_docs, p_sped, pytest.raises(EmpresaNaoElegivelEfd, match="Lucro Presumido"):
        await EfdContribuicoesService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
        )
    sped_repo.criar.assert_not_awaited()


@pytest.mark.asyncio
async def test_simples_nacional_rejeitado() -> None:
    empresa = _empresa_sn()
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, sped_repo, *_ = _patch_repos(
        empresa=empresa, apuracao=_apuracao_canonica(),
    )
    with p_emp, p_apur, p_docs, p_sped, pytest.raises(EmpresaNaoElegivelEfd, match="DEFIS"):
        await EfdContribuicoesService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
        )
    sped_repo.criar.assert_not_awaited()


@pytest.mark.asyncio
async def test_empresa_inexistente_levanta_404() -> None:
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, *_ = _patch_repos(
        empresa=None, apuracao=None,
    )
    with p_emp, p_apur, p_docs, p_sped, pytest.raises(EmpresaNaoEncontrada):
        await EfdContribuicoesService().gerar(
            session, uuid.uuid4(), uuid.uuid4(),
            competencia=date(2026, 3, 1),
        )


@pytest.mark.asyncio
async def test_sem_apuracao_levanta_sem_dados() -> None:
    empresa = _empresa_lp()
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, *_ = _patch_repos(
        empresa=empresa, apuracao=None,
    )
    with p_emp, p_apur, p_docs, p_sped, pytest.raises(SemDadosParaSped, match="Apuração PIS"):
        await EfdContribuicoesService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
        )


@pytest.mark.asyncio
async def test_idempotencia_sem_forcar_levanta_conflito() -> None:
    empresa = _empresa_lp()
    ativo = _arquivo_sped_ativo(empresa.id)
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, sped_repo, *_ = _patch_repos(
        empresa=empresa, apuracao=_apuracao_canonica(), ativo=ativo,
    )
    with p_emp, p_apur, p_docs, p_sped, pytest.raises(SpedJaGerado, match="já gerada"):
        await EfdContribuicoesService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
        )
    sped_repo.criar.assert_not_awaited()
    sped_repo.marcar_superseded.assert_not_awaited()


@pytest.mark.asyncio
async def test_forcar_supersede_versao_anterior() -> None:
    empresa = _empresa_lp()
    ativo = _arquivo_sped_ativo(empresa.id)
    docs = [_doc_nfe_saida(empresa.id)]
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, sped_repo, *_ = _patch_repos(
        empresa=empresa,
        apuracao=_apuracao_canonica(),
        documentos=docs,
        ativo=ativo,
    )
    with p_emp, p_apur, p_docs, p_sped:
        gerada = await EfdContribuicoesService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
            forcar=True,
        )
    assert gerada.arquivo.supersedes == ativo.id
    sped_repo.criar.assert_awaited_once()
    sped_repo.marcar_superseded.assert_awaited_once()


@pytest.mark.asyncio
async def test_competencia_normalizada_para_inicio_de_mes() -> None:
    """``competencia=2026-03-15`` deriva ``periodo_inicio=2026-03-01``."""
    empresa = _empresa_lp()
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, sped_repo, *rest = _patch_repos(
        empresa=empresa,
        apuracao=_apuracao_canonica(),
        documentos=[],
    )
    with p_emp, p_apur, p_docs, p_sped:
        gerada = await EfdContribuicoesService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 27),
        )
    assert gerada.arquivo.periodo_inicio == date(2026, 3, 1)
    assert gerada.arquivo.periodo_fim == date(2026, 3, 31)


@pytest.mark.asyncio
async def test_sem_codigo_municipio_levanta_sem_dados() -> None:
    empresa = _empresa_lp()
    empresa.codigo_municipio_ibge = None  # type: ignore[assignment]
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, *_ = _patch_repos(
        empresa=empresa,
        apuracao=_apuracao_canonica(),
        documentos=[],
    )
    with p_emp, p_apur, p_docs, p_sped, pytest.raises(SemDadosParaSped, match="codigo_municipio_ibge"):
        await EfdContribuicoesService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
        )
