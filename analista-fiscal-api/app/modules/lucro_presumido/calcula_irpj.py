"""Calculadora IRPJ trimestral — Lucro Presumido.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 9.249/1995 art. 15 — percentuais de presunção por atividade.
  * Lei 9.249/1995 art. 3º §1º — alíquota IRPJ 15%.
  * Lei 9.249/1995 art. 3º §1º — adicional 10% sobre o que exceder
    R$20.000 × nº de meses do período (= R$60.000 em trimestre completo).
  * Lei 9.430/1996 art. 1º — apuração trimestral (períodos encerrados em
    31/03, 30/06, 30/09, 31/12).
  * Lei 9.430/1996 art. 64 — IRRF retido na fonte (1,5% PJ→PJ por serviços
    profissionais, art. 647 RIR/2018) deduzido do IRPJ devido no trimestre.
  * IN RFB 1.700/2017 art. 33 (consolidação).

Fórmula (v2 — Fase 1.5/1.6 do plano de remediação):

  base_presumida    = receita_bruta_trimestre × percentual_irpj_atividade
  base_total        = base_presumida + ganhos_capital + receitas_aplicacoes + outras_adicoes
  irpj_normal       = base_total × 15%
  irpj_adicional    = max(0, base_total − limite) × 10%
                      (limite = 20000 × meses_periodo; default 60000 = 3 meses)
  irpj_total_bruto  = irpj_normal + irpj_adicional           # soma raw, sem quantizar antes
  irrf_consumido    = min(irrf_a_compensar, irpj_total_bruto)
  irpj_devido       = irpj_total_bruto − irrf_consumido      # nunca negativo
  irrf_saldo_credor = irrf_a_compensar − irrf_consumido      # aproveitável próximo trimestre

Quantização: ``ROUND_HALF_EVEN`` 2 casas aplicada **uma única vez** ao
``irpj_total_bruto`` antes da subtração do IRRF — assim o resultado bate
com o PVA/DCTFWeb da Receita (que também quantiza só no fim).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "lp.irpj.trimestral.v2"

_CENTAVO = Decimal("0.01")
_ALIQ_NORMAL = Decimal("0.1500")
_ALIQ_ADICIONAL = Decimal("0.1000")
_LIMITE_MES = Decimal("20000.00")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class ResultadoIrpjLp:
    """Snapshot persistido em ``apuracao_fiscal`` (tipo='irpj')."""

    receita_bruta_trimestre: Decimal
    percentual_presuncao: Decimal
    base_presumida: Decimal
    ganhos_capital: Decimal
    receitas_aplicacoes: Decimal
    outras_adicoes: Decimal
    base_total: Decimal
    meses_periodo: int
    limite_adicional: Decimal
    irpj_normal: Decimal           # exibição (quantizado)
    irpj_adicional: Decimal        # exibição (quantizado)
    irpj_total: Decimal            # IRPJ bruto antes da dedução IRRF (quantizado)
    irrf_a_compensar: Decimal      # IRRF informado como input
    irrf_consumido: Decimal        # parte do IRRF efetivamente abatida nesse trimestre
    irrf_saldo_credor: Decimal     # excedente para próximo trimestre
    irpj_devido: Decimal           # valor final a recolher (= irpj_total - irrf_consumido)
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def calcular_irpj_trimestral(
    receita_bruta_trimestre: Decimal,
    percentual_presuncao: Decimal,
    *,
    ganhos_capital: Decimal = _ZERO,
    receitas_aplicacoes: Decimal = _ZERO,
    outras_adicoes: Decimal = _ZERO,
    meses_periodo: int = 3,
    irrf_a_compensar: Decimal = _ZERO,
) -> ResultadoIrpjLp:
    """Calcula IRPJ do trimestre com dedução de IRRF sofrido.

    Args:
        receita_bruta_trimestre: receita do trimestre (BRL).
        percentual_presuncao: vem da tabela SCD ``presuncao_lucro_presumido``
            (ex.: 0,0800 = 8%; 0,3200 = 32%).
        ganhos_capital: ganho de capital somado integral à base (não recebe
            presunção — art. 25 §1º Lei 9.430).
        receitas_aplicacoes: rendimentos financeiros — base 100%.
        outras_adicoes: ajustes/recuperações que entram integrais na base.
        meses_periodo: default 3 (trimestre cheio); 1 ou 2 para apuração
            de início de atividade.
        irrf_a_compensar: IRRF retido na fonte no trimestre (Lei 9.430 art. 64).
            Aceita também saldo credor de IRRF acumulado de trimestres
            anteriores. Não pode ser negativo. Default zero (compatibilidade
            backward com chamadores que ainda não passam o valor).

    Returns:
        ResultadoIrpjLp com ``irpj_devido`` (a recolher) + ``irrf_saldo_credor``
        (excedente para próximo trimestre).

    Raises:
        ValueError: parâmetros inválidos.
    """
    if receita_bruta_trimestre < _ZERO:
        raise ValueError(
            f"receita_bruta_trimestre não pode ser negativa: "
            f"{receita_bruta_trimestre}"
        )
    if percentual_presuncao < _ZERO or percentual_presuncao > Decimal("1"):
        raise ValueError(
            f"percentual_presuncao fora de [0, 1]: {percentual_presuncao}"
        )
    if meses_periodo < 1 or meses_periodo > 3:
        raise ValueError(
            f"meses_periodo deve estar entre 1 e 3 (recebido {meses_periodo})"
        )
    if irrf_a_compensar < _ZERO:
        raise ValueError(
            f"irrf_a_compensar não pode ser negativo: {irrf_a_compensar}"
        )
    for nome, v in (
        ("ganhos_capital", ganhos_capital),
        ("receitas_aplicacoes", receitas_aplicacoes),
        ("outras_adicoes", outras_adicoes),
    ):
        if v < _ZERO:
            raise ValueError(f"{nome} não pode ser negativo: {v}")

    base_presumida = receita_bruta_trimestre * percentual_presuncao
    base_total = (
        base_presumida + ganhos_capital + receitas_aplicacoes + outras_adicoes
    )

    irpj_normal = base_total * _ALIQ_NORMAL
    limite = _LIMITE_MES * Decimal(meses_periodo)
    excedente = base_total - limite
    irpj_adicional = excedente * _ALIQ_ADICIONAL if excedente > _ZERO else _ZERO

    # ── Quantização única no fim (Fase 1.6) ──────────────────────────────
    # Quantizar antes da soma e depois de novo introduzia desvio de R$0,01-0,02
    # vs cálculo do PVA da Receita. A soma vai do raw e quantiza só uma vez.
    irpj_total_raw = irpj_normal + irpj_adicional
    irpj_total = _quantizar(irpj_total_raw)

    # ── IRRF a compensar (Fase 1.5) ──────────────────────────────────────
    # Lei 9.430/1996 art. 64: IRRF sofrido é deduzido do IRPJ devido.
    irrf_a_compensar_q = _quantizar(irrf_a_compensar)
    irrf_consumido = min(irrf_a_compensar_q, irpj_total)
    irrf_saldo_credor = irrf_a_compensar_q - irrf_consumido
    irpj_devido = irpj_total - irrf_consumido

    return ResultadoIrpjLp(
        receita_bruta_trimestre=receita_bruta_trimestre,
        percentual_presuncao=percentual_presuncao,
        base_presumida=_quantizar(base_presumida),
        ganhos_capital=ganhos_capital,
        receitas_aplicacoes=receitas_aplicacoes,
        outras_adicoes=outras_adicoes,
        base_total=_quantizar(base_total),
        meses_periodo=meses_periodo,
        limite_adicional=limite,
        irpj_normal=_quantizar(irpj_normal),
        irpj_adicional=_quantizar(irpj_adicional),
        irpj_total=irpj_total,
        irrf_a_compensar=irrf_a_compensar_q,
        irrf_consumido=irrf_consumido,
        irrf_saldo_credor=irrf_saldo_credor,
        irpj_devido=irpj_devido,
    )
