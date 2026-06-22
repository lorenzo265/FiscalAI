"""Repositorio async do modulo LGPD (Marco 3)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import LgpdSolicitacao
from app.shared.types import JsonObject


class LgpdSolicitacaoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def registrar(
        self,
        *,
        tenant_id: UUID,
        tipo: str,
        usuario_id: UUID | None,
        status: str,
        detalhes: JsonObject,
    ) -> LgpdSolicitacao:
        """Grava a trilha de auditoria da solicitacao (flush -> id disponivel)."""
        solicitacao = LgpdSolicitacao(
            tenant_id=tenant_id,
            tipo=tipo,
            usuario_id=usuario_id,
            status=status,
            detalhes=detalhes,
        )
        self._s.add(solicitacao)
        await self._s.flush()
        return solicitacao
