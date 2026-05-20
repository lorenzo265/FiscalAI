"""Service DET (Sprint 11 PR3)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.det.repo import MensagemDetRepo
from app.modules.det.schemas import RegistrarMensagemDetIn
from app.modules.empresa.repo import EmpresaRepo
from app.shared.db.models import MensagemDet
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    MensagemDetJaExiste,
)

log = structlog.get_logger(__name__)
_TZ_BR = ZoneInfo("America/Sao_Paulo")


class DetService:
    async def registrar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: RegistrarMensagemDetIn,
    ) -> MensagemDet:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        if await MensagemDetRepo(session).buscar_por_id_externo(
            empresa_id, payload.id_externo_det
        ):
            raise MensagemDetJaExiste(
                f"Mensagem DET id_externo={payload.id_externo_det!r} já registrada"
            )

        mensagem = MensagemDet(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            id_externo_det=payload.id_externo_det,
            assunto=payload.assunto,
            corpo=payload.corpo,
            origem=payload.origem,
            recebida_em=payload.recebida_em,
        )
        try:
            await MensagemDetRepo(session).criar(mensagem)
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise MensagemDetJaExiste(
                f"Mensagem DET id_externo={payload.id_externo_det!r} já registrada"
            ) from exc
        await session.refresh(mensagem)

        log.info(
            "det.mensagem.criada",
            empresa_id=str(empresa_id),
            id_externo=payload.id_externo_det,
            assunto=payload.assunto[:60],
        )
        return mensagem

    async def marcar_lida(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        mensagem_id: UUID,
    ) -> MensagemDet | None:
        repo = MensagemDetRepo(session)
        # Lookup direto pelo id (RLS já filtra tenant)
        from sqlalchemy import select

        stmt = select(MensagemDet).where(
            MensagemDet.id == mensagem_id,
            MensagemDet.empresa_id == empresa_id,
        )
        mensagem = (await session.execute(stmt)).scalar_one_or_none()
        if mensagem is None:
            return None
        if mensagem.lida_em is not None:
            return mensagem
        await repo.marcar_lida(mensagem, datetime.now(tz=_TZ_BR))
        await session.commit()
        await session.refresh(mensagem)
        log.info(
            "det.mensagem.lida",
            empresa_id=str(empresa_id),
            mensagem_id=str(mensagem_id),
        )
        return mensagem
