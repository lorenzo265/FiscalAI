"""Cálculo do IRRF mensal — empregado CLT.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 14.848/2024 — atualizou faixas vigentes.
  * MP 1.171/2024 — convertida na referida lei; ampliou isenção até R$ 2.259,20.
  * IN RFB 1.500/2014 (consolidação) + RIR 2018 art. 700.
  * Lei 9.250/1995 art. 4º II / art. 8º II "f" — pensão alimentícia judicial
    dedutível da base de cálculo do IRRF.
  * Lei 14.848/2024 art. 2º — desconto simplificado mensal: 25% do teto da
    1ª faixa da tabela progressiva mensal (faixa de alíquota 0% / isenção).
    Aplica-se o método mais benéfico ao contribuinte (menor IRRF).

Fórmulas:

    Método legal:
        base_irrf_legal = salario_bruto
                        − inss_empregado
                        − (dependentes × deducao_dependente_mensal)
                        − pensao_alimenticia

    Método simplificado (Lei 14.848/2024):
        desconto_simplificado = 0,25 × base_ate_faixa_1
        base_irrf_simpl       = salario_bruto − desconto_simplificado

    Para cada base: aplica tabela progressiva → irrf = base × aliquota − parcela_deduzir
    Resultado final: método com menor IRRF.

    Encontra a faixa cuja ``base_ate >= base_irrf`` (ordenadas crescentes).
    irrf = max(0, base_irrf × aliquota_faixa − parcela_deduzir_faixa)

  Faixa 1 (isenta) → aliquota=0, parcela_deduzir=0 → irrf=0 automaticamente.

Quantização: ``ROUND_HALF_EVEN`` 2 casas no resultado final.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from typing import Literal

getcontext().prec = 28

ALGORITMO_VERSAO = "irrf.mensal.v2"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")
_DESCONTO_SIMPLIFICADO_PCT = Decimal("0.25")


@dataclass(frozen=True, slots=True)
class FaixaIrrf:
    """Linha de ``tabela_irrf_faixa`` (SCD Type 2 — vem do banco)."""

    faixa: int  # 1..5
    base_ate: Decimal
    aliquota: Decimal  # fração: 0.0750 = 7,5%
    parcela_deduzir: Decimal
    deducao_dependente: Decimal


@dataclass(frozen=True, slots=True)
class ResultadoIrrf:
    """Snapshot do cálculo persistido no holerite."""

    salario_bruto: Decimal
    inss_empregado: Decimal
    dependentes: int
    deducao_dependentes: Decimal
    pensao_alimenticia: Decimal
    base_irrf: Decimal
    faixa: int
    aliquota: Decimal
    parcela_deduzir: Decimal
    irrf: Decimal  # valor a reter (BRL, 2 casas)
    metodo: Literal["legal", "simplificado"]  # qual método foi aplicado
    algoritmo_versao: str = ALGORITMO_VERSAO


def calcular_irrf_mensal(
    salario_bruto: Decimal,
    inss_empregado: Decimal,
    dependentes: int,
    faixas: list[FaixaIrrf],
    pensao_alimenticia: Decimal = _ZERO,
) -> ResultadoIrrf:
    """Calcula o IRRF mensal a reter.

    Aplica ambos os métodos (legal e simplificado) e devolve o mais benéfico
    (menor IRRF). O campo ``metodo`` indica qual foi aplicado.

    Args:
        salario_bruto: rendimento tributável bruto do mês.
        inss_empregado: INSS já retido (dedutível da base — IN RFB 1.500 art. 52).
        dependentes: número de dependentes para fins de IRRF.
        faixas: 5 faixas vigentes na competência. Vêm de ``tabela_irrf_faixa``
                filtrada por vigência. Todas compartilham a mesma
                ``deducao_dependente`` (uniforme na legislação atual).
        pensao_alimenticia: pensão alimentícia judicial paga (Lei 9.250/1995
                art. 4º II / art. 8º II "f"). Dedutível da base do IRRF pelo
                método legal. Default=0 (backward-compatible).

    Returns:
        ResultadoIrrf com base, faixa, valor e método aplicado.

    Raises:
        ValueError: se valores negativos ou ``faixas`` vazia.
    """
    if salario_bruto < _ZERO:
        raise ValueError(f"salario_bruto não pode ser negativo: {salario_bruto}")
    if inss_empregado < _ZERO:
        raise ValueError(f"inss_empregado não pode ser negativo: {inss_empregado}")
    if dependentes < 0:
        raise ValueError(f"dependentes não pode ser negativo: {dependentes}")
    if pensao_alimenticia < _ZERO:
        raise ValueError(
            f"pensao_alimenticia não pode ser negativa: {pensao_alimenticia}"
        )
    if not faixas:
        raise ValueError("faixas não pode ser vazia")

    ordenadas = sorted(faixas, key=lambda f: f.faixa)
    ded_por_dep = ordenadas[0].deducao_dependente
    deducao_dependentes = ded_por_dep * Decimal(dependentes)

    # ── Método legal (Lei 9.250/1995 + IN RFB 1.500) ───────────────────────
    base_legal = salario_bruto - inss_empregado - deducao_dependentes - pensao_alimenticia
    if base_legal < _ZERO:
        base_legal = _ZERO

    faixa_legal = _encontrar_faixa(base_legal, ordenadas)
    irrf_legal_bruto = base_legal * faixa_legal.aliquota - faixa_legal.parcela_deduzir
    if irrf_legal_bruto < _ZERO:
        irrf_legal_bruto = _ZERO
    irrf_legal = irrf_legal_bruto.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)

    # ── Método simplificado (Lei 14.848/2024) ─────────────────────────────
    # Desconto = 25% × teto da faixa 1 (base_ate da faixa de alíquota 0%).
    # O teto é derivado da SCD FaixaIrrf — nunca hardcoded.
    teto_faixa_1 = ordenadas[0].base_ate
    desconto_simplificado = _DESCONTO_SIMPLIFICADO_PCT * teto_faixa_1

    base_simpl = salario_bruto - desconto_simplificado
    if base_simpl < _ZERO:
        base_simpl = _ZERO

    faixa_simpl = _encontrar_faixa(base_simpl, ordenadas)
    irrf_simpl_bruto = base_simpl * faixa_simpl.aliquota - faixa_simpl.parcela_deduzir
    if irrf_simpl_bruto < _ZERO:
        irrf_simpl_bruto = _ZERO
    irrf_simpl = irrf_simpl_bruto.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)

    # ── Escolha do método mais benéfico ────────────────────────────────────
    if irrf_simpl < irrf_legal:
        metodo: Literal["legal", "simplificado"] = "simplificado"
        irrf_final = irrf_simpl
        faixa_obj = faixa_simpl
        base_final = base_simpl
    else:
        metodo = "legal"
        irrf_final = irrf_legal
        faixa_obj = faixa_legal
        base_final = base_legal

    return ResultadoIrrf(
        salario_bruto=salario_bruto,
        inss_empregado=inss_empregado,
        dependentes=dependentes,
        deducao_dependentes=deducao_dependentes.quantize(
            _CENTAVO, rounding=ROUND_HALF_EVEN
        ),
        pensao_alimenticia=pensao_alimenticia.quantize(
            _CENTAVO, rounding=ROUND_HALF_EVEN
        ),
        base_irrf=base_final.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN),
        faixa=faixa_obj.faixa,
        aliquota=faixa_obj.aliquota,
        parcela_deduzir=faixa_obj.parcela_deduzir,
        irrf=irrf_final,
        metodo=metodo,
    )


def _encontrar_faixa(base: Decimal, faixas: list[FaixaIrrf]) -> FaixaIrrf:
    for f in faixas:
        if base <= f.base_ate:
            return f
    return faixas[-1]
