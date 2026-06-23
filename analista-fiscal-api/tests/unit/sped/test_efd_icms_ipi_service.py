"""Testes do EfdIcmsIpiService — orquestração + idempotência (Sprint 17 PR2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.modules.sped.efd.repo import ApuracaoIcmsLida
from app.modules.sped.efd.service import EfdIcmsIpiService
from app.shared.exceptions import (
    EmpresaNaoElegivelEfd,
    EmpresaNaoEncontrada,
    SemDadosParaSped,
    SpedJaGerado,
)

# ── Fixtures de stub ──────────────────────────────────────────────────────


def _empresa_sp_com_ie() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        regime_tributario="lucro_presumido",
        cnpj="12345678000190",
        razao_social="Comércio SP LTDA",
        nome_fantasia="Modelo",
        uf="SP",
        municipio="São Paulo",
        codigo_municipio_ibge="3550308",
        ie="111222333",
        im="987654",
    )


def _empresa_sem_ie() -> SimpleNamespace:
    e = _empresa_sp_com_ie()
    e.ie = None
    return e


def _apuracao_devedor() -> ApuracaoIcmsLida:
    return ApuracaoIcmsLida(
        uf="SP",
        debito=Decimal("9000.00"),
        credito=Decimal("0"),
        saldo_credor_anterior=Decimal("0"),
        ajustes_devedores=Decimal("0"),
        ajustes_credores=Decimal("0"),
        icms_a_recolher=Decimal("9000.00"),
        saldo_credor_a_transportar=Decimal("0"),
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
        valor_total=Decimal("50000.00"),
        valor_pis=Decimal("325.00"),
        valor_cofins=Decimal("1500.00"),
        valor_icms=Decimal("9000.00"),
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
        tipo="efd_icms_ipi",
        periodo_inicio=date(2026, 3, 1),
        periodo_fim=date(2026, 3, 31),
        superseded_by=None,
        hash_arquivo="0" * 64,
        algoritmo_versao="sped.efd_icms_ipi.v1",
        gerado_em=datetime(2026, 4, 5),
        status="gerado",
    )


def _patch_repos(
    *,
    empresa,
    apuracao,
    documentos=(),
    ativo=None,
    bens_ciap=(),
    dia_vencimento=10,
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

    # Sprint 19.6 PR1 (#33 + #31): novos repos chamados pelo service.
    aliquota_icms_repo = AsyncMock()
    aliquota_icms_repo.dia_vencimento_padrao_por_uf = AsyncMock(
        return_value=dia_vencimento
    )

    bem_repo = AsyncMock()
    bem_repo.listar_para_ciap = AsyncMock(return_value=list(bens_ciap))

    return (
        patch(
            "app.modules.sped.efd.service.EmpresaRepo",
            return_value=empresa_repo,
        ),
        patch(
            "app.modules.sped.efd.service.ApuracoesIcmsRepo",
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
        patch(
            "app.modules.sped.efd.service.AliquotaIcmsRepo",
            return_value=aliquota_icms_repo,
        ),
        patch(
            "app.modules.sped.efd.service.BemImobilizadoRepo",
            return_value=bem_repo,
        ),
        sped_repo,
        apur_repo,
        docs_repo,
    )


# ── Testes de orquestração ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gera_efd_icms_ipi_persiste_arquivo_com_hash() -> None:
    empresa = _empresa_sp_com_ie()
    docs = [_doc_nfe_saida(empresa.id)]
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, sped_repo, *_ = _patch_repos(
        empresa=empresa,
        apuracao=_apuracao_devedor(),
        documentos=docs,
    )
    with p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem:
        gerada = await EfdIcmsIpiService().gerar(
            session, uuid.uuid4(), empresa.id, competencia=date(2026, 3, 15),
        )

    assert gerada.conteudo.startswith(b"|0000|")
    assert gerada.arquivo.tipo == "efd_icms_ipi"
    assert gerada.arquivo.periodo_inicio == date(2026, 3, 1)
    assert gerada.arquivo.periodo_fim == date(2026, 3, 31)
    assert gerada.arquivo.algoritmo_versao == "sped.efd_icms_ipi.v4"
    assert len(gerada.arquivo.hash_arquivo) == 64
    sped_repo.criar.assert_awaited_once()
    sped_repo.marcar_superseded.assert_not_awaited()
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_empresa_sem_ie_rejeitada() -> None:
    empresa = _empresa_sem_ie()
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, sped_repo, *_ = _patch_repos(
        empresa=empresa, apuracao=_apuracao_devedor(),
    )
    with p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, pytest.raises(EmpresaNaoElegivelEfd, match="inscrição estadual"):
        await EfdIcmsIpiService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
        )
    sped_repo.criar.assert_not_awaited()


@pytest.mark.asyncio
async def test_empresa_inexistente_levanta_404() -> None:
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, *_ = _patch_repos(
        empresa=None, apuracao=None,
    )
    with p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, pytest.raises(EmpresaNaoEncontrada):
        await EfdIcmsIpiService().gerar(
            session, uuid.uuid4(), uuid.uuid4(),
            competencia=date(2026, 3, 1),
        )


@pytest.mark.asyncio
async def test_sem_apuracao_levanta_sem_dados() -> None:
    empresa = _empresa_sp_com_ie()
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, *_ = _patch_repos(
        empresa=empresa, apuracao=None,
    )
    with p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, pytest.raises(SemDadosParaSped, match="Apuração ICMS"):
        await EfdIcmsIpiService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
        )


@pytest.mark.asyncio
async def test_idempotencia_sem_forcar_levanta_conflito() -> None:
    empresa = _empresa_sp_com_ie()
    ativo = _arquivo_sped_ativo(empresa.id)
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, sped_repo, *_ = _patch_repos(
        empresa=empresa, apuracao=_apuracao_devedor(), ativo=ativo,
    )
    with p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, pytest.raises(SpedJaGerado, match="já gerada"):
        await EfdIcmsIpiService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
        )
    sped_repo.criar.assert_not_awaited()


@pytest.mark.asyncio
async def test_forcar_supersede_versao_anterior() -> None:
    empresa = _empresa_sp_com_ie()
    ativo = _arquivo_sped_ativo(empresa.id)
    docs = [_doc_nfe_saida(empresa.id)]
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, sped_repo, *_ = _patch_repos(
        empresa=empresa,
        apuracao=_apuracao_devedor(),
        documentos=docs,
        ativo=ativo,
    )
    with p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem:
        gerada = await EfdIcmsIpiService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
            forcar=True,
        )
    assert gerada.arquivo.supersedes == ativo.id
    sped_repo.criar.assert_awaited_once()
    sped_repo.marcar_superseded.assert_awaited_once()


@pytest.mark.asyncio
async def test_documentos_filtra_apenas_nfe_e_nfce() -> None:
    """Service deve pedir tipos=('nfe','nfce') ao repo — NFS-e fica fora."""
    empresa = _empresa_sp_com_ie()
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, sped_repo, _apur_repo, docs_repo = _patch_repos(
        empresa=empresa,
        apuracao=_apuracao_devedor(),
        documentos=[],
    )
    with p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem:
        await EfdIcmsIpiService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
        )
    docs_repo.por_periodo.assert_awaited_once()
    chamada = docs_repo.por_periodo.await_args
    assert chamada.kwargs.get("tipos") == ("nfe", "nfce")


@pytest.mark.asyncio
async def test_sem_codigo_municipio_levanta_sem_dados() -> None:
    empresa = _empresa_sp_com_ie()
    empresa.codigo_municipio_ibge = None  # type: ignore[assignment]
    session = AsyncMock()
    p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, *_ = _patch_repos(
        empresa=empresa,
        apuracao=_apuracao_devedor(),
        documentos=[],
    )
    with p_emp, p_apur, p_docs, p_sped, p_aliq, p_bem, pytest.raises(SemDadosParaSped, match="codigo_municipio_ibge"):
        await EfdIcmsIpiService().gerar(
            session, uuid.uuid4(), empresa.id,
            competencia=date(2026, 3, 1),
        )
