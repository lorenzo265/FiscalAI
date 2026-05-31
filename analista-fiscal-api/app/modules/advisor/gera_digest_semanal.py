"""Geração do weekly digest — função pura (Sprint 15 PR3).

Camada 1 (determinística). Recebe snapshots carregados pelo service e
estrutura o conteúdo do digest. **Não chama LLM, não toca DB, não envia
WhatsApp.** A redação do texto fica em ``redigir_texto`` (template ou LLM).

Princípios cravados:

  * §8.5 — toda entrada no digest carrega ``fonte_id`` (UUID/competência)
    que aponta para um fato real no banco — citação obrigatória.
  * §8.8 — sem LLM aqui (estruturação 100% determinística).
  * §8.12 — sugestões e anomalias herdam ``observacao_estimativa`` da camada
    anterior (PRs 1-2).

Estrutura do digest:

  1. Saudação (com nome curto da empresa).
  2. Apurações fechadas na semana (até 3).
  3. Anomalias abertas mais severas (até 3 — alta > media > baixa).
  4. Próximos vencimentos (até 3 — data crescente, próximos 14 dias).
  5. Sugestões de otimização (até 2 — severidade decrescente).
  6. Call-to-action (link para o dashboard).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

ALGORITMO_VERSAO = "advisor.digest.v1"

_MAX_APURACOES = 3
_MAX_ANOMALIAS = 3
_MAX_VENCIMENTOS = 3
_MAX_SUGESTOES = 2
_JANELA_VENCIMENTO_DIAS = 14

_ORDEM_SEVERIDADE = {"alta": 0, "media": 1, "baixa": 2, "informativa": 3}


# ── Inputs do algoritmo (dataclasses puros — caller monta a partir de ORM) ──


@dataclass(frozen=True, slots=True)
class ApuracaoResumo:
    """Snapshot de uma apuração fechada na semana."""

    apuracao_id: str  # UUID como str
    tipo: str  # "das", "irpj", "pis", ...
    competencia: date
    valor: Decimal


@dataclass(frozen=True, slots=True)
class AnomaliaResumo:
    """Snapshot de uma anomalia ativa não-dispensada."""

    anomalia_id: str
    tipo: str
    competencia: date
    severidade: str  # "baixa" | "media" | "alta"
    mensagem: str
    valor_observado: Decimal
    valor_esperado: Decimal


@dataclass(frozen=True, slots=True)
class VencimentoResumo:
    """Snapshot de uma obrigação fiscal próxima (AgendaItem)."""

    agenda_item_id: str
    titulo: str
    data_vencimento: date
    tipo_obrigacao: str


@dataclass(frozen=True, slots=True)
class SugestaoResumo:
    """Snapshot reduzido de SugestaoCalculada (PR2) para o digest."""

    codigo: str
    titulo: str
    descricao: str
    severidade: str
    economia_anual_estimada: Decimal | None


# ── Output do algoritmo ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FonteCitavel:
    """Fato referenciável pelo redator — espelha ``FonteFato`` do LLM client."""

    id: str  # "apuracao:<uuid>" | "anomalia:<uuid>" | "agenda:<uuid>" | ...
    tipo: str
    payload: str  # texto livre que deve aparecer literalmente se citado
    data: str | None = None


@dataclass(frozen=True, slots=True)
class DigestEstruturado:
    """Snapshot estruturado pronto para redação (template ou LLM)."""

    empresa_nome: str
    empresa_apelido_curto: str  # primeiro nome p/ saudação informal
    semana_iso: str  # "2026-W21"
    periodo_inicio: date
    periodo_fim: date
    apuracoes: list[ApuracaoResumo]
    anomalias: list[AnomaliaResumo]
    proximos_vencimentos: list[VencimentoResumo]
    sugestoes: list[SugestaoResumo]
    fontes: list[FonteCitavel] = field(default_factory=list)
    algoritmo_versao: str = ALGORITMO_VERSAO


# ── Função pura ─────────────────────────────────────────────────────────────


def gerar_digest_estruturado(
    *,
    empresa_nome: str,
    apuracoes_semana: list[ApuracaoResumo],
    anomalias_abertas: list[AnomaliaResumo],
    agenda_proximos: list[VencimentoResumo],
    sugestoes: list[SugestaoResumo],
    referencia: date,
) -> DigestEstruturado:
    """Filtra/prioriza/limita as entradas e monta o digest pronto para redação.

    Args:
        empresa_nome: razão social ou fantasia (apelido curto deriva).
        apuracoes_semana: apurações fechadas no período (caller já filtra
            por janela; este algoritmo só ordena e corta os top-N).
        anomalias_abertas: ativas + não-dispensadas (PR1).
        agenda_proximos: itens da agenda fiscal (filtragem por janela feita
            aqui — apenas próximos 14 dias).
        sugestoes: sugestões PR2 (já ordenadas por severidade).
        referencia: data que define a semana ISO e a janela de vencimentos.

    Returns:
        ``DigestEstruturado`` imutável com top-N + lista de ``fontes``
        para citação obrigatória.
    """
    iso_year, iso_week, _ = referencia.isocalendar()
    semana_iso = f"{iso_year:04d}-W{iso_week:02d}"
    periodo_inicio = referencia - timedelta(days=referencia.weekday())
    periodo_fim = periodo_inicio + timedelta(days=6)

    apuracoes_top = sorted(
        apuracoes_semana, key=lambda a: a.competencia, reverse=True
    )[:_MAX_APURACOES]

    anomalias_top = sorted(
        anomalias_abertas,
        key=lambda a: (
            _ORDEM_SEVERIDADE.get(a.severidade, 9),
            -a.competencia.toordinal(),
        ),
    )[:_MAX_ANOMALIAS]

    horizonte = referencia + timedelta(days=_JANELA_VENCIMENTO_DIAS)
    vencimentos_top = sorted(
        (
            v for v in agenda_proximos
            if referencia <= v.data_vencimento <= horizonte
        ),
        key=lambda v: v.data_vencimento,
    )[:_MAX_VENCIMENTOS]

    sugestoes_top = sugestoes[:_MAX_SUGESTOES]

    fontes = _montar_fontes(
        apuracoes_top, anomalias_top, vencimentos_top, sugestoes_top
    )

    return DigestEstruturado(
        empresa_nome=empresa_nome,
        empresa_apelido_curto=_apelido_curto(empresa_nome),
        semana_iso=semana_iso,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        apuracoes=apuracoes_top,
        anomalias=anomalias_top,
        proximos_vencimentos=vencimentos_top,
        sugestoes=sugestoes_top,
        fontes=fontes,
    )


# ── Helpers ─────────────────────────────────────────────────────────────────


def _apelido_curto(empresa_nome: str) -> str:
    """Extrai primeiro identificador para saudação informal.

    Razão social tipo "ACME COMERCIO LTDA" → "ACME". Mantém capitalização
    original (sem title-case para preservar siglas tipo "DDS Tecnologia").
    """
    sufixos_remover = {"LTDA", "S.A.", "S/A", "ME", "EPP", "EIRELI", "MEI"}
    palavras = empresa_nome.strip().split()
    filtradas = [p for p in palavras if p.upper().rstrip(".,") not in sufixos_remover]
    if not filtradas:
        return empresa_nome.strip()
    return filtradas[0]


def _montar_fontes(
    apuracoes: list[ApuracaoResumo],
    anomalias: list[AnomaliaResumo],
    vencimentos: list[VencimentoResumo],
    sugestoes: list[SugestaoResumo],
) -> list[FonteCitavel]:
    """Constrói lista de fontes citáveis (§8.5) — payload contém valores
    monetários e datas LITERALMENTE como aparecem no texto, para o
    ``validar_resposta`` do LLM aceitar.
    """
    fontes: list[FonteCitavel] = []
    for ap in apuracoes:
        fontes.append(
            FonteCitavel(
                id=f"apuracao:{ap.apuracao_id}",
                tipo="apuracao_fiscal",
                payload=(
                    f"{ap.tipo.upper()} competência {ap.competencia.isoformat()}: "
                    f"R$ {ap.valor:,.2f}"
                ),
                data=ap.competencia.isoformat(),
            )
        )
    for an in anomalias:
        fontes.append(
            FonteCitavel(
                id=f"anomalia:{an.anomalia_id}",
                tipo="anomalia_fiscal",
                payload=an.mensagem,
                data=an.competencia.isoformat(),
            )
        )
    for v in vencimentos:
        fontes.append(
            FonteCitavel(
                id=f"agenda:{v.agenda_item_id}",
                tipo="agenda_item",
                payload=f"{v.titulo} vence em {v.data_vencimento.isoformat()}",
                data=v.data_vencimento.isoformat(),
            )
        )
    for s in sugestoes:
        economia = (
            f" Economia estimada R$ {s.economia_anual_estimada:,.2f}/ano."
            if s.economia_anual_estimada is not None
            else ""
        )
        fontes.append(
            FonteCitavel(
                id=f"sugestao:{s.codigo}",
                tipo="sugestao_otimizacao",
                payload=f"{s.titulo}.{economia}",
            )
        )
    return fontes
