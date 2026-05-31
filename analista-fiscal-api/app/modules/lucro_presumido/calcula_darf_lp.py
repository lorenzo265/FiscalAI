"""Calculadora DARF — Lucro Presumido.

Camada 1 (determinística). Função pura, zero I/O.

Gera os dados do DARF (Documento de Arrecadação de Receitas Federais) para
os quatro tributos do Lucro Presumido:

  * **IRPJ** — código 2089; apuração trimestral.
  * **CSLL** — código 2372; apuração trimestral.
  * **PIS**  — código 8109; apuração mensal cumulativa (Lei 9.718/1998).
  * **Cofins** — código 2172; apuração mensal cumulativa.

Vencimentos (Lei 9.430/1996 art. 5º + IN RFB 1.700/2017):
  * IRPJ/CSLL: último dia do mês seguinte ao encerramento do trimestre.
    (ex.: T1 encerrado 31/03 → vence 30/04; T4 → vence 31/01 do ano seguinte)
  * PIS/Cofins: dia 25 do mês seguinte à competência.
    (ex.: jan/2026 → vence 25/02/2026; dez/2026 → vence 25/01/2027)

Nota MVP: vencimentos não ajustam para dias úteis. O ajuste (+1 dia quando
25 ou último-dia cai em fim de semana/feriado) depende do calendário federal
e fica a cargo do cliente/contador ao verificar o prazo no Receita Online.

Fundamento legal:
  * Lei 9.430/1996 art. 5º e 64 (IRPJ/CSLL LP + IRRF compensação).
  * IN RFB 1.700/2017 art. 33 (consolidação).
  * Lei 9.718/1998 art. 2º-3º (PIS/Cofins cumulativo).
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "lp.darf.v1"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")

# Códigos DARF RFB
_CODIGO_IRPJ = "2089"
_CODIGO_CSLL = "2372"
_CODIGO_PIS = "8109"
_CODIGO_COFINS = "2172"


@dataclass(frozen=True, slots=True)
class ResultadoDarfLp:
    """Dados do DARF prontos para persistir em ``guia_pagamento``."""

    codigo_receita: str
    denominacao: str
    competencia: date
    periodo_apuracao: str     # "2026-T1" (trim.) ou "2026-01" (mensal)
    valor_principal: Decimal
    juros: Decimal
    multa: Decimal
    total: Decimal
    data_vencimento: date
    algoritmo_versao: str = ALGORITMO_VERSAO
    fundamento_legal: str = ""


def calcular_darf_irpj(
    valor_devido: Decimal,
    ano: int,
    trimestre: int,
    *,
    juros: Decimal = _ZERO,
    multa: Decimal = _ZERO,
) -> ResultadoDarfLp:
    """Calcula DARF do IRPJ trimestral (código 2089).

    Args:
        valor_devido: ``irpj_devido`` da apuração trimestral (≥ 0).
        ano: ano-calendário (ex.: 2026).
        trimestre: 1, 2, 3 ou 4.
        juros: mora SELIC acumulada (default 0 — pago no prazo).
        multa: multa de mora (default 0 — pago no prazo).

    Returns:
        ResultadoDarfLp com vencimento no último dia do mês seguinte
        ao encerramento do trimestre.
    """
    _validar_valor(valor_devido, "valor_devido")
    _validar_valor(juros, "juros")
    _validar_valor(multa, "multa")
    _validar_trimestre(trimestre)

    competencia = _data_trimestre(ano, trimestre)
    vencimento = _vencimento_trimestral(ano, trimestre)
    total = _quantizar(valor_devido + juros + multa)

    return ResultadoDarfLp(
        codigo_receita=_CODIGO_IRPJ,
        denominacao="IRPJ — Lucro Presumido (trimestral)",
        competencia=competencia,
        periodo_apuracao=f"{ano}-T{trimestre}",
        valor_principal=_quantizar(valor_devido),
        juros=_quantizar(juros),
        multa=_quantizar(multa),
        total=total,
        data_vencimento=vencimento,
        fundamento_legal="Lei 9.430/1996 art. 5º; Lei 9.249/1995 art. 3º",
    )


def calcular_darf_csll(
    valor_devido: Decimal,
    ano: int,
    trimestre: int,
    *,
    juros: Decimal = _ZERO,
    multa: Decimal = _ZERO,
) -> ResultadoDarfLp:
    """Calcula DARF da CSLL trimestral (código 2372).

    Mesmo vencimento do IRPJ — Lei 9.430/1996 art. 5º.
    """
    _validar_valor(valor_devido, "valor_devido")
    _validar_valor(juros, "juros")
    _validar_valor(multa, "multa")
    _validar_trimestre(trimestre)

    competencia = _data_trimestre(ano, trimestre)
    vencimento = _vencimento_trimestral(ano, trimestre)
    total = _quantizar(valor_devido + juros + multa)

    return ResultadoDarfLp(
        codigo_receita=_CODIGO_CSLL,
        denominacao="CSLL — Lucro Presumido (trimestral)",
        competencia=competencia,
        periodo_apuracao=f"{ano}-T{trimestre}",
        valor_principal=_quantizar(valor_devido),
        juros=_quantizar(juros),
        multa=_quantizar(multa),
        total=total,
        data_vencimento=vencimento,
        fundamento_legal="Lei 7.689/1988; Lei 9.430/1996 art. 5º",
    )


def calcular_darf_pis(
    valor_devido: Decimal,
    competencia: date,
    *,
    juros: Decimal = _ZERO,
    multa: Decimal = _ZERO,
) -> ResultadoDarfLp:
    """Calcula DARF do PIS cumulativo mensal (código 8109).

    Args:
        valor_devido: ``tributo`` da apuração PIS mensal (≥ 0).
        competencia: primeiro dia do mês de apuração (ex.: date(2026, 1, 1)).
        juros: mora (default 0).
        multa: multa de mora (default 0).

    Returns:
        ResultadoDarfLp com vencimento no dia 25 do mês seguinte.
    """
    _validar_valor(valor_devido, "valor_devido")
    _validar_valor(juros, "juros")
    _validar_valor(multa, "multa")
    _validar_competencia(competencia)

    vencimento = _vencimento_mensal(competencia)
    total = _quantizar(valor_devido + juros + multa)

    return ResultadoDarfLp(
        codigo_receita=_CODIGO_PIS,
        denominacao="PIS — Regime Cumulativo (mensal)",
        competencia=competencia,
        periodo_apuracao=f"{competencia.year}-{competencia.month:02d}",
        valor_principal=_quantizar(valor_devido),
        juros=_quantizar(juros),
        multa=_quantizar(multa),
        total=total,
        data_vencimento=vencimento,
        fundamento_legal="Lei 9.718/1998 art. 2º-3º; IN RFB 1.911/2019",
    )


def calcular_darf_cofins(
    valor_devido: Decimal,
    competencia: date,
    *,
    juros: Decimal = _ZERO,
    multa: Decimal = _ZERO,
) -> ResultadoDarfLp:
    """Calcula DARF do Cofins cumulativo mensal (código 2172).

    Mesmo vencimento do PIS — dia 25 do mês seguinte.
    """
    _validar_valor(valor_devido, "valor_devido")
    _validar_valor(juros, "juros")
    _validar_valor(multa, "multa")
    _validar_competencia(competencia)

    vencimento = _vencimento_mensal(competencia)
    total = _quantizar(valor_devido + juros + multa)

    return ResultadoDarfLp(
        codigo_receita=_CODIGO_COFINS,
        denominacao="Cofins — Regime Cumulativo (mensal)",
        competencia=competencia,
        periodo_apuracao=f"{competencia.year}-{competencia.month:02d}",
        valor_principal=_quantizar(valor_devido),
        juros=_quantizar(juros),
        multa=_quantizar(multa),
        total=total,
        data_vencimento=vencimento,
        fundamento_legal="Lei 9.718/1998 art. 2º-3º; IN RFB 1.911/2019",
    )


# ── Helpers privados ─────────────────────────────────────────────────────────


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def _validar_valor(v: Decimal, nome: str) -> None:
    if v < _ZERO:
        raise ValueError(f"{nome} não pode ser negativo: {v}")


def _validar_trimestre(trimestre: int) -> None:
    if trimestre not in (1, 2, 3, 4):
        raise ValueError(
            f"trimestre deve ser 1, 2, 3 ou 4 (recebido {trimestre})"
        )


def _validar_competencia(competencia: date) -> None:
    if competencia.day != 1:
        raise ValueError(
            f"competencia deve ser o primeiro dia do mês "
            f"(recebido {competencia.isoformat()})"
        )


def _data_trimestre(ano: int, trimestre: int) -> date:
    """Primeiro dia do trimestre (competência canônica)."""
    mes_inicial = {1: 1, 2: 4, 3: 7, 4: 10}[trimestre]
    return date(ano, mes_inicial, 1)


def _vencimento_trimestral(ano: int, trimestre: int) -> date:
    """Último dia do mês seguinte ao encerramento do trimestre.

    Lei 9.430/1996 art. 5º: vencimento no último dia útil do mês seguinte.
    MVP: usa último dia do mês (sem ajuste para dias úteis).
    """
    mes_encerramento = trimestre * 3  # T1→3, T2→6, T3→9, T4→12
    if mes_encerramento == 12:
        mes_venc, ano_venc = 1, ano + 1
    else:
        mes_venc, ano_venc = mes_encerramento + 1, ano
    _, ultimo_dia = monthrange(ano_venc, mes_venc)
    return date(ano_venc, mes_venc, ultimo_dia)


def _vencimento_mensal(competencia: date) -> date:
    """Dia 25 do mês seguinte à competência.

    IN RFB 1.911/2019 art. 50: PIS/Cofins vencem no dia 25 do mês
    seguinte. MVP: sem ajuste para dias úteis.
    """
    if competencia.month == 12:
        return date(competencia.year + 1, 1, 25)
    return date(competencia.year, competencia.month + 1, 25)
