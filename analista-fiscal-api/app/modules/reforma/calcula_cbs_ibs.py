"""Calculadora CBS/IBS informacional — Reforma Tributária 2026+.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * LC 214/2025 art. 348 §3º — cobrança-teste 2026 (CBS 0,9% + IBS 0,1%)
  * LC 214/2025 art. 349 — CBS plena 2027+ substitui PIS+Cofins
  * LC 214/2025 art. 124 — ICMS+ISS extintos em 2033
  * LC 214/2025 art. 156-A §1º — alíquota de referência 26,5% (preliminar)

**Princípio §8.12** — toda exibição CBS/IBS é informacional/estimativa e
deve ser labelada ``"Estimativa — sujeita a regulamentação (LC 214/2025 +
PLP 68/2024 em tramitação). Não substitui apuração oficial."``

Fórmula (v1):

  valor_cbs   = base_calculo × aliquota_cbs
  valor_ibs   = base_calculo × aliquota_ibs
  valor_total = valor_cbs + valor_ibs

Quantização: ``ROUND_HALF_EVEN`` 2 casas aplicada a cada parcela
isoladamente (CBS e IBS são tributos distintos com escrituração própria).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

from app.modules.reforma.periodo_transicao import FaseReforma
from app.shared.exceptions import BaseCalculoInvalida

getcontext().prec = 28

ALGORITMO_VERSAO = "reforma.cbs-ibs.v1"

OBSERVACAO_ESTIMATIVA = (
    "Estimativa — sujeita a regulamentação (LC 214/2025 + PLP 68/2024 em "
    "tramitação). Não substitui apuração oficial."
)

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")
_UM = Decimal("1")


@dataclass(frozen=True, slots=True)
class AliquotaCBSIBS:
    """Vigência da tabela SCD ``aliquota_cbs_ibs`` resolvida para uma
    competência específica.
    """

    fase: FaseReforma
    aliquota_cbs: Decimal
    aliquota_ibs: Decimal
    valid_from: date
    valid_to: date | None
    fonte_norma: str
    algoritmo_versao: str
    observacao: str | None = None


@dataclass(frozen=True, slots=True)
class ResultadoCBSIBS:
    """Snapshot do cálculo informacional CBS/IBS."""

    base_calculo: Decimal
    aliquota_cbs: Decimal
    aliquota_ibs: Decimal
    valor_cbs: Decimal             # quantizado 0.01 ROUND_HALF_EVEN
    valor_ibs: Decimal             # quantizado 0.01 ROUND_HALF_EVEN
    valor_total: Decimal           # = valor_cbs + valor_ibs
    fase: FaseReforma
    fonte_norma: str
    observacao_estimativa: str
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def calcular_cbs_ibs(
    base_calculo: Decimal,
    aliquotas: AliquotaCBSIBS,
) -> ResultadoCBSIBS:
    """Calcula CBS e IBS informacionais sobre uma base.

    Args:
        base_calculo: valor da operação que serve de base (BRL). Deve ser
            ``>= 0`` e Decimal finito.
        aliquotas: vigência resolvida pela SCD ``aliquota_cbs_ibs``.

    Returns:
        ResultadoCBSIBS com valores quantizados (2 casas) + observação de
        estimativa preenchida.

    Raises:
        BaseCalculoInvalida: base negativa, NaN ou inf.
        ValueError: alíquota fora de [0, 1] (defeito de seed — SCD deveria
            já ter rejeitado via CHECK constraint).
    """
    # ── Validação de base ────────────────────────────────────────────────
    if not isinstance(base_calculo, Decimal):
        raise BaseCalculoInvalida(
            f"base_calculo deve ser Decimal, recebido {type(base_calculo).__name__}"
        )
    if base_calculo.is_nan() or base_calculo.is_infinite():
        raise BaseCalculoInvalida(
            f"base_calculo deve ser finita (não NaN/Infinity): {base_calculo}"
        )
    if base_calculo < _ZERO:
        raise BaseCalculoInvalida(
            f"base_calculo não pode ser negativa: {base_calculo}"
        )

    # ── Defensivo: alíquota fora de range (CHECK no DB deve impedir) ─────
    for nome, aliq in (
        ("aliquota_cbs", aliquotas.aliquota_cbs),
        ("aliquota_ibs", aliquotas.aliquota_ibs),
    ):
        if aliq < _ZERO or aliq > _UM:
            raise ValueError(f"{nome} fora de [0, 1]: {aliq}")

    valor_cbs = _quantizar(base_calculo * aliquotas.aliquota_cbs)
    valor_ibs = _quantizar(base_calculo * aliquotas.aliquota_ibs)
    valor_total = valor_cbs + valor_ibs

    return ResultadoCBSIBS(
        base_calculo=base_calculo,
        aliquota_cbs=aliquotas.aliquota_cbs,
        aliquota_ibs=aliquotas.aliquota_ibs,
        valor_cbs=valor_cbs,
        valor_ibs=valor_ibs,
        valor_total=valor_total,
        fase=aliquotas.fase,
        fonte_norma=aliquotas.fonte_norma,
        observacao_estimativa=OBSERVACAO_ESTIMATIVA,
    )
