from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import ApuracaoFiscal, TabelaSimplesFaixa


class TabelaSimplesRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def faixas_vigentes(self, anexo: str, em: date) -> list[TabelaSimplesFaixa]:
        """Retorna as 6 faixas do anexo vigentes na data da competência."""
        stmt = (
            select(TabelaSimplesFaixa)
            .where(TabelaSimplesFaixa.anexo == anexo)
            .where(TabelaSimplesFaixa.valid_from <= em)
            .where(
                (TabelaSimplesFaixa.valid_to == None)  # noqa: E711
                | (TabelaSimplesFaixa.valid_to >= em)
            )
            .order_by(TabelaSimplesFaixa.faixa)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows)


class ApuracaoFiscalRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def buscar(
        self, empresa_id: UUID, competencia: date, tipo: str
    ) -> ApuracaoFiscal | None:
        stmt = select(ApuracaoFiscal).where(
            ApuracaoFiscal.empresa_id == empresa_id,
            ApuracaoFiscal.competencia == competencia,
            ApuracaoFiscal.tipo == tipo,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def listar_empresa(
        self, empresa_id: UUID, *, tipo: str | None = None
    ) -> list[ApuracaoFiscal]:
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .order_by(ApuracaoFiscal.competencia.desc())
        )
        if tipo:
            stmt = stmt.where(ApuracaoFiscal.tipo == tipo)
        return list((await self.session.execute(stmt)).scalars().all())

    async def salvar(self, apuracao: ApuracaoFiscal) -> ApuracaoFiscal:
        self.session.add(apuracao)
        await self.session.flush()
        await self.session.refresh(apuracao)
        return apuracao
