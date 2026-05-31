"""Orquestrador de sugestões de otimização (Sprint 15 PR2).

Camada 1 (determinística). Funções puras, zero I/O — receivem snapshots
carregados pelo service e devolvem a lista de sugestões aplicáveis.

Heurísticas cobertas nesta sprint:

  1. ``fator_r_migrar_anexo`` — Simples Nacional com Anexo III/V. Compara DAS
     mensal nos dois anexos e sugere migração se ``deve_migrar`` + economia
     anual ≥ R$ 100 (limiar para não inundar a UI com ruído).
  2. ``parcelar_das_atrasado`` — apurações DAS calculadas e não pagas há
     mais de 30 dias da data de vencimento. Sugestão de parcelamento Lei
     10.522/2002 (até 60 parcelas). Não calcula valor — é nudge informativo.

Heurísticas futuras (pendências conscientes):
  * ``distribuicao_isenta_subutilizada`` (Sprint 15 PR3 — depende de cálculo
    do limite isento a partir da DRE).
  * ``regime_lp_vs_sn`` (sprint futura — exige modelo carga LP completo).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

import structlog

from app.modules.advisor.simula_fator_r import SimulacaoFatorR

log = structlog.get_logger(__name__)

ALGORITMO_VERSAO = "advisor.sugestoes.v1"

_ECONOMIA_MINIMA_RELEVANTE = Decimal("100.00")  # R$ 100/ano — abaixo disso é ruído
_DIAS_DESDE_VENCIMENTO_ATRASO = 30  # apuração não-paga > 30d ⇒ atrasada


@dataclass(frozen=True, slots=True)
class SugestaoCalculada:
    """Item da lista de sugestões — pronto para serializar no endpoint."""

    codigo: str  # snake_case estável (UI usa para ordenar/agrupar)
    titulo: str  # curto pt-BR (até ~80 chars)
    descricao: str  # ~150-300 chars, frase completa
    severidade: str  # "informativa" | "media" | "alta"
    economia_anual_estimada: Decimal | None  # None se não-monetária
    fonte_norma: str
    detalhes: dict[str, str] = field(default_factory=dict)
    observacao_estimativa: str = ""
    algoritmo_versao: str = ALGORITMO_VERSAO


@dataclass(frozen=True, slots=True)
class ApuracaoPendente:
    """Apuração calculada mas não paga — input da heurística de parcelamento."""

    apuracao_id: str  # UUID como str (frozen-friendly)
    tipo: str  # "das", "irpj", ...
    competencia: date
    valor: Decimal
    vencimento: date
    status: str  # "calculado" | "transmitido"


# ── Heurística 1: Fator R ───────────────────────────────────────────────────


def sugerir_migracao_fator_r(
    simulacao: SimulacaoFatorR | None,
) -> SugestaoCalculada | None:
    """Gera sugestão de migração Anexo III↔V quando aplicável.

    Retorna ``None`` quando:
      * Simulação não foi calculada (empresa fora do Simples ou anexo ≠ III/V).
      * Anexo atual já é o recomendado.
      * Economia anual estimada é menor que ``_ECONOMIA_MINIMA_RELEVANTE``.
    """
    if simulacao is None or not simulacao.deve_migrar:
        return None
    economia = simulacao.economia_anual_estimada
    if abs(economia) < _ECONOMIA_MINIMA_RELEVANTE:
        return None

    if simulacao.anexo_recomendado == "III":
        titulo = "Aumente sua folha e migre para o Anexo III"
        descricao = (
            f"Sua razão folha/receita está em {(simulacao.fator_r_atual * 100):.2f}%. "
            f"Atingindo 28% (Fator R), sua atividade passa do Anexo V para o III. "
            f"Faltam R$ {simulacao.gap_folha_anual:,.2f} de folha anual para cruzar "
            f"o boundary; a economia estimada com a migração é R$ "
            f"{economia:,.2f}/ano."
        )
        severidade = "alta" if economia >= Decimal("1000.00") else "media"
    else:
        titulo = "Sua atividade está mais barata no Anexo V"
        descricao = (
            f"Sua razão folha/receita está em {(simulacao.fator_r_atual * 100):.2f}%. "
            f"Reduzindo a folha abaixo de 28%, sua atividade migra para o Anexo V, "
            f"que neste momento tem alíquota efetiva menor — economia estimada "
            f"R$ {economia:,.2f}/ano. Verifique impactos trabalhistas antes."
        )
        severidade = "informativa"

    return SugestaoCalculada(
        codigo="fator_r_migrar_anexo_" + simulacao.anexo_recomendado.lower(),
        titulo=titulo,
        descricao=descricao,
        severidade=severidade,
        economia_anual_estimada=economia,
        fonte_norma=simulacao.fonte_norma,
        detalhes={
            "fator_r_atual": str(simulacao.fator_r_atual),
            "fator_r_limiar": str(simulacao.fator_r_limiar),
            "anexo_atual_efetivo": simulacao.anexo_atual_efetivo,
            "anexo_recomendado": simulacao.anexo_recomendado,
            "das_anexo_iii_mensal": str(simulacao.das_anexo_iii_mensal),
            "das_anexo_v_mensal": str(simulacao.das_anexo_v_mensal),
            "gap_folha_anual": str(simulacao.gap_folha_anual),
            "competencia_referencia": simulacao.competencia_referencia.isoformat(),
        },
        observacao_estimativa=simulacao.observacao_estimativa,
    )


# ── Heurística 2: Parcelamento de DAS atrasado ──────────────────────────────


def sugerir_parcelamento_atrasado(
    pendentes: list[ApuracaoPendente],
    *,
    hoje: date,
) -> SugestaoCalculada | None:
    """Sugere parcelamento Lei 10.522/2002 quando há DAS atrasado > 30 dias.

    Soma o valor total dos atrasados (não-pagos passados do vencimento +
    30 dias) e devolve uma única sugestão consolidada.
    """
    limite = hoje - timedelta(days=_DIAS_DESDE_VENCIMENTO_ATRASO)
    atrasadas = [
        p for p in pendentes
        if p.tipo == "das" and p.vencimento < limite
    ]
    if not atrasadas:
        return None

    total = sum((p.valor for p in atrasadas), start=Decimal("0"))
    competencias = sorted({p.competencia.isoformat() for p in atrasadas})

    return SugestaoCalculada(
        codigo="parcelar_das_atrasado",
        titulo="Parcele o DAS em atraso (até 60 parcelas)",
        descricao=(
            f"Você tem {len(atrasadas)} apuração(ões) de DAS em atraso somando "
            f"R$ {total:,.2f}. A Lei 10.522/2002 permite parcelar débitos da RFB "
            f"em até 60 vezes, com parcela mínima de R$ 200. Considere parcelar "
            f"para evitar inscrição em dívida ativa e CND irregular."
        ),
        severidade="alta",
        economia_anual_estimada=None,  # não-monetária; é mitigação
        fonte_norma="Lei 10.522/2002 art. 10",
        detalhes={
            "quantidade_atrasadas": str(len(atrasadas)),
            "valor_total_atrasado": str(total),
            "competencias": ",".join(competencias),
            "dias_corte": str(_DIAS_DESDE_VENCIMENTO_ATRASO),
        },
        observacao_estimativa=(
            "Valor agregado das competências de DAS calculadas há mais de 30 dias "
            "do vencimento e não confirmadas como pagas. Conferir antes de transmitir."
        ),
    )


# ── Orquestrador (recebe snapshots; sem I/O) ────────────────────────────────


@dataclass(frozen=True, slots=True)
class InsumosSugestoes:
    """Tudo que o orquestrador precisa, carregado pelo service uma vez."""

    simulacao_fator_r: SimulacaoFatorR | None
    apuracoes_pendentes: list[ApuracaoPendente]
    competencia_referencia: date


def calcular_sugestoes(insumos: InsumosSugestoes) -> list[SugestaoCalculada]:
    """Aplica todas as heurísticas e devolve a lista filtrada (ordem estável).

    Ordem: severidade (alta → media → informativa), depois código alfabético.
    """
    candidatas: list[SugestaoCalculada | None] = [
        sugerir_migracao_fator_r(insumos.simulacao_fator_r),
        sugerir_parcelamento_atrasado(
            insumos.apuracoes_pendentes, hoje=insumos.competencia_referencia
        ),
    ]
    aplicaveis = [s for s in candidatas if s is not None]

    ordem_sev = {"alta": 0, "media": 1, "informativa": 2}
    aplicaveis.sort(key=lambda s: (ordem_sev.get(s.severidade, 9), s.codigo))
    return aplicaveis
