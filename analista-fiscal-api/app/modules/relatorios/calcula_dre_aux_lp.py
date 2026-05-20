"""DRE auxiliar trimestral Lucro Presumido — reconciliação fiscal × contábil.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * IN RFB 1.700/2017 — apuração trimestral LP (IRPJ + CSLL).
  * Lei 9.430/1996 art. 1º — períodos de apuração trimestrais.
  * Lei 9.249/1995 art. 15 + art. 20 — presunção.
  * IN RFB 2.005/2021 — DCTFWeb (declaração que consome estes dados).

Objetivo: dar ao contador (e ao dono) uma visão única do trimestre cruzando:

  * Apurações fiscais já calculadas (Sprint 11 — IRPJ/CSLL trimestrais
    + PIS/Cofins mensais agregados + ICMS mensal agregado).
  * DRE contábil do mesmo trimestre (Sprint 12 PR1).

E mostrar:
  * Total de tributos do trimestre por categoria.
  * Receita bruta contábil vs. receita usada nas apurações fiscais —
    diferença flagra:
      a) lançamento contábil esquecido (DRE < Fiscal),
      b) apuração incompleta (Fiscal < DRE).
  * Carga tributária efetiva = Σ tributos / Receita Bruta contábil.

Inputs (caller monta a partir de ``apuracao_fiscal`` + ``ResultadoDre``).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "dre_aux_lp.v1"

_CENTAVO = Decimal("0.01")
_ALIQ_PRECISAO = Decimal("0.0001")
_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class ApuracaoFiscalInput:
    """Resumo de uma linha de apuracao_fiscal (Sprint 11 PR1/PR2) no trimestre."""

    tipo: str            # 'irpj' | 'csll' | 'pis' | 'cofins' | 'icms' | 'iss'
    valor: Decimal       # tributo apurado
    base_calculo: Decimal | None = None   # receita usada (presumida ou bruta)


@dataclass(frozen=True, slots=True)
class EntradaDreAuxLp:
    ano: int
    trimestre: int       # 1..4
    receita_bruta_contabil: Decimal
    receita_liquida_contabil: Decimal
    lucro_liquido_contabil: Decimal
    apuracoes: list[ApuracaoFiscalInput]


@dataclass(frozen=True, slots=True)
class LinhaTributo:
    tipo: str
    valor: Decimal
    base_calculo: Decimal | None


@dataclass(frozen=True, slots=True)
class ResultadoDreAuxLp:
    """Snapshot persistido em ``relatorio_gerado.payload`` (tipo='dre_aux_lp')."""

    ano: int
    trimestre: int
    receita_bruta_contabil: Decimal
    receita_liquida_contabil: Decimal
    lucro_liquido_contabil: Decimal
    # Detalhamento por tributo
    tributos: tuple[LinhaTributo, ...]
    # Subtotais
    total_irpj: Decimal
    total_csll: Decimal
    total_pis: Decimal
    total_cofins: Decimal
    total_icms: Decimal
    total_iss: Decimal
    total_tributos: Decimal
    # Reconciliação
    base_irpj: Decimal           # base apurada usada para IRPJ
    base_csll: Decimal           # idem CSLL
    base_pis_cofins: Decimal     # base de PIS+Cofins (receita bruta − exclusões)
    diferenca_receita: Decimal   # contabil − fiscal (PIS+Cofins base)
    # Métricas
    carga_tributaria_efetiva: Decimal | None  # total_tributos / receita_bruta
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def _quantizar_aliq(v: Decimal) -> Decimal:
    return v.quantize(_ALIQ_PRECISAO, rounding=ROUND_HALF_EVEN)


def calcular_dre_aux_lp(entrada: EntradaDreAuxLp) -> ResultadoDreAuxLp:
    """Consolida o trimestre LP cruzando contábil × fiscal.

    Args:
        entrada: ano + trimestre + métricas contábeis + apurações fiscais
            do mesmo trimestre.

    Returns:
        ResultadoDreAuxLp.

    Raises:
        ValueError: parâmetros fora de domínio.
    """
    if entrada.trimestre < 1 or entrada.trimestre > 4:
        raise ValueError(
            f"trimestre deve estar entre 1 e 4 (recebido {entrada.trimestre})"
        )
    if entrada.receita_bruta_contabil < _ZERO:
        raise ValueError("receita_bruta_contabil não pode ser negativa")

    # Subtotais por tipo
    total_irpj = _ZERO
    total_csll = _ZERO
    total_pis = _ZERO
    total_cofins = _ZERO
    total_icms = _ZERO
    total_iss = _ZERO
    base_irpj = _ZERO
    base_csll = _ZERO
    base_pis_cofins = _ZERO

    linhas: list[LinhaTributo] = []
    for ap in entrada.apuracoes:
        linhas.append(
            LinhaTributo(
                tipo=ap.tipo,
                valor=_quantizar(ap.valor),
                base_calculo=_quantizar(ap.base_calculo) if ap.base_calculo is not None else None,
            )
        )
        if ap.tipo == "irpj":
            total_irpj += ap.valor
            if ap.base_calculo is not None:
                base_irpj += ap.base_calculo
        elif ap.tipo == "csll":
            total_csll += ap.valor
            if ap.base_calculo is not None:
                base_csll += ap.base_calculo
        elif ap.tipo == "pis":
            total_pis += ap.valor
            if ap.base_calculo is not None:
                base_pis_cofins += ap.base_calculo
        elif ap.tipo == "cofins":
            total_cofins += ap.valor
            # base PIS == base Cofins, não somar de novo
        elif ap.tipo == "icms":
            total_icms += ap.valor
        elif ap.tipo == "iss":
            total_iss += ap.valor

    total_tributos = (
        total_irpj + total_csll + total_pis + total_cofins
        + total_icms + total_iss
    )

    # Reconciliação: base PIS+Cofins é receita bruta menos exclusões legais —
    # em LP sem grandes exclusões, deveria bater com receita contábil bruta.
    diferenca_receita = entrada.receita_bruta_contabil - base_pis_cofins

    carga = (
        _quantizar_aliq(total_tributos / entrada.receita_bruta_contabil)
        if entrada.receita_bruta_contabil != _ZERO else None
    )

    return ResultadoDreAuxLp(
        ano=entrada.ano,
        trimestre=entrada.trimestre,
        receita_bruta_contabil=_quantizar(entrada.receita_bruta_contabil),
        receita_liquida_contabil=_quantizar(entrada.receita_liquida_contabil),
        lucro_liquido_contabil=_quantizar(entrada.lucro_liquido_contabil),
        tributos=tuple(linhas),
        total_irpj=_quantizar(total_irpj),
        total_csll=_quantizar(total_csll),
        total_pis=_quantizar(total_pis),
        total_cofins=_quantizar(total_cofins),
        total_icms=_quantizar(total_icms),
        total_iss=_quantizar(total_iss),
        total_tributos=_quantizar(total_tributos),
        base_irpj=_quantizar(base_irpj),
        base_csll=_quantizar(base_csll),
        base_pis_cofins=_quantizar(base_pis_cofins),
        diferenca_receita=_quantizar(diferenca_receita),
        carga_tributaria_efetiva=carga,
    )
