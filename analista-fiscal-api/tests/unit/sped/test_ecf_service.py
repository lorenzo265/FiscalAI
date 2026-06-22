"""Testes do EcfService — orquestração + idempotência (Sprint 16 PR2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.fiscal.snapshots import CsllLpSnapshot, IrpjLpSnapshot
from app.modules.sped.ecf.repo import (
    ApuracaoTrimestreLp,
)
from app.modules.sped.ecf.service import EcfService
from app.shared.exceptions import (
    EmpresaNaoElegivelEcd,
    EmpresaNaoEncontrada,
    SemDadosParaSped,
    SpedJaGerado,
)

# ── Fixtures ───────────────────────────────────────────────────────────────


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


def _empresa_simples() -> SimpleNamespace:
    e = _empresa_lp()
    e.regime_tributario = "simples_nacional"
    return e


def _empresa_mei() -> SimpleNamespace:
    e = _empresa_lp()
    e.regime_tributario = "mei"
    return e


def _conta(codigo: str, descricao: str, natureza: str, *,
           nivel: int = 1, aceita: bool = False,
           ref: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        codigo=codigo, descricao=descricao, natureza=natureza, nivel=nivel,
        aceita_lancamento=aceita, codigo_ecd_referencial=ref,
    )


def _plano() -> list[SimpleNamespace]:
    return [
        _conta("1", "ATIVO", "D", nivel=1, ref="1"),
        _conta("1.1.1.01", "Caixa", "D", nivel=4, aceita=True,
               ref="1.01.01.01.01.01"),
        _conta("4.1.01", "Receita Serv.", "C", nivel=3, aceita=True,
               ref="4.01.01.01.01.01"),
    ]


def _apuracao_trimestre(numero: int) -> ApuracaoTrimestreLp:
    """Trimestre serviços (32%) com R$ 100k receita."""
    competencia = date(2025, 3 * (numero - 1) + 1, 1)
    irpj = IrpjLpSnapshot(
        irpj_total=Decimal("4800.00"),
        irpj_devido=Decimal("4800.00"),
        irrf_consumido=Decimal("0"),
        irrf_saldo_credor=Decimal("0"),
        base_total=Decimal("32000.00"),
        base_presumida=Decimal("32000.00"),
        receita_bruta_trimestre=Decimal("100000.00"),
        meses_periodo=3,
        percentual_presuncao=Decimal("0.3200"),
        ganhos_capital=Decimal("0"),
        receitas_aplicacoes=Decimal("0"),
        outras_adicoes=Decimal("0"),
        limite_adicional=Decimal("60000.00"),
        irpj_normal=Decimal("4800.00"),
        irpj_adicional=Decimal("0"),
        irrf_a_compensar=Decimal("0"),
    )
    csll = CsllLpSnapshot(
        csll=Decimal("2880.00"),
        base_total=Decimal("32000.00"),
        base_presumida=Decimal("32000.00"),
        receita_bruta_trimestre=Decimal("100000.00"),
        percentual_presuncao=Decimal("0.3200"),
        outras_adicoes=Decimal("0"),
    )
    return ApuracaoTrimestreLp(
        numero=numero, irpj=irpj, csll=csll, competencia=competencia,
    )


def _arquivo_sped_ativo(empresa_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        tipo="ecf",
        periodo_inicio=date(2025, 1, 1),
        periodo_fim=date(2025, 12, 31),
        superseded_by=None,
        hash_arquivo="0" * 64,
        algoritmo_versao="sped.ecf.v2",
        gerado_em=datetime(2026, 7, 5),
        status="gerado",
    )


def _patch_repos(
    *,
    empresa,
    apuracoes,
    plano,
    saldos=None,
    ativo=None,
    ecd_vinculada=None,
):
    """Cria mocks para os 5 repos consumidos pelo EcfService."""
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    ap_repo = AsyncMock()
    ap_repo.listar_trimestres_do_ano = AsyncMock(return_value=apuracoes)

    contabil_repo = AsyncMock()
    contabil_repo.listar_plano_contas_vigente = AsyncMock(return_value=plano)

    saldos_repo = AsyncMock()
    saldos_repo.saldos_no_trimestre = AsyncMock(
        return_value=saldos or []
    )

    ecd_repo = AsyncMock()
    ecd_repo.por_ano = AsyncMock(return_value=ecd_vinculada)

    sped_repo = AsyncMock()
    sped_repo.ativo = AsyncMock(return_value=ativo)
    sped_repo.criar = AsyncMock(side_effect=lambda x: x)
    sped_repo.marcar_superseded = AsyncMock()

    return (
        patch("app.modules.sped.ecf.service.EmpresaRepo",
              return_value=empresa_repo),
        patch("app.modules.sped.ecf.service.ApuracoesLpParaEcfRepo",
              return_value=ap_repo),
        patch("app.modules.sped.ecf.service.ContabilParaEcdRepo",
              return_value=contabil_repo),
        patch("app.modules.sped.ecf.service.SaldosTrimestreParaEcfRepo",
              return_value=saldos_repo),
        patch("app.modules.sped.ecf.service.EcdVinculadaRepo",
              return_value=ecd_repo),
        patch("app.modules.sped.ecf.service.ArquivoSpedRepo",
              return_value=sped_repo),
        sped_repo,
    )


# ── Testes ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gera_ecf_feliz_com_4_trimestres() -> None:
    empresa = _empresa_lp()
    apuracoes = [_apuracao_trimestre(n) for n in range(1, 5)]
    session = AsyncMock()

    pE, pA, pC, pS, pEcd, pSped, sped_repo = _patch_repos(
        empresa=empresa, apuracoes=apuracoes, plano=_plano(),
    )
    with pE, pA, pC, pS, pEcd, pSped:
        gerada = await EcfService().gerar(
            session, uuid.uuid4(), empresa.id, ano=2025,
        )

    assert gerada.conteudo.startswith(b"|0000|LECF|")
    assert gerada.arquivo.tipo == "ecf"
    assert gerada.arquivo.periodo_inicio == date(2025, 1, 1)
    assert gerada.arquivo.periodo_fim == date(2025, 12, 31)
    assert gerada.arquivo.algoritmo_versao == "sped.ecf.v2"
    assert len(gerada.arquivo.hash_arquivo) == 64
    sped_repo.criar.assert_awaited_once()
    sped_repo.marcar_superseded.assert_not_awaited()


@pytest.mark.asyncio
async def test_mei_rejeitado() -> None:
    empresa = _empresa_mei()
    session = AsyncMock()
    pE, pA, pC, pS, pEcd, pSped, _ = _patch_repos(
        empresa=empresa, apuracoes=[], plano=[],
    )
    with pE, pA, pC, pS, pEcd, pSped, pytest.raises(EmpresaNaoElegivelEcd, match="MEI"):
        await EcfService().gerar(
            session, uuid.uuid4(), empresa.id, ano=2025,
        )


@pytest.mark.asyncio
async def test_simples_nacional_rejeitado() -> None:
    """ECF MVP só suporta Lucro Presumido."""
    empresa = _empresa_simples()
    session = AsyncMock()
    pE, pA, pC, pS, pEcd, pSped, _ = _patch_repos(
        empresa=empresa, apuracoes=[], plano=[],
    )
    with pE, pA, pC, pS, pEcd, pSped, pytest.raises(EmpresaNaoElegivelEcd, match="simples"):
        await EcfService().gerar(
            session, uuid.uuid4(), empresa.id, ano=2025,
        )


@pytest.mark.asyncio
async def test_sem_apuracoes_levanta_sem_dados() -> None:
    empresa = _empresa_lp()
    session = AsyncMock()
    pE, pA, pC, pS, pEcd, pSped, _ = _patch_repos(
        empresa=empresa, apuracoes=[], plano=_plano(),
    )
    with pE, pA, pC, pS, pEcd, pSped, pytest.raises(SemDadosParaSped, match="apuração"):
        await EcfService().gerar(
            session, uuid.uuid4(), empresa.id, ano=2025,
        )


@pytest.mark.asyncio
async def test_plano_vazio_levanta_sem_dados() -> None:
    empresa = _empresa_lp()
    apuracoes = [_apuracao_trimestre(n) for n in range(1, 5)]
    session = AsyncMock()
    pE, pA, pC, pS, pEcd, pSped, _ = _patch_repos(
        empresa=empresa, apuracoes=apuracoes, plano=[],
    )
    with pE, pA, pC, pS, pEcd, pSped, pytest.raises(SemDadosParaSped, match="Plano de contas"):
        await EcfService().gerar(
            session, uuid.uuid4(), empresa.id, ano=2025,
        )


@pytest.mark.asyncio
async def test_idempotencia_409_sem_forcar() -> None:
    empresa = _empresa_lp()
    ativo = _arquivo_sped_ativo(empresa.id)
    session = AsyncMock()
    pE, pA, pC, pS, pEcd, pSped, sped_repo = _patch_repos(
        empresa=empresa, apuracoes=[], plano=_plano(), ativo=ativo,
    )
    with pE, pA, pC, pS, pEcd, pSped, pytest.raises(SpedJaGerado):
        await EcfService().gerar(
            session, uuid.uuid4(), empresa.id, ano=2025,
        )
    sped_repo.criar.assert_not_awaited()


@pytest.mark.asyncio
async def test_forcar_supersede_anterior() -> None:
    empresa = _empresa_lp()
    apuracoes = [_apuracao_trimestre(n) for n in range(1, 5)]
    ativo = _arquivo_sped_ativo(empresa.id)
    session = AsyncMock()
    pE, pA, pC, pS, pEcd, pSped, sped_repo = _patch_repos(
        empresa=empresa, apuracoes=apuracoes, plano=_plano(), ativo=ativo,
    )
    with pE, pA, pC, pS, pEcd, pSped:
        gerada = await EcfService().gerar(
            session, uuid.uuid4(), empresa.id, ano=2025, forcar=True,
        )
    sped_repo.criar.assert_awaited_once()
    sped_repo.marcar_superseded.assert_awaited_once()
    assert gerada.arquivo.supersedes == ativo.id


@pytest.mark.asyncio
async def test_ecd_vinculada_propaga_para_arquivo() -> None:
    """Quando há ECD do ano, hash + recibo entram no bloco C040."""
    empresa = _empresa_lp()
    apuracoes = [_apuracao_trimestre(n) for n in range(1, 5)]
    ecd = SimpleNamespace(
        id=uuid.uuid4(),
        hash_arquivo="b" * 64,
        recibo_transmissao="RECECD999",
        transmitido_em=datetime(2026, 5, 30, 12, 0, 0),
    )
    session = AsyncMock()
    pE, pA, pC, pS, pEcd, pSped, _ = _patch_repos(
        empresa=empresa, apuracoes=apuracoes, plano=_plano(),
        ecd_vinculada=ecd,
    )
    with pE, pA, pC, pS, pEcd, pSped:
        gerada = await EcfService().gerar(
            session, uuid.uuid4(), empresa.id, ano=2025,
        )
    # C040 com o hash da ECD aparece no conteúdo gerado.
    assert b"bbbbbbbbbbbbbbbb" in gerada.conteudo  # parte do hash 'b'*64


@pytest.mark.asyncio
async def test_empresa_inexistente_levanta_404() -> None:
    session = AsyncMock()
    pE, pA, pC, pS, pEcd, pSped, _ = _patch_repos(
        empresa=None, apuracoes=[], plano=[],
    )
    with pE, pA, pC, pS, pEcd, pSped, pytest.raises(EmpresaNaoEncontrada):
        await EcfService().gerar(
            session, uuid.uuid4(), uuid.uuid4(), ano=2025,
        )


@pytest.mark.asyncio
async def test_empresa_sem_ibge_levanta_sem_dados() -> None:
    empresa = _empresa_lp()
    empresa.codigo_municipio_ibge = None
    apuracoes = [_apuracao_trimestre(n) for n in range(1, 5)]
    session = AsyncMock()
    pE, pA, pC, pS, pEcd, pSped, _ = _patch_repos(
        empresa=empresa, apuracoes=apuracoes, plano=_plano(),
    )
    with pE, pA, pC, pS, pEcd, pSped, pytest.raises(SemDadosParaSped, match="codigo_municipio_ibge"):
        await EcfService().gerar(
            session, uuid.uuid4(), empresa.id, ano=2025,
        )
