"""Service de conciliação banco × NF (Sprint 7 PR3).

Fluxo do ``run``:
  1. Lista transações CONFIRMED ainda não conciliadas.
  2. Lista documentos fiscais candidatos (janela ±15 dias).
  3. Para cada par, calcula score via ``algoritmo.pontuar_match``.
  4. Persiste matches com score ≥ LIMIAR_SUGERIDA (AUTO se ≥ LIMIAR_AUTO).
  5. UNIQUE em (transacao, documento) garante idempotência —
     re-execução não duplica.

Princípio §8.2 — matches são append-only; confirmação/rejeição é UPDATE
no mesmo registro (tipo muda para MANUAL ou REJEITADA), trilha em
``confirmado_em``/``rejeitado_em``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conciliacao.algoritmo import (
    ALGORITMO_VERSAO,
    LIMIAR_AUTO,
    LIMIAR_SUGERIDA,
    DocumentoView,
    TransacaoView,
    pontuar_match,
)
from app.modules.conciliacao.repo import ConciliacaoRepo
from app.modules.conciliacao.schemas import (
    MatchOut,
    RunConciliacaoIn,
    RunConciliacaoOut,
    TipoMatch,
)
from app.modules.empresa.repo import EmpresaRepo
from app.shared.db.models import ConciliacaoMatch, DocumentoFiscal, TransacaoBancaria
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    MatchJaResolvido,
    MatchNaoEncontrado,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


class ConciliacaoService:
    async def run(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        payload: RunConciliacaoIn,
    ) -> RunConciliacaoOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        repo = ConciliacaoRepo(session)
        transacoes = await repo.listar_transacoes_nao_conciliadas(
            empresa_id, desde=payload.desde, ate=payload.ate
        )
        documentos = await repo.listar_documentos_candidatos(
            empresa_id, desde=payload.desde, ate=payload.ate
        )

        matches_auto = 0
        matches_sugeridos = 0
        pares_avaliados = 0

        for tx in transacoes:
            tx_view = _transacao_para_view(tx)
            for doc in documentos:
                doc_view = _documento_para_view(doc)
                pares_avaliados += 1
                score = pontuar_match(tx_view, doc_view)
                if score.pontos < LIMIAR_SUGERIDA:
                    continue

                tipo = (
                    TipoMatch.AUTO.value
                    if score.pontos >= LIMIAR_AUTO
                    else TipoMatch.SUGERIDA.value
                )
                criado = await repo.criar_match(
                    tenant_id=tenant_id,
                    empresa_id=empresa_id,
                    transacao_id=tx.id,
                    documento_fiscal_id=doc.id,
                    confianca=score.pontos,
                    tipo=tipo,
                    algoritmo_versao=score.versao,
                    score_breakdown=score.breakdown,
                )
                if criado is None:
                    continue
                if tipo == TipoMatch.AUTO.value:
                    matches_auto += 1
                else:
                    matches_sugeridos += 1

        await session.commit()

        log.info(
            "conciliacao.run.ok",
            empresa_id=str(empresa_id),
            transacoes=len(transacoes),
            documentos=len(documentos),
            auto=matches_auto,
            sugeridos=matches_sugeridos,
            pares_avaliados=pares_avaliados,
        )

        return RunConciliacaoOut(
            transacoes_avaliadas=len(transacoes),
            documentos_candidatos=len(documentos),
            matches_auto=matches_auto,
            matches_sugeridos=matches_sugeridos,
            pares_avaliados=pares_avaliados,
            algoritmo_versao=ALGORITMO_VERSAO,
        )

    async def confirmar(
        self,
        session: AsyncSession,
        empresa_id: uuid.UUID,
        match_id: uuid.UUID,
        usuario_id: uuid.UUID,
    ) -> MatchOut:
        repo = ConciliacaoRepo(session)
        match = await repo.por_id(match_id)
        if match is None or match.empresa_id != empresa_id:
            raise MatchNaoEncontrado(f"Match {match_id} não encontrado")
        if match.tipo == TipoMatch.REJEITADA.value:
            raise MatchJaResolvido(
                f"Match {match_id} já está REJEITADA — não pode ser confirmado"
            )
        if match.tipo == TipoMatch.MANUAL.value:
            # Idempotência: confirmar duas vezes não erra.
            return _para_out(match)

        await repo.marcar_confirmado(
            match,
            usuario_id=usuario_id,
            agora=datetime.now(_TZ_BR),
        )
        await session.commit()
        log.info(
            "conciliacao.confirmado",
            match_id=str(match_id),
            usuario_id=str(usuario_id),
        )
        return _para_out(match)

    async def rejeitar(
        self,
        session: AsyncSession,
        empresa_id: uuid.UUID,
        match_id: uuid.UUID,
        usuario_id: uuid.UUID,
    ) -> MatchOut:
        repo = ConciliacaoRepo(session)
        match = await repo.por_id(match_id)
        if match is None or match.empresa_id != empresa_id:
            raise MatchNaoEncontrado(f"Match {match_id} não encontrado")
        if match.tipo == TipoMatch.MANUAL.value:
            raise MatchJaResolvido(
                f"Match {match_id} já foi confirmado — não pode ser rejeitado"
            )
        if match.tipo == TipoMatch.REJEITADA.value:
            return _para_out(match)

        await repo.marcar_rejeitado(
            match,
            usuario_id=usuario_id,
            agora=datetime.now(_TZ_BR),
        )
        await session.commit()
        log.info(
            "conciliacao.rejeitado",
            match_id=str(match_id),
            usuario_id=str(usuario_id),
        )
        return _para_out(match)


# ── helpers puros ────────────────────────────────────────────────────────────


def _transacao_para_view(t: TransacaoBancaria) -> TransacaoView:
    return TransacaoView(
        id=t.id,
        valor=t.valor,
        tipo=t.tipo,
        data_transacao=t.data_transacao,
        descricao=t.descricao,
    )


def _documento_para_view(d: DocumentoFiscal) -> DocumentoView:
    emitida_data = d.emitida_em.date() if isinstance(d.emitida_em, datetime) else d.emitida_em
    return DocumentoView(
        id=d.id,
        direcao=d.direcao,
        valor_total=d.valor_total,
        emitida_em_data=emitida_data,
        cnpj_emitente=d.cnpj_emitente,
        cnpj_destinatario=d.cnpj_destinatario,
    )


def _para_out(m: ConciliacaoMatch) -> MatchOut:
    breakdown_raw = m.score_breakdown_json or {}
    criterios = breakdown_raw.get("criterios") if isinstance(breakdown_raw, dict) else None
    return MatchOut(
        id=m.id,
        transacao_id=m.transacao_id,
        documento_fiscal_id=m.documento_fiscal_id,
        confianca=m.confianca,
        tipo=TipoMatch(m.tipo),
        algoritmo_versao=m.algoritmo_versao,
        score_breakdown=criterios if isinstance(criterios, list) else [],
        criado_em=m.criado_em,
        confirmado_em=m.confirmado_em,
        rejeitado_em=m.rejeitado_em,
    )
