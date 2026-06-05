"""Cálculo de retenções PJ→PJ (IR + CSRF) — EFD-Reinf.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 7.713/1988 art. 7º + Lei 9.064/1995 art. 6º — IRRF 1,5% sobre
    serviços profissionais prestados por PJ a outra PJ.
  * Lei 10.833/2003 art. 30 — CSRF 4,65% (PIS 0,65% + COFINS 3% + CSLL 1%)
    sobre pagamentos a PJ por serviços enumerados (limpeza, conservação,
    segurança, locação de mão de obra, advocacia, consultoria, assessoria,
    administração de bens, etc.).
  * IN RFB 459/2004 art. 1º §3º — dispensa de retenção quando o valor da
    CSRF é igual ou inferior a R$10,00 (limite passou a R$10 em 2015;
    antes era R$10 desde a Lei 10.833 — mantido em IN 1.234/2012 + 2.145/2023).
  * LC 123/2006 art. 13 §13 — Simples Nacional dispensado de sofrer
    retenção PIS/Cofins/CSLL e IRRF (regra geral; salvo se anexo IV).
    Para simplificar PR2: SN sempre dispensado.

Fórmulas:

  ir_retido     = valor_servico × 1,5%       (sempre se serviço retido)
  pis_retido    = valor_servico × 0,65%
  cofins_retido = valor_servico × 3,00%
  csll_retido   = valor_servico × 1,00%
  csrf_total    = pis_retido + cofins_retido + csll_retido

  Se csrf_total < R$10 → ZERA o CSRF (não retém PIS/Cofins/CSLL).
  IRRF (cód. 1708/5952): a retenção por documento é feita integralmente (sem
  dispensa por nota). O piso de R$10 por código de receita previsto na Lei
  9.430/1996 art. 68 §1º opera no nível de **recolhimento mensal acumulado**
  (DARF), não na retenção por documento isolado. Portanto este módulo retém
  o IRRF por nota normalmente; o controle do piso de acumulação deve ser feito
  pelo módulo de DARF ao consolidar o período (fora do escopo desta função).

Tomador no Simples Nacional → dispensado de toda retenção (IR + CSRF).
Tomador em LP/LR → retém integralmente.

Quantização: ``ROUND_HALF_EVEN`` 2 casas em cada componente.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from enum import StrEnum

getcontext().prec = 28

ALGORITMO_VERSAO = "reinf.retencao_pj.v1"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")
_ALIQ_IR = Decimal("0.0150")
_ALIQ_PIS = Decimal("0.0065")
_ALIQ_COFINS = Decimal("0.0300")
_ALIQ_CSLL = Decimal("0.0100")
_LIMITE_CSRF_DISPENSA = Decimal("10.00")


class RegimeTomador(StrEnum):
    SIMPLES_NACIONAL = "simples_nacional"
    MEI = "mei"
    LUCRO_PRESUMIDO = "lucro_presumido"
    LUCRO_REAL = "lucro_real"


@dataclass(frozen=True, slots=True)
class ResultadoRetencaoPj:
    """Snapshot persistido em ``efd_reinf_evento`` (tipo='R-4020')."""

    valor_servico: Decimal
    regime_tomador: RegimeTomador
    sujeito_a_retencao: bool
    ir_retido: Decimal
    pis_retido: Decimal
    cofins_retido: Decimal
    csll_retido: Decimal
    csrf_total: Decimal       # pis+cofins+csll, antes da dispensa
    csrf_dispensado: bool     # True quando csrf_total < R$10 e foi zerado
    valor_liquido_pago: Decimal
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def calcular_retencao_pj_pj(
    valor_servico: Decimal,
    regime_tomador: RegimeTomador,
) -> ResultadoRetencaoPj:
    """Calcula a retenção PJ→PJ aplicável a um pagamento por serviço.

    Args:
        valor_servico: valor bruto do serviço (BRL).
        regime_tomador: regime do contratante (não do prestador).

    Returns:
        ResultadoRetencaoPj.

    Raises:
        ValueError: ``valor_servico`` negativo.
    """
    if valor_servico < _ZERO:
        raise ValueError(f"valor_servico não pode ser negativo: {valor_servico}")

    # Tomador no SN/MEI é dispensado de toda retenção (LC 123/2006 art. 13 §13).
    sujeito = regime_tomador not in (
        RegimeTomador.SIMPLES_NACIONAL, RegimeTomador.MEI,
    )
    if not sujeito:
        return ResultadoRetencaoPj(
            valor_servico=valor_servico,
            regime_tomador=regime_tomador,
            sujeito_a_retencao=False,
            ir_retido=_ZERO,
            pis_retido=_ZERO,
            cofins_retido=_ZERO,
            csll_retido=_ZERO,
            csrf_total=_ZERO,
            csrf_dispensado=False,
            valor_liquido_pago=_quantizar(valor_servico),
        )

    ir = _quantizar(valor_servico * _ALIQ_IR)
    pis = _quantizar(valor_servico * _ALIQ_PIS)
    cofins = _quantizar(valor_servico * _ALIQ_COFINS)
    csll = _quantizar(valor_servico * _ALIQ_CSLL)
    csrf_total = pis + cofins + csll

    if csrf_total < _LIMITE_CSRF_DISPENSA:
        pis = _ZERO
        cofins = _ZERO
        csll = _ZERO
        csrf_dispensado = True
    else:
        csrf_dispensado = False

    csrf_efetivo = pis + cofins + csll
    liquido = _quantizar(valor_servico - ir - csrf_efetivo)

    return ResultadoRetencaoPj(
        valor_servico=valor_servico,
        regime_tomador=regime_tomador,
        sujeito_a_retencao=True,
        ir_retido=ir,
        pis_retido=pis,
        cofins_retido=cofins,
        csll_retido=csll,
        csrf_total=csrf_total,
        csrf_dispensado=csrf_dispensado,
        valor_liquido_pago=liquido,
    )
