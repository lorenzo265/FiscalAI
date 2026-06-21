"""Cálculo do IRRF mensal — empregado CLT.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 15.191/2025 — tabela progressiva mensal vigente em 2026 (faixas,
    alíquotas, parcela a deduzir, dedução por dependente R$ 189,59,
    desconto simplificado R$ 607,20 = 25% × R$ 2.428,80). Inalterada desde a
    competência maio/2025.
  * Lei 15.270/2025 (vigência 01/01/2026) — REDUTOR mensal da retenção na
    fonte. Aplicado APÓS o cálculo tradicional, sobre o RENDIMENTO TRIBUTÁVEL
    BRUTO do mês (o "salário", não a base de cálculo — confirmado nos exemplos
    oficiais da RFB), com piso 0. Ver constantes ``_REDUTOR_*`` abaixo.
  * IN RFB 1.500/2014 (consolidação) + RIR 2018 art. 700.
  * Lei 9.250/1995 art. 4º II / art. 8º II "f" — pensão alimentícia judicial
    dedutível da base de cálculo do IRRF.
  * Desconto simplificado mensal: 25% do teto da 1ª faixa da tabela progressiva
    mensal (faixa de alíquota 0% / isenção). Aplica-se o método mais benéfico
    ao contribuinte (menor IRRF).

Fórmulas:

    Método legal:
        base_irrf_legal = salario_bruto
                        − inss_empregado
                        − (dependentes × deducao_dependente_mensal)
                        − pensao_alimenticia

    Método simplificado:
        desconto_simplificado = 0,25 × base_ate_faixa_1
        base_irrf_simpl       = salario_bruto − desconto_simplificado

    Para cada base: aplica tabela progressiva → irrf = base × aliquota − parcela_deduzir
    IRRF tradicional = método com menor IRRF.

    Encontra a faixa cuja ``base_ate >= base_irrf`` (ordenadas crescentes).
    irrf = max(0, base_irrf × aliquota_faixa − parcela_deduzir_faixa)

  Faixa 1 (isenta) → aliquota=0, parcela_deduzir=0 → irrf=0 automaticamente.

    Redutor Lei 15.270/2025 (só quando ``aplicar_redutor_lei_15270=True``),
    referência = ``salario_bruto`` (rendimento tributável bruto):
        ref ≤ 5.000,00            → IRRF efetivo = 0,00 (isenção efetiva)
        5.000,01 ≤ ref ≤ 7.350,00 → redutor = max(0, 978,62 − 0,133145 × ref)
                                     IRRF final = max(0, irrf_tradicional − redutor)
        ref > 7.350,00            → tabela cheia (sem redutor)

Quantização: ``ROUND_HALF_EVEN`` 2 casas no resultado final.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from typing import Literal

getcontext().prec = 28

# v3: redutor mensal da Lei 15.270/2025 (vigência 01/01/2026) somado ao motor
# de tabela progressiva da Lei 15.191/2025. v2 = só progressiva (Lei 14.848/2024).
ALGORITMO_VERSAO = "irrf.mensal.v3"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")
_DESCONTO_SIMPLIFICADO_PCT = Decimal("0.25")

# ── Redutor mensal da retenção — Lei 15.270/2025, vigência 01/01/2026 ───────
# Incide sobre o RENDIMENTO TRIBUTÁVEL BRUTO do mês (o "salário"), não sobre a
# base de cálculo — texto literal da RFB: "se utiliza nessa tabela de redução o
# valor do salário, e não o da base de cálculo". Aplicado APÓS o IRRF
# tradicional (método mais benéfico), com piso 0. Coeficientes oficiais:
_REDUTOR_PISO_ISENCAO = Decimal("5000.00")   # ≤ este valor → IRRF efetivo 0,00
_REDUTOR_TETO = Decimal("7350.00")           # acima deste valor → tabela cheia
_REDUTOR_LINEAR_LEI_15270 = Decimal("978.62")  # termo constante da fórmula
_REDUTOR_COEF = Decimal("0.133145")            # coeficiente angular da fórmula


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
    irrf: Decimal  # valor a reter (BRL, 2 casas) — JÁ líquido do redutor
    metodo: Literal["legal", "simplificado"]  # qual método foi aplicado
    # ── Redutor Lei 15.270/2025 (vigência 01/01/2026) — auditável ──────────
    irrf_tradicional: Decimal = _ZERO  # IRRF antes do redutor (tabela cheia)
    redutor_lei_15270: Decimal = _ZERO  # valor abatido (0 se não aplicável)
    algoritmo_versao: str = ALGORITMO_VERSAO


def calcular_irrf_mensal(
    salario_bruto: Decimal,
    inss_empregado: Decimal,
    dependentes: int,
    faixas: list[FaixaIrrf],
    pensao_alimenticia: Decimal = _ZERO,
    *,
    aplicar_redutor_lei_15270: bool = False,
) -> ResultadoIrrf:
    """Calcula o IRRF mensal a reter.

    Aplica ambos os métodos (legal e simplificado) e devolve o mais benéfico
    (menor IRRF). O campo ``metodo`` indica qual foi aplicado. Quando
    ``aplicar_redutor_lei_15270=True`` (competências ≥ 01/01/2026), o redutor
    da Lei 15.270/2025 é subtraído do IRRF tradicional (piso 0).

    Args:
        salario_bruto: rendimento tributável bruto do mês. Também é a
                referência do redutor da Lei 15.270/2025 (o "salário", não a
                base de cálculo — texto literal da RFB).
        inss_empregado: INSS já retido (dedutível da base — IN RFB 1.500 art. 52).
        dependentes: número de dependentes para fins de IRRF.
        faixas: 5 faixas vigentes na competência. Vêm de ``tabela_irrf_faixa``
                filtrada por vigência. Todas compartilham a mesma
                ``deducao_dependente`` (uniforme na legislação atual).
        pensao_alimenticia: pensão alimentícia judicial paga (Lei 9.250/1995
                art. 4º II / art. 8º II "f"). Dedutível da base do IRRF pelo
                método legal. Default=0 (backward-compatible).
        aplicar_redutor_lei_15270: aplica o redutor mensal da Lei 15.270/2025
                APÓS o cálculo tradicional. O caller (service) decide com base
                na competência (vigência 01/01/2026). Default=False
                (backward-compatible — competências anteriores não têm redutor).

    Returns:
        ResultadoIrrf com base, faixa, valor (já líquido do redutor) e método
        aplicado. ``irrf_tradicional`` e ``redutor_lei_15270`` expõem o
        detalhe auditável do abatimento.

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
        irrf_tradicional = irrf_simpl
        faixa_obj = faixa_simpl
        base_final = base_simpl
    else:
        metodo = "legal"
        irrf_tradicional = irrf_legal
        faixa_obj = faixa_legal
        base_final = base_legal

    # ── Redutor mensal — Lei 15.270/2025 (vigência 01/01/2026) ─────────────
    # Aplicado APÓS o IRRF tradicional, sobre o RENDIMENTO TRIBUTÁVEL BRUTO
    # (= salario_bruto, "o salário, não a base de cálculo" — RFB), piso 0.
    redutor = _ZERO
    if aplicar_redutor_lei_15270:
        if salario_bruto <= _REDUTOR_PISO_ISENCAO:
            # Isenção efetiva: o redutor zera o IRRF tradicional inteiro.
            redutor = irrf_tradicional
        elif salario_bruto <= _REDUTOR_TETO:
            redutor_bruto = (
                _REDUTOR_LINEAR_LEI_15270 - _REDUTOR_COEF * salario_bruto
            )
            if redutor_bruto < _ZERO:
                redutor_bruto = _ZERO
            redutor = redutor_bruto.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
            # O abatimento nunca excede o próprio imposto apurado (piso 0).
            if redutor > irrf_tradicional:
                redutor = irrf_tradicional
        # salario_bruto > _REDUTOR_TETO → tabela cheia, redutor permanece 0.

    irrf_final = irrf_tradicional - redutor
    if irrf_final < _ZERO:
        irrf_final = _ZERO

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
        irrf_tradicional=irrf_tradicional,
        redutor_lei_15270=redutor,
    )


def _encontrar_faixa(base: Decimal, faixas: list[FaixaIrrf]) -> FaixaIrrf:
    for f in faixas:
        if base <= f.base_ate:
            return f
    return faixas[-1]
