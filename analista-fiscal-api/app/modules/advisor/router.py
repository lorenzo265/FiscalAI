"""Endpoints REST — AI Advisor (Sprint 15 PR1).

Endpoints (todos sob ``/v1/empresas/{empresa_id}/advisor``):

  * ``GET  /anomalias``                — lista anomalias abertas.
  * ``POST /anomalias/{id}/dispensar`` — dispensa uma anomalia aberta.

Todos usam ``SessionDep`` (RLS multi-tenant) — cliente só vê anomalias
da própria empresa.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request

from app.modules.advisor.schemas import (
    AnomaliaOut,
    DigestOut,
    DispensarAnomaliaIn,
    FonteRedacaoOut,
    GerarDigestIn,
    ListaDigestsOut,
    ListaSugestoesOut,
    MetodoOut,
    SeveridadeOut,
    SeveridadeSugestaoOut,
    StatusDigestOut,
    SugestaoOut,
    TipoTributoOut,
)
from app.modules.advisor.service import AdvisorService
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.db.models import DigestSemanal
from app.shared.integrations.meta_whatsapp.sender import MetaWhatsAppSender

_TZ_BR = ZoneInfo("America/Sao_Paulo")

router = APIRouter(prefix="/v1", tags=["advisor"])


def _to_out(anomalia: object) -> AnomaliaOut:
    # ``anomalia`` é ``AnomaliaFiscal`` (ORM) — usar atributos diretos para
    # type-safety end-to-end sem ``model_validate(..., from_attributes=True)``
    # (que mascararia campos faltantes).
    return AnomaliaOut(
        id=anomalia.id,  # type: ignore[attr-defined]
        empresa_id=anomalia.empresa_id,  # type: ignore[attr-defined]
        tipo=TipoTributoOut(anomalia.tipo),  # type: ignore[attr-defined]
        competencia=anomalia.competencia,  # type: ignore[attr-defined]
        severidade=SeveridadeOut(anomalia.severidade),  # type: ignore[attr-defined]
        valor_observado=anomalia.valor_observado,  # type: ignore[attr-defined]
        valor_esperado=anomalia.valor_esperado,  # type: ignore[attr-defined]
        z_score=anomalia.z_score,  # type: ignore[attr-defined]
        delta_percentual=anomalia.delta_percentual,  # type: ignore[attr-defined]
        metodo=MetodoOut(anomalia.metodo),  # type: ignore[attr-defined]
        amostra_n=anomalia.amostra_n,  # type: ignore[attr-defined]
        mensagem=anomalia.mensagem,  # type: ignore[attr-defined]
        algoritmo_versao=anomalia.algoritmo_versao,  # type: ignore[attr-defined]
        detectado_em=anomalia.detectado_em,  # type: ignore[attr-defined]
        dispensada_em=anomalia.dispensada_em,  # type: ignore[attr-defined]
        dispensada_por=anomalia.dispensada_por,  # type: ignore[attr-defined]
        motivo_dispensa=anomalia.motivo_dispensa,  # type: ignore[attr-defined]
    )


@router.get(
    "/empresas/{empresa_id}/advisor/anomalias",
    response_model=list[AnomaliaOut],
    summary="Lista anomalias abertas da empresa (Sprint 15)",
)
async def listar_anomalias(
    empresa_id: UUID,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AnomaliaOut]:
    abertas = await AdvisorService(session).listar_abertas(empresa_id, limit=limit)
    return [_to_out(a) for a in abertas]


@router.post(
    "/empresas/{empresa_id}/advisor/anomalias/{anomalia_id}/dispensar",
    response_model=AnomaliaOut,
    summary="Dispensa uma anomalia aberta (idempotência via 409)",
)
async def dispensar_anomalia(
    empresa_id: UUID,
    anomalia_id: UUID,
    payload: DispensarAnomaliaIn,
    session: SessionDep,
    ctx: TenantDep,
) -> AnomaliaOut:
    dispensada = await AdvisorService(session).dispensar(
        empresa_id,
        anomalia_id,
        dispensada_por=ctx.usuario_id,
        motivo=payload.motivo,
    )
    await session.commit()
    return _to_out(dispensada)


# ── Sprint 15 PR2 — Sugestões de otimização ─────────────────────────────────


@router.get(
    "/empresas/{empresa_id}/advisor/sugestoes",
    response_model=ListaSugestoesOut,
    summary="Sugestões proativas de otimização (Fator R + parcelamento + ...)",
)
async def listar_sugestoes(
    empresa_id: UUID,
    session: SessionDep,
) -> ListaSugestoesOut:
    competencia = datetime.now(_TZ_BR).date()
    sugestoes = await AdvisorService(session).listar_sugestoes(
        empresa_id, competencia=competencia
    )
    items = [
        SugestaoOut(
            codigo=s.codigo,
            titulo=s.titulo,
            descricao=s.descricao,
            severidade=SeveridadeSugestaoOut(s.severidade),
            economia_anual_estimada=s.economia_anual_estimada,
            fonte_norma=s.fonte_norma,
            detalhes=s.detalhes,
            observacao_estimativa=s.observacao_estimativa,
            algoritmo_versao=s.algoritmo_versao,
        )
        for s in sugestoes
    ]
    return ListaSugestoesOut(
        competencia_referencia=competencia,
        total=len(items),
        sugestoes=items,
    )


# ── Sprint 15 PR3 — Weekly digest ────────────────────────────────────────────


def _digest_to_out(d: DigestSemanal) -> DigestOut:
    citacoes_raw: list[object] = (
        list(d.citacoes) if isinstance(d.citacoes, list) else []
    )
    return DigestOut(
        id=d.id,
        empresa_id=d.empresa_id,
        semana_iso=d.semana_iso,
        periodo_inicio=d.periodo_inicio,
        periodo_fim=d.periodo_fim,
        texto_redigido=d.texto_redigido,
        fonte_redacao=FonteRedacaoOut(d.fonte_redacao),
        citacoes=[str(c) for c in citacoes_raw],
        status=StatusDigestOut(d.status),
        llm_provider=d.llm_provider,
        custo_usd=d.custo_usd,
        tokens_input=d.tokens_input,
        tokens_output=d.tokens_output,
        enviado_via_whatsapp_em=d.enviado_via_whatsapp_em,
        tentativas_envio=d.tentativas_envio,
        ultimo_erro_envio=d.ultimo_erro_envio,
        enviado_template_name=d.enviado_template_name,
        algoritmo_versao=d.algoritmo_versao,
        criado_em=d.criado_em,
    )


@router.post(
    "/empresas/{empresa_id}/advisor/digest",
    response_model=DigestOut,
    summary="Gera (ou re-gera com forcar=true) o digest da semana corrente",
)
async def gerar_digest(
    empresa_id: UUID,
    payload: GerarDigestIn,
    session: SessionDep,
) -> DigestOut:
    """Geração via template determinístico (default).

    LLM ainda não exposto no endpoint REST — uso é restrito ao worker
    Celery que tem acesso ao ``LLMClient`` via DI no startup. Endpoint
    REST mantém o caminho 100% determinístico (mais rápido + sem custo).
    """
    digest = await AdvisorService(session).gerar_digest_semanal(
        empresa_id,
        forcar=payload.forcar,
        usar_llm=False,  # endpoint sempre via template (ver docstring)
    )
    await session.commit()
    return _digest_to_out(digest)


@router.get(
    "/empresas/{empresa_id}/advisor/digests",
    response_model=ListaDigestsOut,
    summary="Lista os digests semanais ativos da empresa (mais recentes primeiro)",
)
async def listar_digests(
    empresa_id: UUID,
    session: SessionDep,
) -> ListaDigestsOut:
    items = await AdvisorService(session).listar_digests(empresa_id)
    outs = [_digest_to_out(d) for d in items]
    return ListaDigestsOut(total=len(outs), digests=outs)


@router.get(
    "/empresas/{empresa_id}/advisor/digests/{digest_id}",
    response_model=DigestOut,
    summary="Detalhe de um digest específico",
)
async def obter_digest(
    empresa_id: UUID,
    digest_id: UUID,
    session: SessionDep,
) -> DigestOut:
    digest = await AdvisorService(session).obter_digest(empresa_id, digest_id)
    return _digest_to_out(digest)


@router.post(
    "/empresas/{empresa_id}/advisor/digests/{digest_id}/enviar",
    response_model=DigestOut,
    summary="Envia o digest via Meta WhatsApp utility template (Sprint 15.5)",
)
async def enviar_digest(
    empresa_id: UUID,
    digest_id: UUID,
    session: SessionDep,
    request: Request,
) -> DigestOut:
    """Envia o digest. Idempotente: re-envio com status='enviado' → 409.

    O ``MetaWhatsAppSender`` e ``Settings`` vêm do ``app.state`` montado no
    lifespan (mesmo pattern do ``whatsapp_router``).
    """
    sender = getattr(request.app.state, "whatsapp_sender", None)
    settings = getattr(request.app.state, "settings", None)
    if sender is None or settings is None:
        raise HTTPException(
            status_code=503,
            detail="WhatsApp sender não configurado no app.state",
        )
    if not isinstance(sender, MetaWhatsAppSender):
        raise HTTPException(
            status_code=503,
            detail="WhatsApp sender em estado inválido",
        )
    digest = await AdvisorService(session).enviar_digest_via_whatsapp(
        empresa_id, digest_id, sender=sender, settings=settings,
    )
    await session.commit()
    return _digest_to_out(digest)
