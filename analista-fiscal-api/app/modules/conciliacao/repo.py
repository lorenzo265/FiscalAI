"""Repositório de conciliacao_match + queries auxiliares."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import desc, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import (
    ConciliacaoMatch,
    DocumentoFiscal,
    TransacaoBancaria,
)


class ConciliacaoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def listar_transacoes_nao_conciliadas(
        self,
        empresa_id: UUID,
        *,
        desde: date | None,
        ate: date | None,
    ) -> list[TransacaoBancaria]:
        """Transações da empresa que ainda não têm match AUTO/SUGERIDA/MANUAL.

        Considera transação "já conciliada" se existe match não-rejeitado para ela.
        """
        # Subquery: ids de transações que já têm match ativo
        sub = (
            select(ConciliacaoMatch.transacao_id)
            .where(
                ConciliacaoMatch.empresa_id == empresa_id,
                ConciliacaoMatch.tipo.in_(["AUTO", "SUGERIDA", "MANUAL"]),
            )
            .scalar_subquery()
        )

        stmt = select(TransacaoBancaria).where(
            TransacaoBancaria.empresa_id == empresa_id,
            TransacaoBancaria.status == "CONFIRMED",
            not_(TransacaoBancaria.id.in_(sub)),
        )
        if desde is not None:
            stmt = stmt.where(TransacaoBancaria.data_transacao >= desde)
        if ate is not None:
            stmt = stmt.where(TransacaoBancaria.data_transacao <= ate)
        stmt = stmt.order_by(TransacaoBancaria.data_transacao)
        return list((await self._s.execute(stmt)).scalars().all())

    async def listar_documentos_candidatos(
        self,
        empresa_id: UUID,
        *,
        desde: date | None,
        ate: date | None,
    ) -> list[DocumentoFiscal]:
        """NFs da empresa dentro da janela ±15 dias do range pedido.

        Permite folga: uma transação de 30/04 ainda pode casar com NF de 25/04
        sem ampliar o range manualmente.
        """
        stmt = select(DocumentoFiscal).where(
            DocumentoFiscal.empresa_id == empresa_id,
            DocumentoFiscal.status != "cancelada",
        )
        if desde is not None:
            from datetime import timedelta

            stmt = stmt.where(
                DocumentoFiscal.emitida_em >= datetime.combine(
                    desde - timedelta(days=15), datetime.min.time()
                )
            )
        if ate is not None:
            from datetime import timedelta

            stmt = stmt.where(
                DocumentoFiscal.emitida_em <= datetime.combine(
                    ate + timedelta(days=15), datetime.max.time()
                )
            )
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar_match(
        self,
        *,
        tenant_id: UUID,
        empresa_id: UUID,
        transacao_id: UUID,
        documento_fiscal_id: UUID,
        confianca: int,
        tipo: str,
        algoritmo_versao: str,
        score_breakdown: list[str],
    ) -> ConciliacaoMatch | None:
        """Cria match novo; retorna None se já existe par."""
        existente = await self.por_par(transacao_id, documento_fiscal_id)
        if existente is not None:
            return None
        match = ConciliacaoMatch(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            transacao_id=transacao_id,
            documento_fiscal_id=documento_fiscal_id,
            confianca=confianca,
            tipo=tipo,
            algoritmo_versao=algoritmo_versao,
            score_breakdown_json={"versao": algoritmo_versao, "criterios": score_breakdown},
        )
        self._s.add(match)
        await self._s.flush()
        return match

    async def por_par(
        self, transacao_id: UUID, documento_fiscal_id: UUID
    ) -> ConciliacaoMatch | None:
        stmt = select(ConciliacaoMatch).where(
            ConciliacaoMatch.transacao_id == transacao_id,
            ConciliacaoMatch.documento_fiscal_id == documento_fiscal_id,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def por_id(self, match_id: UUID) -> ConciliacaoMatch | None:
        stmt = select(ConciliacaoMatch).where(ConciliacaoMatch.id == match_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(
        self, empresa_id: UUID, *, tipo: str | None = None
    ) -> list[tuple[ConciliacaoMatch, TransacaoBancaria, DocumentoFiscal]]:
        """Listagem enriquecida (join com transação + NF) para UI."""
        stmt = (
            select(ConciliacaoMatch, TransacaoBancaria, DocumentoFiscal)
            .join(
                TransacaoBancaria,
                TransacaoBancaria.id == ConciliacaoMatch.transacao_id,
            )
            .join(
                DocumentoFiscal,
                DocumentoFiscal.id == ConciliacaoMatch.documento_fiscal_id,
            )
            .where(ConciliacaoMatch.empresa_id == empresa_id)
        )
        if tipo is not None:
            stmt = stmt.where(ConciliacaoMatch.tipo == tipo)
        stmt = stmt.order_by(desc(ConciliacaoMatch.criado_em))
        result = await self._s.execute(stmt)
        # C416 suprimido na linha: converte Row→tuple explicitamente (list()
        # manteria Row e divergiria do tipo de retorno anotado).
        return [(m, t, d) for m, t, d in result.all()]  # noqa: C416

    async def marcar_confirmado(
        self,
        match: ConciliacaoMatch,
        *,
        usuario_id: UUID,
        agora: datetime,
    ) -> None:
        match.tipo = "MANUAL"  # confirmação humana vira MANUAL
        match.confirmado_em = agora
        match.confirmado_por_usuario_id = usuario_id
        await self._s.flush()

    async def marcar_rejeitado(
        self,
        match: ConciliacaoMatch,
        *,
        usuario_id: UUID,
        agora: datetime,
    ) -> None:
        match.tipo = "REJEITADA"
        match.rejeitado_em = agora
        match.rejeitado_por_usuario_id = usuario_id
        await self._s.flush()
