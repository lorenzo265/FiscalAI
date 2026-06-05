"""Testes do EcdService — orquestração + idempotência (Sprint 16 PR1)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.relatorios.calcula_balanco import (
    LinhaBalanco,
    ResultadoBalanco,
)
from app.modules.relatorios.calcula_dre import LinhaDre, ResultadoDre
from app.modules.sped.ecd.repo import (
    LancamentoComPartidas,
    SaldoMensalConta,
)
from app.modules.sped.ecd.service import EcdService
from app.shared.exceptions import (
    EmpresaNaoElegivelEcd,
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


def _empresa_mei() -> SimpleNamespace:
    e = _empresa_lp()
    e.regime_tributario = "mei"
    return e


def _conta(
    codigo: str,
    descricao: str,
    natureza: str,
    *,
    nivel: int = 1,
    aceita: bool = False,
    ref: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        codigo=codigo,
        descricao=descricao,
        natureza=natureza,
        nivel=nivel,
        aceita_lancamento=aceita,
        codigo_ecd_referencial=ref,
    )


def _plano_minimo() -> list[SimpleNamespace]:
    return [
        _conta("1", "ATIVO", "D", nivel=1, ref="1"),
        _conta("1.1.1.01", "Caixa", "D", nivel=4, aceita=True, ref="1.01.01.01.01.01"),
        _conta("4", "RECEITAS", "C", nivel=1, ref="4"),
        _conta("4.1.01", "Receita Serviços", "C", nivel=3, aceita=True,
               ref="4.01.01.01.01.01"),
        _conta("5", "DESPESAS", "D", nivel=1, ref="4.99"),
        _conta("5.1.01", "CMV", "D", nivel=3, aceita=True,
               ref="4.02.01.01.01.01"),
    ]


def _lancamento_par(plano: list[SimpleNamespace]) -> LancamentoComPartidas:
    caixa = next(c for c in plano if c.codigo == "1.1.1.01")
    receita = next(c for c in plano if c.codigo == "4.1.01")
    lanc = SimpleNamespace(
        id=uuid.uuid4(),
        data_lancamento=date(2025, 3, 15),
        competencia=date(2025, 3, 1),
        historico="Recebimento serviço",
        total_debito=Decimal("1000.00"),
        total_credito=Decimal("1000.00"),
        status="confirmado",
    )
    p_d = SimpleNamespace(
        lancamento_id=lanc.id,
        conta_contabil_id=caixa,
        tipo="D",
        valor=Decimal("1000.00"),
        ordem=1,
    )
    p_c = SimpleNamespace(
        lancamento_id=lanc.id,
        conta_contabil_id=receita,
        tipo="C",
        valor=Decimal("1000.00"),
        ordem=2,
    )
    return LancamentoComPartidas(
        lancamento=lanc,
        partidas=((p_d, caixa), (p_c, receita)),
    )


def _saldo_mes(
    conta: SimpleNamespace, competencia: date, *, debitos: Decimal, creditos: Decimal,
    saldo_inicial: Decimal = Decimal("0"),
) -> SaldoMensalConta:
    if conta.natureza == "D":
        saldo_final = saldo_inicial + debitos - creditos
    else:
        saldo_final = saldo_inicial - debitos + creditos
    return SaldoMensalConta(
        conta=conta,
        competencia=competencia,
        saldo_inicial=saldo_inicial,
        total_debitos=debitos,
        total_creditos=creditos,
        saldo_final=saldo_final,
    )


def _balanco_resultado_vazio() -> ResultadoBalanco:
    zero = Decimal("0.00")
    vazia = LinhaBalanco(rotulo="x", valor=zero, contas=())
    return ResultadoBalanco(
        ativo_circulante=LinhaBalanco("Ativo Circulante", zero, ()),
        ativo_nao_circulante=LinhaBalanco("Ativo Não Circulante", zero, ()),
        ativo_total=LinhaBalanco("ATIVO TOTAL", zero, ()),
        passivo_circulante=LinhaBalanco("Passivo Circulante", zero, ()),
        passivo_nao_circulante=LinhaBalanco("Passivo Não Circulante", zero, ()),
        patrimonio_liquido=LinhaBalanco("Patrimônio Líquido", zero, ()),
        passivo_mais_pl_total=LinhaBalanco("PASSIVO + PL TOTAL", zero, ()),
        fecha=True,
        diferenca=zero,
    )


def _arquivo_sped_ativo(empresa_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        tipo="ecd",
        periodo_inicio=date(2025, 1, 1),
        periodo_fim=date(2025, 12, 31),
        superseded_by=None,
        hash_arquivo="0" * 64,
        algoritmo_versao="sped.ecd.v2",
        gerado_em=datetime(2026, 1, 5),
        status="gerado",
    )


# ── Patches helper ────────────────────────────────────────────────────────


def _patch_repos(
    *,
    empresa,
    plano,
    lancamentos,
    saldos,
    ativo=None,
    movimento_resultado=None,
    irpj_csll=Decimal("0"),
    saldos_posicao=None,
):
    """Cria mocks para todos os repos consumidos pelo service."""
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    contabil_repo = AsyncMock()
    contabil_repo.listar_plano_contas_vigente = AsyncMock(return_value=plano)
    contabil_repo.listar_lancamentos_do_periodo = AsyncMock(
        return_value=lancamentos
    )
    contabil_repo.listar_saldos_mensais = AsyncMock(return_value=saldos)

    saldos_repo = AsyncMock()
    saldos_repo.saldos_posicao_em = AsyncMock(
        return_value=saldos_posicao or []
    )
    saldos_repo.movimento_resultado_periodo = AsyncMock(
        return_value=movimento_resultado or []
    )
    saldos_repo.irpj_csll_apurado_no_periodo = AsyncMock(return_value=irpj_csll)

    sped_repo = AsyncMock()
    sped_repo.ativo = AsyncMock(return_value=ativo)
    sped_repo.criar = AsyncMock(side_effect=lambda x: x)
    sped_repo.marcar_superseded = AsyncMock()

    return (
        patch("app.modules.sped.ecd.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.sped.ecd.service.ContabilParaEcdRepo",
            return_value=contabil_repo,
        ),
        patch(
            "app.modules.sped.ecd.service.SaldosPeriodoRepo",
            return_value=saldos_repo,
        ),
        patch(
            "app.modules.sped.ecd.service.ArquivoSpedRepo",
            return_value=sped_repo,
        ),
        sped_repo,
        contabil_repo,
    )


@pytest.fixture(autouse=True)
def _bypass_balanco_dre() -> Any:
    """Stub `calcular_balanco`/`calcular_dre` para evitar dependência forte
    em dados de balancete completos — testamos a orquestração, não os
    cálculos (que têm suítes próprias)."""
    zero = Decimal("0.00")
    balanco = _balanco_resultado_vazio()
    dre = ResultadoDre(
        receita_bruta=LinhaDre("Receita Bruta", zero, ()),
        deducoes=LinhaDre("(-) Impostos sobre Receita", zero, ()),
        receita_liquida=LinhaDre("Receita Líquida", zero, ()),
        cmv=LinhaDre("(-) CMV", zero, ()),
        lucro_bruto=LinhaDre("Lucro Bruto", zero, ()),
        despesas_pessoal=LinhaDre("Despesas Pessoal", zero, ()),
        outras_despesas=LinhaDre("Outras Despesas", zero, ()),
        ebitda=LinhaDre("EBITDA", zero, ()),
        depreciacao=LinhaDre("Depreciação", zero, ()),
        ebit=LinhaDre("EBIT", zero, ()),
        outras_receitas=LinhaDre("(+) Outras Receitas", zero, ()),
        resultado_financeiro=LinhaDre("Result. Financeiro", zero, ()),
        lair=LinhaDre("LAIR", zero, ()),
        irpj_csll=LinhaDre("IRPJ+CSLL", zero, ()),
        lucro_liquido=LinhaDre("Lucro Líquido", zero, ()),
    )
    with (
        patch(
            "app.modules.sped.ecd.service.calcular_balanco",
            return_value=balanco,
        ),
        patch(
            "app.modules.sped.ecd.service.calcular_dre",
            return_value=dre,
        ),
    ):
        yield


# ── Testes de orquestração ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gera_ecd_feliz_persiste_arquivo_com_hash() -> None:
    empresa = _empresa_lp()
    plano = _plano_minimo()
    lancs = [_lancamento_par(plano)]
    saldos = [
        _saldo_mes(plano[1], date(2025, 3, 1),
                   debitos=Decimal("1000.00"), creditos=Decimal("0")),
        _saldo_mes(plano[3], date(2025, 3, 1),
                   debitos=Decimal("0"), creditos=Decimal("1000.00")),
    ]
    session = AsyncMock()

    p_emp, p_cont, p_sld, p_sped, sped_repo, contabil_repo = _patch_repos(
        empresa=empresa, plano=plano, lancamentos=lancs, saldos=saldos,
    )
    with p_emp, p_cont, p_sld, p_sped:
        gerada = await EcdService().gerar(
            session, uuid.uuid4(), empresa.id, ano=2025
        )

    assert gerada.conteudo.startswith(b"|0000|")
    assert gerada.arquivo.tamanho_bytes == len(gerada.conteudo)
    assert gerada.arquivo.tipo == "ecd"
    assert gerada.arquivo.periodo_inicio == date(2025, 1, 1)
    assert gerada.arquivo.periodo_fim == date(2025, 12, 31)
    assert gerada.arquivo.algoritmo_versao == "sped.ecd.v2"
    assert len(gerada.arquivo.hash_arquivo) == 64
    sped_repo.criar.assert_awaited_once()
    sped_repo.marcar_superseded.assert_not_awaited()
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_mei_rejeitado() -> None:
    empresa = _empresa_mei()
    session = AsyncMock()
    p_emp, p_cont, p_sld, p_sped, sped_repo, _ = _patch_repos(
        empresa=empresa, plano=[], lancamentos=[], saldos=[],
    )
    with p_emp, p_cont, p_sld, p_sped:
        with pytest.raises(EmpresaNaoElegivelEcd, match="MEI"):
            await EcdService().gerar(
                session, uuid.uuid4(), empresa.id, ano=2025
            )
    sped_repo.criar.assert_not_awaited()


@pytest.mark.asyncio
async def test_empresa_inexistente_levanta_404() -> None:
    session = AsyncMock()
    p_emp, p_cont, p_sld, p_sped, _, _ = _patch_repos(
        empresa=None, plano=[], lancamentos=[], saldos=[],
    )
    with p_emp, p_cont, p_sld, p_sped:
        with pytest.raises(EmpresaNaoEncontrada):
            await EcdService().gerar(
                session, uuid.uuid4(), uuid.uuid4(), ano=2025
            )


@pytest.mark.asyncio
async def test_plano_vazio_levanta_sem_dados() -> None:
    empresa = _empresa_lp()
    session = AsyncMock()
    p_emp, p_cont, p_sld, p_sped, _, _ = _patch_repos(
        empresa=empresa, plano=[], lancamentos=[], saldos=[],
    )
    with p_emp, p_cont, p_sld, p_sped:
        with pytest.raises(SemDadosParaSped, match="Plano de contas vazio"):
            await EcdService().gerar(
                session, uuid.uuid4(), empresa.id, ano=2025
            )


@pytest.mark.asyncio
async def test_sem_lancamentos_levanta_sem_dados() -> None:
    empresa = _empresa_lp()
    plano = _plano_minimo()
    session = AsyncMock()
    p_emp, p_cont, p_sld, p_sped, _, _ = _patch_repos(
        empresa=empresa, plano=plano, lancamentos=[], saldos=[],
    )
    with p_emp, p_cont, p_sld, p_sped:
        with pytest.raises(SemDadosParaSped, match="lançamento"):
            await EcdService().gerar(
                session, uuid.uuid4(), empresa.id, ano=2025
            )


@pytest.mark.asyncio
async def test_idempotencia_409_quando_ja_existe_e_nao_forca() -> None:
    empresa = _empresa_lp()
    ativo = _arquivo_sped_ativo(empresa.id)
    session = AsyncMock()
    p_emp, p_cont, p_sld, p_sped, sped_repo, _ = _patch_repos(
        empresa=empresa, plano=_plano_minimo(), lancamentos=[],
        saldos=[], ativo=ativo,
    )
    with p_emp, p_cont, p_sld, p_sped:
        with pytest.raises(SpedJaGerado):
            await EcdService().gerar(
                session, uuid.uuid4(), empresa.id, ano=2025
            )
    sped_repo.criar.assert_not_awaited()


@pytest.mark.asyncio
async def test_forcar_true_supersede_anterior() -> None:
    empresa = _empresa_lp()
    plano = _plano_minimo()
    lancs = [_lancamento_par(plano)]
    saldos: list[SaldoMensalConta] = []
    ativo = _arquivo_sped_ativo(empresa.id)
    session = AsyncMock()
    p_emp, p_cont, p_sld, p_sped, sped_repo, _ = _patch_repos(
        empresa=empresa, plano=plano, lancamentos=lancs,
        saldos=saldos, ativo=ativo,
    )
    with p_emp, p_cont, p_sld, p_sped:
        gerada = await EcdService().gerar(
            session, uuid.uuid4(), empresa.id, ano=2025, forcar=True,
        )
    sped_repo.criar.assert_awaited_once()
    sped_repo.marcar_superseded.assert_awaited_once()
    # O novo arquivo registra supersedes apontando para o anterior.
    assert gerada.arquivo.supersedes == ativo.id


@pytest.mark.asyncio
async def test_empresa_sem_ibge_levanta_sem_dados() -> None:
    empresa = _empresa_lp()
    empresa.codigo_municipio_ibge = None
    plano = _plano_minimo()
    lancs = [_lancamento_par(plano)]
    session = AsyncMock()
    p_emp, p_cont, p_sld, p_sped, _, _ = _patch_repos(
        empresa=empresa, plano=plano, lancamentos=lancs, saldos=[],
    )
    with p_emp, p_cont, p_sld, p_sped:
        with pytest.raises(SemDadosParaSped, match="codigo_municipio_ibge"):
            await EcdService().gerar(
                session, uuid.uuid4(), empresa.id, ano=2025
            )
