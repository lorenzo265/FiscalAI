"""Calculadoras PIS e Cofins — regime cumulativo mensal (Lucro Presumido).

Camada 1 (determinística). Funções puras, zero I/O.

Fundamento legal:
  * Lei 9.715/1998 — PIS cumulativo, alíquota 0,65%.
  * Lei 9.718/1998 — Cofins cumulativo, alíquota 3%.
  * Lei 9.718/1998 art. 3º §2º — exclusões da base:
      I — vendas canceladas e descontos incondicionais concedidos;
      II — reversões de provisões e recuperações de créditos baixados;
      III — receitas de exportação não tributadas;
      IV — IPI destacado nas notas (quando empresa é contribuinte do IPI);
      V — ICMS-ST quando o vendedor é substituto tributário.

Fórmula (idêntica para PIS e Cofins, só muda alíquota):

  base_bruta = receita_bruta_mes − exclusoes_legais
  Se base_bruta < 0 (exclusões > receita — ex.: cancelamentos de meses
  anteriores ou exportações — art. 3º §2º):
    base_calculo = 0  (empresa não recolhe PIS/Cofins no mês)
    saldo_exclusao_transportar = |base_bruta|  → carryover para o próximo mês
  Senão:
    base_calculo = base_bruta
    saldo_exclusao_transportar = 0

  tributo = base_calculo × aliquota  (0,65% PIS / 3% Cofins)

Apuração mensal — recolhimento via DARF até o 25º dia útil do mês seguinte
ao da apuração (Lei 11.933/2009).

Carryover de exclusões (FA7-m3):
  Cenário legítimo: empresa exporta R$120k em janeiro e recebe apenas R$80k
  de receita interna. Exclusão legítima = R$120k > R$80k. A diferença
  (R$40k) é carreada para fevereiro como ``saldo_exclusao_transportar``
  e deve ser somada às exclusões do próximo mês pelo caller.

  Diferente do saldo credor de ICMS (originado pelo excesso de crédito
  sobre débito na apuração), aqui o transporte é de **excesso de exclusão**
  sobre a receita — a empresa já usou R$80k de exclusão este mês (zerou a
  base), e tem R$40k sobrando para usar no próximo período.

Quantização: ``ROUND_HALF_EVEN`` 2 casas.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO_PIS = "lp.pis.cumulativo.v2"
ALGORITMO_VERSAO_COFINS = "lp.cofins.cumulativo.v2"

_CENTAVO = Decimal("0.01")
_ALIQ_PIS = Decimal("0.0065")
_ALIQ_COFINS = Decimal("0.0300")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class ResultadoTributoCumulativo:
    """Snapshot persistido em ``apuracao_fiscal``.

    FA7-m3: campo ``saldo_exclusao_transportar`` expõe o excedente de
    exclusões (exclusoes > receita) que deve ser somado às exclusões do
    próximo período pelo caller (Lei 9.718/98 art. 3º §2º — carryover
    de cancelamentos/exportações de competências anteriores).
    Quando zero, não há excedente (caso normal).
    """

    receita_bruta_mes: Decimal
    exclusoes: Decimal
    base_calculo: Decimal
    aliquota: Decimal
    tributo: Decimal
    saldo_exclusao_transportar: Decimal  # FA7-m3: carryover; 0 quando normal
    algoritmo_versao: str


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def _calcular_cumulativo(
    receita_bruta_mes: Decimal,
    exclusoes: Decimal,
    aliquota: Decimal,
    algoritmo_versao: str,
) -> ResultadoTributoCumulativo:
    if receita_bruta_mes < _ZERO:
        raise ValueError(
            f"receita_bruta_mes não pode ser negativa: {receita_bruta_mes}"
        )
    if exclusoes < _ZERO:
        raise ValueError(f"exclusoes não pode ser negativa: {exclusoes}")

    # FA7-m3: exclusoes > receita é legítimo (cancelamentos de competências
    # anteriores, exportações — Lei 9.718/98 art. 3º §2º). Nesse caso:
    #   base = 0 (empresa não recolhe no mês)
    #   saldo_exclusao_transportar = excedente para o próximo período
    # Não abortar com ValueError: seria negar uma dedução legal ao contribuinte.
    base_bruta = receita_bruta_mes - exclusoes
    if base_bruta >= _ZERO:
        base = base_bruta
        saldo_exclusao_transportar = _ZERO
    else:
        base = _ZERO
        saldo_exclusao_transportar = _quantizar(-base_bruta)

    tributo = _quantizar(base * aliquota)

    return ResultadoTributoCumulativo(
        receita_bruta_mes=receita_bruta_mes,
        exclusoes=exclusoes,
        base_calculo=_quantizar(base),
        aliquota=aliquota,
        tributo=tributo,
        saldo_exclusao_transportar=saldo_exclusao_transportar,
        algoritmo_versao=algoritmo_versao,
    )


def calcular_pis_cumulativo_mensal(
    receita_bruta_mes: Decimal,
    *,
    exclusoes: Decimal = _ZERO,
) -> ResultadoTributoCumulativo:
    """PIS cumulativo — 0,65% sobre receita bruta menos exclusões legais."""
    return _calcular_cumulativo(
        receita_bruta_mes, exclusoes, _ALIQ_PIS, ALGORITMO_VERSAO_PIS
    )


def calcular_cofins_cumulativo_mensal(
    receita_bruta_mes: Decimal,
    *,
    exclusoes: Decimal = _ZERO,
) -> ResultadoTributoCumulativo:
    """Cofins cumulativo — 3,0% sobre receita bruta menos exclusões legais."""
    return _calcular_cumulativo(
        receita_bruta_mes, exclusoes, _ALIQ_COFINS, ALGORITMO_VERSAO_COFINS
    )
