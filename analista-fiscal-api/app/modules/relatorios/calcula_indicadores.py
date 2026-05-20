"""Indicadores financeiros — análise tradicional de DREs e Balanços.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento técnico:
  * NBC TG 26 (R5) — apresentação das demonstrações.
  * Marion, Iudícibus, Matarazzo — manuais clássicos de análise financeira
    (índices padrão usados por bancos, auditoria, controladoria).

Indicadores cobertos:

  Liquidez:
    Corrente   = Ativo Circulante / Passivo Circulante
    Seca       = (Ativo Circulante − Estoques) / Passivo Circulante
    Geral      = (AC + Realizável LP) / (PC + Exigível LP)

  Estrutura de Capital:
    Endividamento Geral      = Passivo Total / Ativo Total
    Composição Endividamento = Passivo Circulante / Passivo Total

  Rentabilidade:
    Margem Bruta    = Lucro Bruto / Receita Líquida
    Margem EBITDA   = EBITDA / Receita Líquida
    Margem Líquida  = Lucro Líquido / Receita Líquida
    ROA             = Lucro Líquido / Ativo Total
    ROE             = Lucro Líquido / Patrimônio Líquido

  Atividade:
    Giro do Ativo   = Receita Líquida / Ativo Total

Convenções:
  * Indicadores de Liquidez/Endividamento/Giro: número absoluto (sem %).
  * Margens / ROA / ROE: número absoluto (caller multiplica × 100 para %).
  * Divisão por zero: retorna ``None`` (frontend mostra "N/A").
  * Quantização: 4 casas (NUMERIC 6,4) — granularidade suficiente para
    análise (~0,01%).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

from app.modules.relatorios.calcula_balanco import ResultadoBalanco
from app.modules.relatorios.calcula_dre import ResultadoDre

getcontext().prec = 28

ALGORITMO_VERSAO = "indicadores.financeiros.v1"

_PRECISAO = Decimal("0.0001")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class LinhaIndicador:
    rotulo: str
    valor: Decimal | None  # None quando divisor é zero
    formato: str  # 'razao' | 'percentual'


@dataclass(frozen=True, slots=True)
class ResultadoIndicadores:
    """Snapshot persistido em ``relatorio_gerado.payload`` (tipo='indicadores')."""

    # Liquidez
    liquidez_corrente: LinhaIndicador
    liquidez_seca: LinhaIndicador
    liquidez_geral: LinhaIndicador
    # Estrutura
    endividamento_geral: LinhaIndicador
    composicao_endividamento: LinhaIndicador
    # Rentabilidade
    margem_bruta: LinhaIndicador
    margem_ebitda: LinhaIndicador
    margem_liquida: LinhaIndicador
    roa: LinhaIndicador
    roe: LinhaIndicador
    # Atividade
    giro_ativo: LinhaIndicador
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_PRECISAO, rounding=ROUND_HALF_EVEN)


def _divide(numerador: Decimal, denominador: Decimal) -> Decimal | None:
    """Divide com ROUND_HALF_EVEN 4 casas; retorna None se denominador zero."""
    if denominador == _ZERO:
        return None
    return _quantizar(numerador / denominador)


def _estoques_de(balanco: ResultadoBalanco) -> Decimal:
    """Soma saldos de contas 1.1.3.x dentro do Ativo Circulante."""
    total = _ZERO
    for codigo, _desc, saldo in balanco.ativo_circulante.contas:
        if codigo == "1.1.3" or codigo.startswith("1.1.3."):
            total += saldo
    return total


def calcular_indicadores(
    balanco: ResultadoBalanco,
    dre: ResultadoDre,
) -> ResultadoIndicadores:
    """Calcula 11 indicadores financeiros a partir do Balanço + DRE.

    Args:
        balanco: Balanço Patrimonial do mesmo período (data de referência
            tipicamente = último dia do período do DRE).
        dre: DRE do período.

    Returns:
        ResultadoIndicadores.
    """
    ac = balanco.ativo_circulante.valor
    anc = balanco.ativo_nao_circulante.valor
    ativo_total = balanco.ativo_total.valor
    pc = balanco.passivo_circulante.valor
    pnc = balanco.passivo_nao_circulante.valor
    passivo_total = pc + pnc
    pl = balanco.patrimonio_liquido.valor
    estoques = _estoques_de(balanco)

    receita_liq = dre.receita_liquida.valor
    lucro_bruto = dre.lucro_bruto.valor
    ebitda = dre.ebitda.valor
    lucro_liquido = dre.lucro_liquido.valor

    return ResultadoIndicadores(
        liquidez_corrente=LinhaIndicador(
            "Liquidez Corrente", _divide(ac, pc), "razao",
        ),
        liquidez_seca=LinhaIndicador(
            "Liquidez Seca", _divide(ac - estoques, pc), "razao",
        ),
        liquidez_geral=LinhaIndicador(
            "Liquidez Geral",
            # MVP: AC + ANC / passivo total. Idealmente "Realizável LP" deve
            # excluir Imobilizado, mas o plano referencial atual não separa
            # essas contas. Anotado como pendência consciente.
            _divide(ac + anc, passivo_total),
            "razao",
        ),
        endividamento_geral=LinhaIndicador(
            "Endividamento Geral", _divide(passivo_total, ativo_total), "percentual",
        ),
        composicao_endividamento=LinhaIndicador(
            "Composição do Endividamento", _divide(pc, passivo_total), "percentual",
        ),
        margem_bruta=LinhaIndicador(
            "Margem Bruta", _divide(lucro_bruto, receita_liq), "percentual",
        ),
        margem_ebitda=LinhaIndicador(
            "Margem EBITDA", _divide(ebitda, receita_liq), "percentual",
        ),
        margem_liquida=LinhaIndicador(
            "Margem Líquida", _divide(lucro_liquido, receita_liq), "percentual",
        ),
        roa=LinhaIndicador(
            "ROA — Retorno sobre Ativo", _divide(lucro_liquido, ativo_total), "percentual",
        ),
        roe=LinhaIndicador(
            "ROE — Retorno sobre Patrimônio Líquido",
            _divide(lucro_liquido, pl), "percentual",
        ),
        giro_ativo=LinhaIndicador(
            "Giro do Ativo", _divide(receita_liq, ativo_total), "razao",
        ),
    )
