"""Cálculo de INSS retido do empregado — método escalonado.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Portaria Interministerial MPS/MF que reajusta a tabela anualmente
    (vigente: nº 6/2025 — quando a Portaria 2026 sair, basta inserir nova
    linha SCD na ``tabela_inss_faixa`` com ``valid_from='2026-XX-XX'``).
  * Lei 8.213/1991 + Lei 8.212/1991 (Plano de Custeio).

Método (escalonado, padrão eSocial S-1210):

  Cada faixa contribui apenas com a fatia do salário dentro do seu intervalo.
  Não confundir com método não-escalonado (alíquota efetiva única) — esse foi
  abandonado em 03/2020 pela MP 905. Para salários acima do teto (~R$ 8.157,41),
  a contribuição é capada no teto da faixa 4.

  Exemplo — salário R$ 5.000:
    7,5% ×           1518,00   = 113,85   (faixa 1)
    9,0% ×  (2793,88-1518,00)  = 114,83   (faixa 2)
   12,0% ×  (4190,83-2793,88)  = 167,63   (faixa 3)
   14,0% ×  (5000,00-4190,83)  = 113,28   (faixa 4 parcial)
                          -------
                          509,59

Quantização: somatório com 28 dígitos de precisão; arredonda só no fim,
``ROUND_HALF_EVEN`` para 2 casas (centavos).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "inss.empregado.v1"

_CENTAVO = Decimal("0.01")
_ALIQ_DISPLAY = Decimal("0.0001")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class FaixaInss:
    """Linha de ``tabela_inss_faixa`` (SCD Type 2 — vem do banco)."""

    faixa: int  # 1..4 para empregado
    valor_ate: Decimal  # limite superior inclusivo da faixa
    aliquota: Decimal  # fração: 0.0750 = 7,5%


@dataclass(frozen=True, slots=True)
class ResultadoInssEmpregado:
    """Snapshot do cálculo persistido no holerite."""

    salario_base: Decimal
    inss: Decimal  # valor a reter (BRL, 2 casas)
    aliquota_efetiva: Decimal  # inss / salario_base, 4 casas (para exibição)
    teto_aplicado: bool  # True se o salário excedeu o teto e foi capado
    algoritmo_versao: str = ALGORITMO_VERSAO


def calcular_inss_empregado(
    salario_base: Decimal,
    faixas: list[FaixaInss],
) -> ResultadoInssEmpregado:
    """Calcula o INSS retido pelo método escalonado.

    Args:
        salario_base: salário bruto do empregado (BRL, Decimal).
        faixas: 4 faixas vigentes na competência (ordenáveis por ``faixa``).
                Vêm de ``tabela_inss_faixa`` filtrada por ``tipo='empregado'``
                e ``valid_from <= competencia <= COALESCE(valid_to, ∞)``.

    Returns:
        ResultadoInssEmpregado com valor, alíquota efetiva e flag de teto.

    Raises:
        ValueError: se ``salario_base`` negativo ou ``faixas`` vazia.
    """
    if salario_base < _ZERO:
        raise ValueError(f"salario_base não pode ser negativo: {salario_base}")
    if not faixas:
        raise ValueError("faixas não pode ser vazia")

    ordenadas = sorted(faixas, key=lambda f: f.faixa)
    teto = ordenadas[-1].valor_ate
    teto_aplicado = salario_base > teto
    base = teto if teto_aplicado else salario_base

    acumulado = _ZERO
    limite_inferior = _ZERO
    inss_total = _ZERO

    for f in ordenadas:
        if base <= limite_inferior:
            break
        topo_faixa = min(base, f.valor_ate)
        fatia = topo_faixa - limite_inferior
        if fatia > _ZERO:
            inss_total += fatia * f.aliquota
        limite_inferior = f.valor_ate
        acumulado = topo_faixa

    inss = inss_total.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)

    if salario_base == _ZERO:
        aliq_efetiva = _ZERO
    else:
        aliq_efetiva = (inss / salario_base).quantize(
            _ALIQ_DISPLAY, rounding=ROUND_HALF_EVEN
        )

    return ResultadoInssEmpregado(
        salario_base=salario_base,
        inss=inss,
        aliquota_efetiva=aliq_efetiva,
        teto_aplicado=teto_aplicado,
    )
