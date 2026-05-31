"""Redação do texto do digest — template determinístico + LLM opt-in (Sprint 15 PR3).

Camada 1 (template determinístico) é o caminho default — sempre disponível,
zero custo, zero alucinação. Camada 3 (LLM cloud) é opcional via flag
``DIGEST_LLM_HABILITADO`` em ``Settings``: gera texto mais natural mas exige
validação anti-alucinação (§8.6). Em qualquer falha de LLM (rate limit, alu-
cinação detectada, timeout), cai para o template.

Princípios cravados:

  * §8.5 — toda variável do texto vem de ``FonteCitavel`` (apuração, anomalia,
    agenda, sugestão) — citação por construção.
  * §8.6 — quando LLM redige, ``validar_resposta`` é chamada antes de retornar.
  * §8.8 — LLM nunca grava fatos; apenas redige texto a partir do
    ``DigestEstruturado`` já calculado.
  * §8.12 — observação "estimativa" mantida nas sugestões.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

import structlog

from app.modules.advisor.gera_digest_semanal import (
    DigestEstruturado,
    FonteCitavel,
)
from app.shared.llm.citacao import validar_resposta
from app.shared.llm.client import (
    FonteFato,
    LLMClient,
    LLMProvider,
    LLMRequest,
)

log = structlog.get_logger(__name__)

ALGORITMO_VERSAO_REDATOR = "advisor.digest.redator.v1"

_SYSTEM_PROMPT = (
    "Você é o Analista Fiscal, assistente proativo de PMEs brasileiras "
    "(Simples Nacional + Lucro Presumido). Redija o digest semanal em "
    "português brasileiro, tom informal e direto, máximo 150 palavras. "
    "REGRAS CRÍTICAS: "
    "1. Use APENAS os valores, datas e percentuais que aparecem nas FONTES "
    "fornecidas — literalmente, sem arredondar nem reformatar. "
    "2. Não invente sugestões, alíquotas ou prazos. "
    "3. Cite cada item via fato_id quando relevante. "
    "4. Não use markdown nem emoji. "
    "5. Termine com call-to-action curto para o app."
)


class FonteRedacao(StrEnum):
    TEMPLATE = "template"
    LLM_GEMINI = "llm_gemini_flash"
    LLM_FALLBACK = "llm_fallback"  # LLM tentado, falhou, caiu no template


@dataclass(frozen=True, slots=True)
class RedacaoResult:
    """Resultado de uma chamada de redação — pronto para persistir."""

    texto: str
    fonte: FonteRedacao
    citacoes_fato_ids: list[str]
    llm_provider: str | None = None
    custo_usd: Decimal | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    tokens_cached: int | None = None
    algoritmo_versao: str = ALGORITMO_VERSAO_REDATOR


# ── Template determinístico ─────────────────────────────────────────────────


def redigir_template(digest: DigestEstruturado) -> RedacaoResult:
    """Gera texto pt-BR ~150 palavras citando apenas dados do snapshot.

    Sempre disponível — não depende de LLM, Redis, internet. Caminho default.
    """
    linhas: list[str] = []
    citacoes: list[str] = []

    saudacao = f"Olá, {digest.empresa_apelido_curto}! Aqui está seu resumo da semana ({_fmt_periodo(digest.periodo_inicio, digest.periodo_fim)})."
    linhas.append(saudacao)

    if digest.apuracoes:
        linhas.append(_secao_apuracoes(digest, citacoes))
    if digest.anomalias:
        linhas.append(_secao_anomalias(digest, citacoes))
    if digest.proximos_vencimentos:
        linhas.append(_secao_vencimentos(digest, citacoes))
    if digest.sugestoes:
        linhas.append(_secao_sugestoes(digest, citacoes))

    if not (
        digest.apuracoes
        or digest.anomalias
        or digest.proximos_vencimentos
        or digest.sugestoes
    ):
        linhas.append(
            "Nenhuma novidade fiscal relevante nesta semana — tudo em dia."
        )

    linhas.append("Acesse o app para detalhes e tomar ações.")
    texto = " ".join(linhas)

    return RedacaoResult(
        texto=texto,
        fonte=FonteRedacao.TEMPLATE,
        citacoes_fato_ids=citacoes,
    )


def _fmt_periodo(inicio: date, fim: date) -> str:
    return f"{inicio.strftime('%d/%m')} a {fim.strftime('%d/%m')}"


def _secao_apuracoes(digest: DigestEstruturado, citacoes: list[str]) -> str:
    partes: list[str] = []
    for ap in digest.apuracoes:
        citacoes.append(f"apuracao:{ap.apuracao_id}")
        partes.append(
            f"{ap.tipo.upper()} {ap.competencia.isoformat()}: R$ {ap.valor:,.2f}"
        )
    return "Apurações fechadas: " + "; ".join(partes) + "."


def _secao_anomalias(digest: DigestEstruturado, citacoes: list[str]) -> str:
    partes: list[str] = []
    for an in digest.anomalias:
        citacoes.append(f"anomalia:{an.anomalia_id}")
        partes.append(an.mensagem)
    return "Alertas abertos: " + " ".join(partes)


def _secao_vencimentos(digest: DigestEstruturado, citacoes: list[str]) -> str:
    partes: list[str] = []
    for v in digest.proximos_vencimentos:
        citacoes.append(f"agenda:{v.agenda_item_id}")
        partes.append(f"{v.titulo} vence em {v.data_vencimento.isoformat()}")
    return "Próximos vencimentos: " + "; ".join(partes) + "."


def _secao_sugestoes(digest: DigestEstruturado, citacoes: list[str]) -> str:
    partes: list[str] = []
    for s in digest.sugestoes:
        citacoes.append(f"sugestao:{s.codigo}")
        if s.economia_anual_estimada is not None:
            partes.append(
                f"{s.titulo} (economia estimada R$ "
                f"{s.economia_anual_estimada:,.2f}/ano)"
            )
        else:
            partes.append(s.titulo)
    return "Sugestões: " + "; ".join(partes) + "."


# ── Redação via LLM (opt-in via flag) ───────────────────────────────────────


async def redigir_via_llm(
    digest: DigestEstruturado,
    *,
    llm_client: LLMClient,
    empresa_id: str,
    cache_perfil_ttl_seg: int = 3600,
) -> RedacaoResult:
    """Chama Gemini 2.5 Flash, valida citação, devolve resultado.

    Se a resposta falha em ``validar_resposta`` (regra anti-alucinação) ou
    o provider levanta erro, cai para ``redigir_template`` e marca a fonte
    como ``llm_fallback``.

    System prompt cacheado por 7 dias (Gemini); contexto empresa cacheado
    por 1h por (empresa_id, semana_iso).
    """
    fontes_fato = _fontes_para_llm(digest.fontes)
    contexto = _montar_contexto_para_llm(digest)

    request = LLMRequest(
        prompt=contexto,
        system=_SYSTEM_PROMPT,
        cache_key=f"digest:empresa:{empresa_id}:{digest.semana_iso}",
        cache_ttl_seconds=cache_perfil_ttl_seg,
        temperature=0.2,
        fontes_disponiveis=fontes_fato,
    )

    try:
        resp = await llm_client.chamar(
            request, provider=LLMProvider.GEMINI_2_5_FLASH
        )
    except Exception:
        log.exception(
            "advisor.digest.llm_falhou",
            empresa_id=empresa_id,
            semana_iso=digest.semana_iso,
        )
        fallback = redigir_template(digest)
        return RedacaoResult(
            texto=fallback.texto,
            fonte=FonteRedacao.LLM_FALLBACK,
            citacoes_fato_ids=fallback.citacoes_fato_ids,
        )

    if not validar_resposta(resp, fontes_fato):
        log.warning(
            "advisor.digest.alucinacao_detectada",
            empresa_id=empresa_id,
            semana_iso=digest.semana_iso,
        )
        fallback = redigir_template(digest)
        return RedacaoResult(
            texto=fallback.texto,
            fonte=FonteRedacao.LLM_FALLBACK,
            citacoes_fato_ids=fallback.citacoes_fato_ids,
            llm_provider=resp.provider.value,
            custo_usd=resp.custo_usd,
            tokens_input=resp.tokens_input,
            tokens_output=resp.tokens_output,
            tokens_cached=resp.tokens_cached,
        )

    return RedacaoResult(
        texto=resp.texto,
        fonte=FonteRedacao.LLM_GEMINI,
        citacoes_fato_ids=[c.fato_id for c in resp.citacoes],
        llm_provider=resp.provider.value,
        custo_usd=resp.custo_usd,
        tokens_input=resp.tokens_input,
        tokens_output=resp.tokens_output,
        tokens_cached=resp.tokens_cached,
    )


def _fontes_para_llm(fontes: list[FonteCitavel]) -> list[FonteFato]:
    return [
        FonteFato(id=f.id, tipo=f.tipo, payload=f.payload, data=f.data)
        for f in fontes
    ]


def _montar_contexto_para_llm(digest: DigestEstruturado) -> str:
    """Serializa o snapshot como bloco compacto para o prompt."""
    linhas = [
        f"Empresa: {digest.empresa_nome} (apelido: {digest.empresa_apelido_curto})",
        f"Semana: {digest.semana_iso} ({digest.periodo_inicio.isoformat()} a "
        f"{digest.periodo_fim.isoformat()})",
        "",
    ]
    if digest.apuracoes:
        linhas.append("APURACOES_FECHADAS:")
        for ap in digest.apuracoes:
            linhas.append(
                f"- [fato_id=apuracao:{ap.apuracao_id}] {ap.tipo.upper()} "
                f"competência {ap.competencia.isoformat()}: R$ {ap.valor:,.2f}"
            )
    if digest.anomalias:
        linhas.append("ANOMALIAS_ABERTAS:")
        for an in digest.anomalias:
            linhas.append(
                f"- [fato_id=anomalia:{an.anomalia_id}] severidade={an.severidade}: "
                f"{an.mensagem}"
            )
    if digest.proximos_vencimentos:
        linhas.append("VENCIMENTOS_PROXIMOS:")
        for v in digest.proximos_vencimentos:
            linhas.append(
                f"- [fato_id=agenda:{v.agenda_item_id}] {v.titulo} vence em "
                f"{v.data_vencimento.isoformat()}"
            )
    if digest.sugestoes:
        linhas.append("SUGESTOES:")
        for s in digest.sugestoes:
            economia = (
                f" Economia estimada R$ {s.economia_anual_estimada:,.2f}/ano."
                if s.economia_anual_estimada is not None
                else ""
            )
            linhas.append(
                f"- [fato_id=sugestao:{s.codigo}] {s.titulo}.{economia}"
            )
    linhas.extend([
        "",
        "Redija o digest semanal seguindo as regras do system prompt.",
    ])
    return "\n".join(linhas)
