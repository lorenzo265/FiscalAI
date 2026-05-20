"""Serviço do assistente fiscal com IA — orquestra RAG + LLM + validação de citação.

Pipeline (§8 do Plano):
  1. Detectar se pergunta é out-of-scope → encaminhar marketplace
  2. Buscar contexto RAG no grafo de memória (pgvector)
  3. Chamar LLMClient com fontes como contexto
  4. Validar resposta (re-check determinístico) → rejeitar se alucinar
  5. Segunda tentativa se falhar → resposta padrão "vou verificar com seu contador"
"""
from __future__ import annotations

import hashlib
from decimal import Decimal
from uuid import UUID

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.assistente.schemas import CitacaoOut, PerguntaIn, RespostaOut
from app.modules.memoria.service import buscar_contexto_rag, contexto_para_fontes
from app.shared.llm.citacao import (
    RESPOSTA_PADRAO_VERIFICAR,
    detectar_out_of_scope,
    validar_resposta,
)
from app.shared.llm.client import FonteFato, LLMClient, LLMRequest, LLMResponse
from app.shared.llm.prompts import get_prompt

log = structlog.get_logger(__name__)

_MAX_TENTATIVAS = 2


async def responder_pergunta(
    empresa_id: UUID,
    payload: PerguntaIn,
    session: AsyncSession,
    llm_client: LLMClient,
    settings: Settings,
    http_client: httpx.AsyncClient | None = None,
) -> RespostaOut:
    """Ponto central do assistente fiscal."""

    # ── 1. Detectar out-of-scope ─────────────────────────────────────────────
    eh_out, categoria = detectar_out_of_scope(payload.pergunta)
    if eh_out:
        log.info(
            "assistente.out_of_scope",
            empresa_id=str(empresa_id),
            categoria=categoria,
        )
        return RespostaOut(
            resposta=(
                f"Essa pergunta está fora do escopo do Analista Fiscal. "
                f"Para '{payload.pergunta}', recomendo consultar um especialista em "
                f"{_categoria_pt(categoria)}. Posso conectar você com um profissional parceiro."
            ),
            citacoes=[],
            encaminhar_marketplace=True,
            categoria_marketplace=categoria,
            provider_usado="deterministic",
            tokens_input=0,
            tokens_output=0,
            tokens_cached=0,
            custo_usd=Decimal("0"),
            latencia_ms=0,
            empresa_id=empresa_id,
        )

    # ── 2. Buscar contexto RAG ────────────────────────────────────────────────
    try:
        contexto = await buscar_contexto_rag(
            empresa_id=empresa_id,
            pergunta=payload.pergunta,
            session=session,
            ollama_url=settings.OLLAMA_URL,
            k=5,
            http_client=http_client,
        )
        fontes_rag = contexto_para_fontes(contexto)
    except Exception as exc:
        log.warning("assistente.rag_falhou", erro=str(exc))
        fontes_rag = []

    fontes = [
        FonteFato(id=f["id"], tipo=f["tipo"], payload=f["payload"])
        for f in fontes_rag
    ]

    # ── 3 + 4. Chamar LLM e validar (até _MAX_TENTATIVAS) ───────────────────
    cache_key = hashlib.sha256(
        f"{empresa_id}:{payload.pergunta}".encode()
    ).hexdigest()[:32]

    contexto_str = (
        "\n".join(f"[{f.id}] {f.payload}" for f in fontes)
        if fontes else "Nenhum fato específico disponível no grafo."
    )

    prompt = (
        f"Pergunta: {payload.pergunta}\n\n"
        f"Fatos disponíveis da empresa:\n{contexto_str}\n\n"
        f"Responda de forma clara e objetiva, citando os IDs dos fatos usados."
    )
    if payload.contexto_adicional:
        prompt += f"\n\nContexto adicional: {payload.contexto_adicional}"

    system_prompt = get_prompt("assistente_resposta_v1")
    request = LLMRequest(
        prompt=prompt,
        system=system_prompt.texto,
        cache_key=cache_key,
        cache_ttl_seconds=300,  # 5 min — fatos do grafo expiram rápido
        fontes_disponiveis=fontes,
        contem_pii=payload.contem_pii,
    )

    llm_resp: LLMResponse | None = None
    for tentativa in range(1, _MAX_TENTATIVAS + 1):
        try:
            llm_resp = await llm_client.chamar(request)
        except Exception as exc:
            log.warning(
                "assistente.llm_erro",
                empresa_id=str(empresa_id),
                tentativa=tentativa,
                erro=str(exc),
            )
            break

        if validar_resposta(llm_resp, fontes):
            break

        log.warning(
            "assistente.citacao_invalida",
            empresa_id=str(empresa_id),
            tentativa=tentativa,
        )
        llm_resp = None  # força nova tentativa

    # Falha total → resposta padrão (nunca propagar alucinação)
    if llm_resp is None:
        return RespostaOut(
            resposta=RESPOSTA_PADRAO_VERIFICAR,
            citacoes=[],
            encaminhar_marketplace=False,
            categoria_marketplace=None,
            provider_usado="fallback",
            tokens_input=0,
            tokens_output=0,
            tokens_cached=0,
            custo_usd=Decimal("0"),
            latencia_ms=0,
            empresa_id=empresa_id,
        )

    return RespostaOut(
        resposta=llm_resp.texto,
        citacoes=[
            CitacaoOut(fato_id=c.fato_id, trecho_citado=c.trecho_citado)
            for c in llm_resp.citacoes
        ],
        encaminhar_marketplace=llm_resp.encaminhar_marketplace,
        categoria_marketplace=llm_resp.categoria_marketplace,
        provider_usado=str(llm_resp.provider),
        tokens_input=llm_resp.tokens_input,
        tokens_output=llm_resp.tokens_output,
        tokens_cached=llm_resp.tokens_cached,
        custo_usd=llm_resp.custo_usd,
        latencia_ms=llm_resp.latencia_ms,
        empresa_id=empresa_id,
    )


def _categoria_pt(categoria: str | None) -> str:
    mapa = {
        "contencioso_fiscal": "contencioso fiscal (advogado tributarista)",
        "societario": "questões societárias (advogado empresarial)",
        "planejamento_tributario": "planejamento tributário (contador especialista)",
        "operacoes_complexas": "operações fiscais complexas (despachante/contador especialista)",
    }
    return mapa.get(categoria or "", "questões especializadas")
