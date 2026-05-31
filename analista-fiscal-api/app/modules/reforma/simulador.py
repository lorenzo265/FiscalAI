"""Simulador de impacto da Reforma Tributária (Sprint 14 PR3).

Algoritmo puro (zero I/O). Camada 1 determinística.

Recebe a **carga tributária anualizada atual** da empresa (PIS+Cofins+
ICMS+ISS), a **alíquota CBS+IBS do regime pleno 2033** (vinda da SCD), a
**receita anualizada** e o **ICMS médio mensal** (para estimar impacto
do split payment 2027 no fluxo de caixa). Devolve 3 cenários
(pessimista/realista/otimista, ±2pp em torno da alíquota de referência).

Fundamento legal:

  * LC 214/2025 art. 156-A §1º — alíquota de referência 26,5% (preliminar).
  * EC 132/2023 art. 7º — split payment retém IBS/CBS na transação Pix/
    cartão. Empresas perdem o float entre recebimento e pagamento do
    imposto (capital de giro).

**Princípio §8.12** — todo resultado carrega ``observacao_estimativa``
citando LC 214/2025 + PLP 68/2024 em tramitação. Toda saída labelada
"Estimativa — sujeita a regulamentação".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from enum import StrEnum
from uuid import UUID

from app.modules.reforma.calcula_cbs_ibs import (
    OBSERVACAO_ESTIMATIVA,
    AliquotaCBSIBS,
)
from app.modules.reforma.periodo_transicao import FaseReforma

getcontext().prec = 28

ALGORITMO_VERSAO = "reforma.simulador.v1"

# ±2pp em torno da alíquota de referência (decimal: 0,02 = 2 pontos
# percentuais). Aplicado uniformemente sobre CBS+IBS — não distinguimos
# o CBS do IBS por cenário, pois o consumidor final do simulador é a
# carga total (PMEs não otimizam um vs. outro).
_DELTA_CENARIO = Decimal("0.02")

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")
_UM = Decimal("1")

_PRAZO_PADRAO_RECOLHIMENTO_DIAS = 20  # ICMS típico: dia 20 do mês seguinte


class Cenario(StrEnum):
    """Cenários de alíquota total CBS+IBS no regime pleno."""

    PESSIMISTA = "pessimista"   # +2pp
    REALISTA = "realista"       # alíquota tabela (referência LC 214)
    OTIMISTA = "otimista"       # -2pp


@dataclass(frozen=True, slots=True)
class CargaTributariaAnualizada:
    """Soma das apurações dos últimos 12m em tributos que serão substituídos
    por CBS+IBS no regime pleno (2033).
    """

    pis: Decimal
    cofins: Decimal
    icms: Decimal
    iss: Decimal

    @property
    def total(self) -> Decimal:
        return self.pis + self.cofins + self.icms + self.iss


@dataclass(frozen=True, slots=True)
class SimulacaoCenario:
    """Projeção CBS+IBS para um cenário específico (3 cenários no total)."""

    cenario: Cenario
    aliquota_total: Decimal       # CBS+IBS aplicada no cenário
    cbs_projetada: Decimal        # quantizada 0.01
    ibs_projetada: Decimal        # quantizada 0.01
    total_projetado: Decimal      # = cbs + ibs
    delta_absoluto: Decimal       # total_projetado − carga_atual.total
    delta_percentual: Decimal     # delta / carga_atual.total (0 quando carga=0)


@dataclass(frozen=True, slots=True)
class ImpactoFluxoCaixa:
    """Estimativa de capital de giro perdido com split payment 2027.

    O split payment retém o imposto na transação financeira. Empresas que
    hoje usam o intervalo (recebimento → recolhimento ICMS) como capital
    de giro perdem esse float.

    Fórmula: ``capital_perdido ≈ media_icms_mensal × (prazo_dias / 30)``.
    """

    media_icms_mensal: Decimal
    prazo_medio_recolhimento_dias: int
    capital_giro_perdido: Decimal


@dataclass(frozen=True, slots=True)
class ResultadoSimulacao:
    """Snapshot do simulador — devolvido pelo router como SimulacaoOut."""

    empresa_id: UUID
    periodo_base: tuple[date, date]
    fase_atual: FaseReforma
    receita_anualizada: Decimal
    carga_atual: CargaTributariaAnualizada
    cenarios: list[SimulacaoCenario]       # sempre 3 — ordenados
    impacto_fluxo_caixa_2027: ImpactoFluxoCaixa
    observacao_estimativa: str             # OBRIGATÓRIO — §8.12
    fontes_norma: list[str]
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def _clamp_aliquota(v: Decimal) -> Decimal:
    """Garante alíquota efetiva em [0, 1] após aplicar delta de cenário."""
    if v < _ZERO:
        return _ZERO
    if v > _UM:
        return _UM
    return v


def _calcular_cenario(
    *,
    cenario: Cenario,
    aliquota_cbs_base: Decimal,
    aliquota_ibs_base: Decimal,
    delta: Decimal,
    receita: Decimal,
    carga_atual_total: Decimal,
) -> SimulacaoCenario:
    """Aplica delta proporcionalmente em CBS e IBS, quantiza, calcula deltas."""
    aliquota_total_base = aliquota_cbs_base + aliquota_ibs_base
    aliquota_total_cenario = _clamp_aliquota(aliquota_total_base + delta)

    # Repartição proporcional do delta entre CBS e IBS (mantém ratio do regime
    # pleno). Quando a base total é zero, atribui tudo a CBS (defesa em
    # profundidade — não deveria acontecer na seed real).
    if aliquota_total_base > _ZERO:
        ratio_cbs = aliquota_cbs_base / aliquota_total_base
        cbs_cenario = aliquota_total_cenario * ratio_cbs
        ibs_cenario = aliquota_total_cenario - cbs_cenario
    else:
        cbs_cenario = aliquota_total_cenario
        ibs_cenario = _ZERO

    cbs_projetada = _quantizar(receita * cbs_cenario)
    ibs_projetada = _quantizar(receita * ibs_cenario)
    total_projetado = cbs_projetada + ibs_projetada

    delta_absoluto = total_projetado - carga_atual_total
    if carga_atual_total > _ZERO:
        delta_percentual = (delta_absoluto / carga_atual_total).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_EVEN
        )
    else:
        delta_percentual = _ZERO

    return SimulacaoCenario(
        cenario=cenario,
        aliquota_total=aliquota_total_cenario,
        cbs_projetada=cbs_projetada,
        ibs_projetada=ibs_projetada,
        total_projetado=total_projetado,
        delta_absoluto=delta_absoluto,
        delta_percentual=delta_percentual,
    )


def projetar_impacto(
    *,
    empresa_id: UUID,
    periodo_base: tuple[date, date],
    fase_atual: FaseReforma,
    receita_anualizada: Decimal,
    carga_atual: CargaTributariaAnualizada,
    aliquota_pleno: AliquotaCBSIBS,
    icms_medio_mensal: Decimal,
    prazo_recolhimento_dias: int = _PRAZO_PADRAO_RECOLHIMENTO_DIAS,
) -> ResultadoSimulacao:
    """Projeta carga CBS+IBS no regime pleno 2033 em 3 cenários.

    Args:
        empresa_id: identificador da empresa.
        periodo_base: (inicio, fim) do período de 12m que originou a carga.
        fase_atual: fase vigente no momento da simulação (informativa).
        receita_anualizada: receita bruta do período base (BRL).
        carga_atual: soma anualizada dos tributos a substituir.
        aliquota_pleno: vigência do regime pleno (2033+) vinda da SCD —
            base para os 3 cenários (±2pp aplicado uniformemente).
        icms_medio_mensal: média mensal de ICMS recolhido — input para o
            cálculo do impacto de fluxo de caixa do split payment 2027.
        prazo_recolhimento_dias: dias entre recebimento da venda e pagamento
            do ICMS hoje (padrão 20). Maior prazo = maior impacto do split.

    Returns:
        ResultadoSimulacao com 3 cenários ordenados (pessimista, realista,
        otimista) + impacto de fluxo de caixa + observação obrigatória.

    Raises:
        ValueError: receita_anualizada < 0 ou icms_medio_mensal < 0 ou
            prazo_recolhimento_dias < 0.
    """
    if receita_anualizada < _ZERO:
        raise ValueError(
            f"receita_anualizada não pode ser negativa: {receita_anualizada}"
        )
    if icms_medio_mensal < _ZERO:
        raise ValueError(
            f"icms_medio_mensal não pode ser negativo: {icms_medio_mensal}"
        )
    if prazo_recolhimento_dias < 0:
        raise ValueError(
            f"prazo_recolhimento_dias não pode ser negativo: {prazo_recolhimento_dias}"
        )

    carga_atual_total = carga_atual.total

    cenarios = [
        _calcular_cenario(
            cenario=Cenario.PESSIMISTA,
            aliquota_cbs_base=aliquota_pleno.aliquota_cbs,
            aliquota_ibs_base=aliquota_pleno.aliquota_ibs,
            delta=_DELTA_CENARIO,
            receita=receita_anualizada,
            carga_atual_total=carga_atual_total,
        ),
        _calcular_cenario(
            cenario=Cenario.REALISTA,
            aliquota_cbs_base=aliquota_pleno.aliquota_cbs,
            aliquota_ibs_base=aliquota_pleno.aliquota_ibs,
            delta=_ZERO,
            receita=receita_anualizada,
            carga_atual_total=carga_atual_total,
        ),
        _calcular_cenario(
            cenario=Cenario.OTIMISTA,
            aliquota_cbs_base=aliquota_pleno.aliquota_cbs,
            aliquota_ibs_base=aliquota_pleno.aliquota_ibs,
            delta=-_DELTA_CENARIO,
            receita=receita_anualizada,
            carga_atual_total=carga_atual_total,
        ),
    ]

    # ── Impacto de fluxo de caixa (split payment 2027) ───────────────────
    capital_giro_perdido = _quantizar(
        icms_medio_mensal * Decimal(prazo_recolhimento_dias) / Decimal("30")
    )
    fluxo = ImpactoFluxoCaixa(
        media_icms_mensal=icms_medio_mensal,
        prazo_medio_recolhimento_dias=prazo_recolhimento_dias,
        capital_giro_perdido=capital_giro_perdido,
    )

    return ResultadoSimulacao(
        empresa_id=empresa_id,
        periodo_base=periodo_base,
        fase_atual=fase_atual,
        receita_anualizada=receita_anualizada,
        carga_atual=carga_atual,
        cenarios=cenarios,
        impacto_fluxo_caixa_2027=fluxo,
        observacao_estimativa=OBSERVACAO_ESTIMATIVA,
        fontes_norma=[
            aliquota_pleno.fonte_norma,
            "EC 132/2023 art. 7º (split payment 2027)",
        ],
    )
