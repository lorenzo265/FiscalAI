"""Repositório de sugestões de vigência (Sprint 19.5 PR3)."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import CursorResult, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tabelas_admin.sugestoes_schemas import StatusSugestao
from app.shared.db.models import SugestaoVigenciaTabela
from app.shared.idempotency import NS_TABELA_ADMIN

_TZ_BR = ZoneInfo("America/Sao_Paulo")


def idempotency_key_para_dou(
    *, url_dou: str, tipo_tabela: str
) -> UUID:
    """``uuid5(NS_TABELA_ADMIN, "dou|{tipo}|{url}")`` — 1 sugestão por URL+tipo.

    Worker varrer DOU 2× no mesmo mês detecta a mesma URL — devolve None
    no ON CONFLICT, sem duplicar.
    """
    return uuid5(NS_TABELA_ADMIN, f"dou|{tipo_tabela}|{url_dou}")


class SugestaoVigenciaRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(
        self, sugestao_id: UUID
    ) -> SugestaoVigenciaTabela | None:
        stmt = select(SugestaoVigenciaTabela).where(
            SugestaoVigenciaTabela.id == sugestao_id
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def por_idempotency_key(
        self, key: UUID
    ) -> SugestaoVigenciaTabela | None:
        stmt = select(SugestaoVigenciaTabela).where(
            SugestaoVigenciaTabela.idempotency_key == key
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def criar(
        self, sugestao: SugestaoVigenciaTabela
    ) -> SugestaoVigenciaTabela:
        self._s.add(sugestao)
        await self._s.flush()
        await self._s.refresh(sugestao)
        return sugestao

    async def listar(
        self,
        *,
        status: StatusSugestao | None = None,
        tipo_tabela: str | None = None,
        limite: int = 100,
    ) -> list[SugestaoVigenciaTabela]:
        stmt = select(SugestaoVigenciaTabela)
        if status is not None:
            stmt = stmt.where(SugestaoVigenciaTabela.status == status)
        if tipo_tabela is not None:
            stmt = stmt.where(
                SugestaoVigenciaTabela.tipo_tabela == tipo_tabela
            )
        stmt = stmt.order_by(SugestaoVigenciaTabela.criado_em.desc()).limit(
            limite
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def marcar_aprovada(
        self,
        sugestao: SugestaoVigenciaTabela,
        *,
        vigencia_tabela_log_id: UUID,
        aprovada_por_usuario_id: UUID | None = None,
    ) -> SugestaoVigenciaTabela:
        sugestao.status = "aprovada"
        sugestao.aprovada_em = datetime.now(_TZ_BR)
        sugestao.aprovada_por_usuario_id = aprovada_por_usuario_id
        sugestao.vigencia_tabela_log_id = vigencia_tabela_log_id
        await self._s.flush()
        return sugestao

    async def marcar_rejeitada(
        self,
        sugestao: SugestaoVigenciaTabela,
        *,
        motivo: str,
    ) -> SugestaoVigenciaTabela:
        sugestao.status = "rejeitada"
        sugestao.rejeitada_motivo = motivo
        await self._s.flush()
        return sugestao

    async def expirar_pendentes_antigas(self, *, max_dias: int = 60) -> int:
        """Marca como ``expirada`` sugestões ``pendente`` criadas há > N dias.

        Chamada pelo worker periódico. Retorna número expirado.
        """
        limite = datetime.now(_TZ_BR) - timedelta(days=max_dias)
        result = await self._s.execute(
            text(
                """
                UPDATE sugestao_vigencia_tabela
                   SET status = 'expirada'
                 WHERE status = 'pendente'
                   AND criado_em < :limite
                """
            ),
            {"limite": limite},
        )
        if isinstance(result, CursorResult):
            return result.rowcount or 0
        return 0


__all__ = ["SugestaoVigenciaRepo", "idempotency_key_para_dou"]
