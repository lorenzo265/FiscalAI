"""Cálculo de distribuição de lucros para sócio.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 9.249/1995 art. 10 — lucros distribuídos por PJ a sócio pessoa física
    são ISENTOS de IRRF e não integram a base do IR do beneficiário, desde
    que dentro do limite contábil (lucro líquido apurado).
  * Para empresas SEM escrituração contábil completa (regra geral para SN e
    LP que não optam por contabilidade formal): o limite isento é a presunção
    do lucro do regime menos os impostos pagos (IRPJ + CSLL + PIS + COFINS).
  * Para empresas COM escrituração contábil completa: o limite é o lucro
    líquido contábil do exercício/período (RIR/2018 art. 238).
  * Excesso ao limite: tributado como rendimento comum (faixa IRRF mensal),
    com retenção na fonte e ajuste na declaração anual (PF).
  * Lei 15.270/2025 (vigência 01/01/2026) — retenção adicional de 10% de
    IRRF na fonte sobre lucros/dividendos pagos/creditados pela PJ à PF
    residente que EXCEDAM R$ 50.000,00 no mesmo MÊS (mesmo calendário).
    Aplica-se a TODOS os regimes, inclusive Simples Nacional e MEI.
    A retenção incide sobre o TOTAL do mês (não só o excedente) quando o
    total supera R$ 50.000 ("superior a" — limite exclusivo: exatamente
    R$ 50.000,00 NÃO retém). Base vedada de qualquer dedução.
    É antecipação do IR, ajustada na DAA do sócio.
    Múltiplos pagamentos no mês: retenção devida = 10%×total_acum −
    já retido nos pagamentos anteriores do mês (piso zero).
    Preservada a isenção de lucros apurados até 2025/aprovados até
    31/12/2025 e pagos até 2028 (art. de transição da Lei 15.270/2025).

COEXISTÊNCIA DOS DOIS MECANISMOS:
  * Lei 9.249/1995 art. 10 (isenção + IRRF progressivo no excedente) e
    Lei 15.270/2025 (retenção 10% sobre o total do mês) são mecanismos
    INDEPENDENTES e cumulativos:
    - A isenção da Lei 9.249 protege o lucro dentro do limite contábil de
      entrar na tabela progressiva de rendimentos, mas NÃO afasta a retenção
      antecipada da Lei 15.270 (que incide sobre o VALOR BRUTO pago no mês).
    - ``irrf_retido`` continua sendo o IRRF progressivo sobre o excedente
      (mecanismo histórico).
    - ``retencao_dividendos_10pct`` é o novo componente da Lei 15.270/2025.
    - ``valor_liquido_socio`` = bruto − irrf_retido − retencao_dividendos_10pct.
    - Ambas as retenções são antecipações do IR do sócio (ajustadas na DAA).

Estratégia do PR3:
  * O ``limite_isento`` é INPUT — calculado externamente pelo service ou
    pelo contador (depende de base contábil/presunção da empresa, que
    pertence ao módulo ``relatorios`` da Sprint 12).
  * Algoritmo decide split isento/tributável e aplica IRRF se houver
    excedente (alíquota progressiva mensal — usa mesma tabela do CLT).

Quantização: ``ROUND_HALF_EVEN`` 2 casas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from enum import StrEnum

from app.modules.pessoal.calcula_irrf import (
    FaixaIrrf,
    ResultadoIrrf,
    calcular_irrf_mensal,
)

getcontext().prec = 28

ALGORITMO_VERSAO = "distribuicao.v3"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")

# ── Constantes legais — Lei 15.270/2025 (vigência 01/01/2026) ────────────────
# Alíquota de retenção antecipada sobre lucros/dividendos do mês.
_ALIQUOTA_RETENCAO_LEI_15270 = Decimal("0.10")  # 10% — art. 2º Lei 15.270/2025
# Limite mensal por PJ×PF: SUPERIOR A este valor dispara retenção (limite exclusivo).
_LIMITE_MENSAL_LEI_15270 = Decimal("50000.00")  # R$ 50.000,00 — art. 2º §1º


class BaseCalculoReferencia(StrEnum):
    PRESUNCAO_LP = "presuncao_lp"
    SIMPLES_DENTRO_DAS = "simples_dentro_das"
    LUCRO_CONTABIL = "lucro_contabil"
    MEI = "mei"


@dataclass(frozen=True, slots=True)
class ResultadoDistribuicao:
    """Snapshot persistido em ``distribuicao_lucros``.

    Campos da Lei 15.270/2025 (vigência 01/01/2026):
      * ``retencao_dividendos_10pct``: retenção antecipada de 10% calculada
        neste pagamento (pode ser zero se total_acumulado_mes <= 50k).
      * ``total_acumulado_mes``: total do mês após este pagamento, usado para
        auditoria e para o próximo pagamento do mesmo mês/sócio/PJ.

    ``irrf_retido`` continua sendo o IRRF progressivo sobre o excedente
    ao limite contábil (Lei 9.249/1995 art. 10). Os dois mecanismos são
    cumulativos e independentes.
    """

    valor_distribuido: Decimal
    limite_isento_apurado: Decimal
    valor_isento: Decimal
    valor_tributavel: Decimal
    base_calculo_referencia: BaseCalculoReferencia
    irrf_excedente: ResultadoIrrf | None  # None se não houver excedente
    irrf_retido: Decimal
    # ── Lei 15.270/2025 ──────────────────────────────────────────────────────
    retencao_dividendos_10pct: Decimal  # retenção deste pagamento (>= 0)
    total_acumulado_mes: Decimal        # total bruto acumulado no mês após este pgto
    # ─────────────────────────────────────────────────────────────────────────
    valor_liquido_socio: Decimal  # bruto − irrf_retido − retencao_dividendos_10pct
    algoritmo_versao: str = field(default=ALGORITMO_VERSAO)


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def _calcular_retencao_lei_15270(
    total_acumulado_mes: Decimal,
    retido_anteriormente_no_mes: Decimal,
) -> Decimal:
    """Calcula a retenção de 10% devida NESTE pagamento — Lei 15.270/2025.

    Regra: retenção = 10% × total_acum_mes − já_retido,
    mas somente quando total_acum_mes > R$ 50.000,00 (limite exclusivo).
    Piso: zero (nunca devolve ao sócio via retenção negativa).

    Args:
        total_acumulado_mes: soma de todos os pagamentos do mês para esta
            PJ×PF (incluindo o pagamento atual).
        retido_anteriormente_no_mes: total já retido via Lei 15.270 nos
            pagamentos ANTERIORES deste mês (default 0 no primeiro pagamento).

    Returns:
        Decimal quantizado em 2 casas — retenção devida neste evento.
    """
    if total_acumulado_mes <= _LIMITE_MENSAL_LEI_15270:
        # R$ 50.000 "superior a" — exatamente 50k NÃO retém.
        return _ZERO
    retencao_devida_mes = _quantizar(
        _ALIQUOTA_RETENCAO_LEI_15270 * total_acumulado_mes
    )
    retencao_neste_pgto = _quantizar(
        retencao_devida_mes - retido_anteriormente_no_mes
    )
    return max(_ZERO, retencao_neste_pgto)


def calcular_distribuicao(
    valor_distribuido: Decimal,
    limite_isento_apurado: Decimal,
    base_calculo_referencia: BaseCalculoReferencia,
    faixas_irrf: list[FaixaIrrf],
    dependentes: int,
    dividendos_ja_pagos_no_mes: Decimal = _ZERO,
    retencao_lei_15270_ja_retida_no_mes: Decimal = _ZERO,
) -> ResultadoDistribuicao:
    """Decide split isento/tributável, calcula IRRF sobre excedente e retenção
    antecipada de 10% (Lei 15.270/2025) sobre o total do mês.

    MECANISMOS COEXISTENTES (ver docstring do módulo):
      1. Lei 9.249/1995 art. 10: isenção dentro do limite contábil;
         excedente → tabela progressiva IRRF → ``irrf_retido``.
      2. Lei 15.270/2025 (vigência 01/01/2026): 10% sobre total do mês
         quando > R$ 50.000, independente de regime → ``retencao_dividendos_10pct``.

    Args:
        valor_distribuido: total bruto que será distribuído ao sócio neste
            evento.
        limite_isento_apurado: limite contábil (presunção − impostos, ou
            lucro líquido contábil) para fins de Lei 9.249/1995 art. 10.
        base_calculo_referencia: rótulo do método usado pelo serviço para
            apurar o limite — persistido para auditoria.
        faixas_irrf: tabela mensal vigente (aplicada apenas se houver
            excedente sobre o limite).
        dependentes: dependentes IRRF do sócio.
        dividendos_ja_pagos_no_mes: soma dos valores brutos distribuídos para
            esta mesma PJ×PF nos pagamentos ANTERIORES do mesmo mês calendário.
            Default 0 (primeiro pagamento do mês). Lei 15.270/2025.
        retencao_lei_15270_ja_retida_no_mes: total já retido pela Lei 15.270
            nos pagamentos anteriores do mês para esta PJ×PF. Default 0.
            Permite calcular corretamente a retenção incremental em múltiplos
            pagamentos no mês. Lei 15.270/2025.

    Returns:
        ResultadoDistribuicao.

    Raises:
        ValueError: parâmetros inválidos.
    """
    if valor_distribuido < _ZERO:
        raise ValueError(
            f"valor_distribuido não pode ser negativo: {valor_distribuido}"
        )
    if limite_isento_apurado < _ZERO:
        raise ValueError(
            f"limite_isento_apurado não pode ser negativo: {limite_isento_apurado}"
        )
    if dependentes < 0:
        raise ValueError(f"dependentes não pode ser negativo: {dependentes}")
    if dividendos_ja_pagos_no_mes < _ZERO:
        raise ValueError(
            f"dividendos_ja_pagos_no_mes não pode ser negativo: "
            f"{dividendos_ja_pagos_no_mes}"
        )
    if retencao_lei_15270_ja_retida_no_mes < _ZERO:
        raise ValueError(
            f"retencao_lei_15270_ja_retida_no_mes não pode ser negativa: "
            f"{retencao_lei_15270_ja_retida_no_mes}"
        )

    # ── Mecanismo 1: Lei 9.249/1995 — isenção + IRRF progressivo ─────────────
    valor_isento = min(valor_distribuido, limite_isento_apurado)
    # m6 FA8: quantizar valor_tributavel ANTES de passar ao IRRF.
    # Se limite_isento_apurado vier com >2 casas decimais (e.g. de
    # receita×presunção em calcula_limite_isento), a subtração produziria
    # base com casas extras → centavo divergente no IRRF. Quantizamos aqui
    # na fronteira, conforme ROUND_HALF_EVEN (padrão fiscal do sistema).
    valor_tributavel = _quantizar(valor_distribuido - valor_isento)

    if valor_tributavel == _ZERO:
        irrf_obj: ResultadoIrrf | None = None
        irrf_retido = _ZERO
    else:
        # Excedente é tratado como rendimento mensal — sem dedução de INSS
        # (já paga na fonte da empresa, distinto do tributo do sócio).
        # Valor já quantizado (2 casas) para garantir base limpa ao IRRF.
        irrf_obj = calcular_irrf_mensal(
            valor_tributavel, _ZERO, dependentes, faixas_irrf
        )
        irrf_retido = irrf_obj.irrf

    # ── Mecanismo 2: Lei 15.270/2025 — retenção antecipada 10% ───────────────
    # Incide sobre o TOTAL do mês (incluindo este pagamento), independente
    # do regime tributário da PJ ou da isenção da Lei 9.249/1995.
    # Base: valor bruto pago/creditado — vedada qualquer dedução.
    total_acumulado_mes = _quantizar(dividendos_ja_pagos_no_mes + valor_distribuido)
    retencao_10pct = _calcular_retencao_lei_15270(
        total_acumulado_mes,
        retencao_lei_15270_ja_retida_no_mes,
    )

    # ── Líquido ao sócio: bruto menos ambas as retenções ─────────────────────
    valor_liquido = _quantizar(valor_distribuido - irrf_retido - retencao_10pct)

    return ResultadoDistribuicao(
        valor_distribuido=valor_distribuido,
        limite_isento_apurado=limite_isento_apurado,
        valor_isento=_quantizar(valor_isento),
        valor_tributavel=_quantizar(valor_tributavel),
        base_calculo_referencia=base_calculo_referencia,
        irrf_excedente=irrf_obj,
        irrf_retido=irrf_retido,
        retencao_dividendos_10pct=retencao_10pct,
        total_acumulado_mes=total_acumulado_mes,
        valor_liquido_socio=valor_liquido,
    )
