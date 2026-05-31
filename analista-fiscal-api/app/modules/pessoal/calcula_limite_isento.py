"""Cálculo do `limite_isento_apurado` automático (Sprint 19.7 PR1 #15).

Camada 1 (determinística). Funções puras — sem I/O.

Fundamento legal:
  * Lei 9.249/1995 art. 10 — limite contábil pra isenção de IRRF na
    distribuição de lucros ao sócio PF.
  * RIR/2018 art. 238 — empresas com escrituração contábil completa
    usam o lucro líquido contábil; sem escrituração, usam a presunção
    do regime menos os impostos pagos no período.

Estratégia:

  * **Lucro Presumido (LP):** ``receita_periodo × presunção_irpj_cnae``
    menos IRPJ + CSLL + PIS + COFINS pagos no período. Reusa
    ``presuncao_lucro_presumido`` SCD (Sprint 11 PR1).

  * **Simples Nacional (SN):** ``receita_periodo × presunção_anexo``
    menos DAS recolhido. Presunção segue Anexo I/II (comércio/indústria
    = 8% IRPJ + 12% CSLL ≈ 20% lucro contábil estimado) ou Anexo III/V
    (serviços = 32% lucro). Fórmula é aproximação — caso edge fica para
    contador no painel.

  * **Lucro Real (LR):** out-of-scope MVP (PlanoBackend §1.1).

ALGORITMO_VERSAO bump em qualquer mudança que altere o resultado.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

ALGORITMO_VERSAO = "limite_isento.v1"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class LimiteIsentoCalculado:
    """Snapshot do cálculo — passível de auditoria (todos os inputs)."""

    limite_isento: Decimal  # max(0, lucro_estimado - impostos)
    lucro_estimado: Decimal  # receita × presunção (antes de impostos)
    impostos_total: Decimal  # IRPJ+CSLL+PIS+COFINS (LP) ou DAS (SN)
    receita_periodo: Decimal
    presuncao_aplicada: Decimal  # fração 0..1 (ex.: 0.32 = 32%)
    base_calculo: str  # 'lucro_presumido_cnae' | 'simples_anexo'
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def calcular_limite_isento_lucro_presumido(
    *,
    receita_periodo: Decimal,
    presuncao_irpj: Decimal,
    irpj_pago: Decimal,
    csll_pago: Decimal,
    pis_pago: Decimal,
    cofins_pago: Decimal,
) -> LimiteIsentoCalculado:
    """LP: ``limite = receita × presunção - (IRPJ + CSLL + PIS + COFINS)``.

    Args:
        receita_periodo: receita bruta acumulada no período (mês/trimestre).
        presuncao_irpj: fração 0..1 da presunção IRPJ da
            ``presuncao_lucro_presumido`` SCD para o CNAE da empresa.
        irpj_pago/csll_pago/pis_pago/cofins_pago: tributos efetivamente
            pagos no período (das apurações da Sprint 11 PR1).

    Returns:
        ``LimiteIsentoCalculado`` com fórmula auditável.

    Raises:
        ValueError: input negativo ou presunção fora de [0, 1].
    """
    if receita_periodo < _ZERO:
        raise ValueError(f"receita_periodo negativa: {receita_periodo}")
    if not (_ZERO <= presuncao_irpj <= Decimal("1")):
        raise ValueError(
            f"presuncao_irpj fora de [0, 1]: {presuncao_irpj}"
        )
    for nome, val in (
        ("irpj_pago", irpj_pago),
        ("csll_pago", csll_pago),
        ("pis_pago", pis_pago),
        ("cofins_pago", cofins_pago),
    ):
        if val < _ZERO:
            raise ValueError(f"{nome} negativo: {val}")

    lucro_estimado = receita_periodo * presuncao_irpj
    impostos_total = irpj_pago + csll_pago + pis_pago + cofins_pago
    limite = max(_ZERO, lucro_estimado - impostos_total)

    return LimiteIsentoCalculado(
        limite_isento=_quantizar(limite),
        lucro_estimado=_quantizar(lucro_estimado),
        impostos_total=_quantizar(impostos_total),
        receita_periodo=_quantizar(receita_periodo),
        presuncao_aplicada=presuncao_irpj,
        base_calculo="lucro_presumido_cnae",
    )


# Presunção estimada por Anexo SN — média de IRPJ+CSLL ponderada pelos
# pisos da tabela. Aproximação suficiente para o cálculo do limite
# isento; valor exato dependeria de pre-classificar a atividade dentro
# do anexo (raramente vale o esforço — admin pode override no painel).
_PRESUNCAO_POR_ANEXO_SN: dict[str, Decimal] = {
    "I": Decimal("0.20"),    # Comércio: 8% IRPJ + 12% CSLL ≈ 20%
    "II": Decimal("0.20"),   # Indústria
    "III": Decimal("0.32"),  # Serviços comuns
    "IV": Decimal("0.32"),   # Construção civil
    "V": Decimal("0.32"),    # Serviços técnicos
}


def calcular_limite_isento_simples_nacional(
    *,
    receita_periodo: Decimal,
    anexo: str,
    das_pago_periodo: Decimal,
) -> LimiteIsentoCalculado:
    """SN: ``limite = receita × presunção_anexo - DAS pago``.

    Aproximação conservadora — admin pode override no painel se conhecer
    margem real da empresa. Anexo desconhecido = 32% (caso mais comum
    em PME — serviços).

    Args:
        receita_periodo: RBT do período em análise (mês ou ano).
        anexo: 'I', 'II', 'III', 'IV' ou 'V' (LC 123/2006).
        das_pago_periodo: DAS efetivamente recolhido no período
            (somatório de ``apuracao_fiscal.output_jsonb.valor`` das
            apurações 'das' da empresa).

    Raises:
        ValueError: receita ou DAS negativos; anexo inválido vai pra 32%.
    """
    if receita_periodo < _ZERO:
        raise ValueError(f"receita_periodo negativa: {receita_periodo}")
    if das_pago_periodo < _ZERO:
        raise ValueError(f"das_pago_periodo negativo: {das_pago_periodo}")

    presuncao = _PRESUNCAO_POR_ANEXO_SN.get(anexo, Decimal("0.32"))
    lucro_estimado = receita_periodo * presuncao
    limite = max(_ZERO, lucro_estimado - das_pago_periodo)

    return LimiteIsentoCalculado(
        limite_isento=_quantizar(limite),
        lucro_estimado=_quantizar(lucro_estimado),
        impostos_total=_quantizar(das_pago_periodo),
        receita_periodo=_quantizar(receita_periodo),
        presuncao_aplicada=presuncao,
        base_calculo="simples_anexo",
    )


__all__ = [
    "ALGORITMO_VERSAO",
    "LimiteIsentoCalculado",
    "calcular_limite_isento_lucro_presumido",
    "calcular_limite_isento_simples_nacional",
]
