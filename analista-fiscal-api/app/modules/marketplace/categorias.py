"""Catálogo de categorias do marketplace + pricing + SLA (§10.3 do Plano).

Constante pura — sem I/O, sem mutação. Versionada em ``CATALOGO_VERSAO`` para
permitir auditoria histórica de qual snapshot de preços/comissões foi aplicado
em cada consulta. Bump quando preço, comissão ou SLA mudarem.

Fonte oficial: ``docs/PlanoBackend.md`` §10.3. Preço base = limite inferior da
faixa do Plano; ``valor_consulta`` final pode ser ajustado em service caso o
contador parceiro precificar acima do mínimo (mantendo CHECK do DB).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

CATALOGO_VERSAO: str = "mkt-categorias-2026.05"


@dataclass(frozen=True, slots=True)
class Pricing:
    """Pricing + SLA de uma categoria do marketplace.

    ``preco_base`` é a referência mínima cobrada do cliente. ``comissao_pct``
    é a fatia retida pela plataforma (sempre 0–1). ``sla_aceitar`` /
    ``sla_responder`` são contados a partir da abertura da consulta — task
    Celery do PR3 expira automaticamente quando vencidos.
    """

    categoria: str
    preco_base: Decimal
    comissao_pct: Decimal
    sla_aceitar: timedelta
    sla_responder: timedelta
    descricao: str


# Tabela §10.3 — mantida em ordem de complexidade crescente. ``comissao_pct``
# decresce conforme valor sobe (incentivo para parceiros aceitarem casos
# caros). Preços expressos em reais com 2 casas (NUMERIC(14,2) no DB).
_CATALOGO: dict[str, Pricing] = {
    "consulta_rapida": Pricing(
        categoria="consulta_rapida",
        preco_base=Decimal("80.00"),
        comissao_pct=Decimal("0.30"),
        sla_aceitar=timedelta(hours=4),
        sla_responder=timedelta(hours=24),
        descricao="Consulta rápida (15 min via WhatsApp)",
    ),
    "analise_intimacao_simples": Pricing(
        categoria="analise_intimacao_simples",
        preco_base=Decimal("200.00"),
        comissao_pct=Decimal("0.25"),
        sla_aceitar=timedelta(hours=12),
        sla_responder=timedelta(hours=48),
        descricao="Análise de intimação simples",
    ),
    "analise_intimacao_complexa": Pricing(
        categoria="analise_intimacao_complexa",
        preco_base=Decimal("500.00"),
        comissao_pct=Decimal("0.25"),
        sla_aceitar=timedelta(hours=24),
        sla_responder=timedelta(hours=72),
        descricao="Análise de intimação complexa",
    ),
    "parecer_tecnico": Pricing(
        categoria="parecer_tecnico",
        preco_base=Decimal("800.00"),
        comissao_pct=Decimal("0.20"),
        sla_aceitar=timedelta(hours=24),
        sla_responder=timedelta(days=5),
        descricao="Parecer técnico escrito",
    ),
    "peticao_administrativa": Pricing(
        categoria="peticao_administrativa",
        preco_base=Decimal("1500.00"),
        comissao_pct=Decimal("0.20"),
        sla_aceitar=timedelta(hours=24),
        sla_responder=timedelta(days=7),
        descricao="Petição administrativa",
    ),
    "defesa_auto": Pricing(
        categoria="defesa_auto",
        preco_base=Decimal("2500.00"),
        comissao_pct=Decimal("0.20"),
        sla_aceitar=timedelta(hours=24),
        sla_responder=timedelta(days=14),
        descricao="Defesa de auto de infração",
    ),
    "planejamento_tributario": Pricing(
        categoria="planejamento_tributario",
        preco_base=Decimal("1500.00"),
        comissao_pct=Decimal("0.20"),
        sla_aceitar=timedelta(hours=48),
        sla_responder=timedelta(days=14),
        descricao="Planejamento tributário",
    ),
    "holding": Pricing(
        categoria="holding",
        preco_base=Decimal("3000.00"),
        comissao_pct=Decimal("0.15"),
        sla_aceitar=timedelta(hours=48),
        sla_responder=timedelta(days=30),
        descricao="Holding patrimonial",
    ),
    "sucessao": Pricing(
        categoria="sucessao",
        preco_base=Decimal("3000.00"),
        comissao_pct=Decimal("0.15"),
        sla_aceitar=timedelta(hours=48),
        sla_responder=timedelta(days=30),
        descricao="Sucessão familiar",
    ),
}


CATEGORIAS: frozenset[str] = frozenset(_CATALOGO.keys())


def pricing_para(categoria: str) -> Pricing:
    """Devolve ``Pricing`` da categoria — fail-fast em categoria desconhecida."""
    try:
        return _CATALOGO[categoria]
    except KeyError as exc:
        raise ValueError(
            f"Categoria desconhecida: {categoria!r}. Esperado uma de {sorted(CATEGORIAS)}"
        ) from exc


def comissao(categoria: str, valor_consulta: Decimal) -> Decimal:
    """Calcula a comissão da plataforma em reais, quantizada para 2 casas.

    Invariante: ``comissao <= valor_consulta`` (CHECK do DB também garante).
    """
    p = pricing_para(categoria)
    valor = (valor_consulta * p.comissao_pct).quantize(Decimal("0.01"))
    # Defesa em profundidade — arredondamento + comissão_pct=1.0 não deveria
    # ultrapassar, mas se ultrapassar, clampa.
    return min(valor, valor_consulta)


# ── Mapping categoria detectada pelo assistente → categoria do marketplace ──
#
# O ``detectar_out_of_scope`` (app/shared/llm/citacao.py) classifica em 4
# buckets amplos. O marketplace oferece categorias mais granulares. Para
# cada bucket sugerimos a categoria mais comum (cliente pode escolher outra
# manualmente). Usado pela integração assistente → matching (PR2).
_ASSISTENTE_PARA_MARKETPLACE: dict[str, str] = {
    "contencioso_fiscal": "analise_intimacao_complexa",
    "societario": "holding",
    "planejamento_tributario": "planejamento_tributario",
    "operacoes_complexas": "parecer_tecnico",
}


def categoria_do_assistente(bucket: str) -> str | None:
    """Mapa categoria do assistente → categoria do marketplace. ``None`` se desconhecido."""
    return _ASSISTENTE_PARA_MARKETPLACE.get(bucket)
