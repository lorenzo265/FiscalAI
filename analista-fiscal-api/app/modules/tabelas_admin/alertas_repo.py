"""Repositório de alertas admin (Sprint 19.5 PR2).

Separa-se de ``repo.py`` (que trata do log de auditoria + bridge SCD) para
isolar concerns operacionais. Mesma sessão admin com role
``tax_table_admin`` que o PR1 — ``GRANT INSERT, UPDATE, SELECT`` na
migration 0043.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import CursorResult, and_, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tabelas_admin.alertas_schemas import Severidade
from app.shared.db.models import AlertaAdmin
from app.shared.idempotency import NS_TABELA_ADMIN

_TZ_BR = ZoneInfo("America/Sao_Paulo")


def _build_idempotency_key(
    *, tipo: str, tipo_tabela: str, ano: int
) -> UUID:
    """``uuid5(NS_TABELA_ADMIN, "alerta|{tipo}|{tipo_tabela}|{ano}")``.

    1 alerta por (tipo, tipo_tabela, ano). Worker rodando em runs sucessivos
    no mesmo período produz a mesma chave — INSERT ON CONFLICT DO NOTHING
    deixa a 2ª chamada no-op.
    """
    return uuid5(
        NS_TABELA_ADMIN, f"alerta|{tipo}|{tipo_tabela}|{ano}"
    )


class AlertaAdminRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, alerta_id: UUID) -> AlertaAdmin | None:
        stmt = select(AlertaAdmin).where(AlertaAdmin.id == alerta_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def upsert_idempotente(
        self,
        *,
        tipo: str,
        tipo_tabela: str,
        ano: int,
        severidade: Severidade,
        titulo: str,
        descricao: str,
        contexto: dict[str, Any],
    ) -> AlertaAdmin | None:
        """Insere alerta no-op se idempotency_key já existe.

        Devolve o ``AlertaAdmin`` criado **ou** ``None`` se já existia
        (worker logam contadores separados). Implementa a inserção via
        ``pg_insert(...).on_conflict_do_nothing(...)`` para evitar
        round-trip extra antes do INSERT.
        """
        key = _build_idempotency_key(
            tipo=tipo, tipo_tabela=tipo_tabela, ano=ano
        )
        stmt = (
            pg_insert(AlertaAdmin)
            .values(
                tipo=tipo,
                severidade=severidade,
                titulo=titulo,
                descricao=descricao,
                contexto_jsonb=contexto,
                idempotency_key=key,
            )
            .on_conflict_do_nothing(
                index_elements=[AlertaAdmin.idempotency_key]
            )
            .returning(AlertaAdmin.id)
        )
        resultado = (await self._s.execute(stmt)).scalar_one_or_none()
        if resultado is None:
            # Conflito ON CONFLICT — alerta já existia. Retornamos None
            # (caller incrementa contador "ja_existia" do worker).
            return None
        # Recarrega o objeto completo via SELECT para devolver à camada
        # superior (caller pode logar contexto / disparar webhook).
        return await self.por_id(resultado)

    async def listar(
        self,
        *,
        severidade: Severidade | None = None,
        resolvido: bool | None = None,
        limite: int = 100,
    ) -> list[AlertaAdmin]:
        """Lista alertas. ``resolvido=False`` = abertos (resolvido_em
        IS NULL **ou** > now()); ``resolvido=True`` = passado.
        ``resolvido=None`` = sem filtro.
        """
        stmt = select(AlertaAdmin)
        if severidade is not None:
            stmt = stmt.where(AlertaAdmin.severidade == severidade)
        if resolvido is False:
            agora = datetime.now(_TZ_BR)
            stmt = stmt.where(
                or_(
                    AlertaAdmin.resolvido_em.is_(None),
                    AlertaAdmin.resolvido_em > agora,
                )
            )
        elif resolvido is True:
            agora = datetime.now(_TZ_BR)
            stmt = stmt.where(
                and_(
                    AlertaAdmin.resolvido_em.is_not(None),
                    AlertaAdmin.resolvido_em <= agora,
                )
            )
        stmt = stmt.order_by(AlertaAdmin.criado_em.desc()).limit(limite)
        return list((await self._s.execute(stmt)).scalars().all())

    async def resolver(
        self, alerta_id: UUID, *, usuario_id: UUID | None = None
    ) -> AlertaAdmin | None:
        alerta = await self.por_id(alerta_id)
        if alerta is None:
            return None
        alerta.resolvido_em = datetime.now(_TZ_BR)
        alerta.resolvido_por_usuario_id = usuario_id
        await self._s.flush()
        return alerta

    async def snooze(
        self, alerta_id: UUID, *, dias: int
    ) -> AlertaAdmin | None:
        alerta = await self.por_id(alerta_id)
        if alerta is None:
            return None
        alerta.resolvido_em = datetime.now(_TZ_BR) + timedelta(days=dias)
        await self._s.flush()
        return alerta

    async def resolver_relacionados(
        self, *, tipo_tabela: str, ano: int
    ) -> int:
        """Marca como resolvidos todos alertas abertos cujo
        ``contexto_jsonb.tipo_tabela == tipo_tabela`` e
        ``contexto_jsonb.ano_corrente == ano`` — chamado por
        ``TabelaAdminService`` após cada POST da Camada 1.

        Retorna o número de alertas marcados.
        """
        agora = datetime.now(_TZ_BR)
        # Usar SQL puro para o filtro JSONB — mais simples que arrancar
        # comparações via column-based syntax do SQLA. Update direto
        # respeitando o role tax_table_admin (que tem GRANT UPDATE).
        result = await self._s.execute(
            text(
                """
                UPDATE alerta_admin
                   SET resolvido_em = :agora
                 WHERE resolvido_em IS NULL
                   AND contexto_jsonb ->> 'tipo_tabela' = :tipo_tabela
                   AND (contexto_jsonb ->> 'ano_corrente')::int = :ano
                """
            ),
            {"agora": agora, "tipo_tabela": tipo_tabela, "ano": ano},
        )
        # ``execute()`` em UPDATE devolve CursorResult — rowcount disponível.
        # Cast explícito para satisfazer mypy strict (Result[Any] genérico
        # não expõe rowcount no stub).
        if isinstance(result, CursorResult):
            return result.rowcount or 0
        return 0


__all__ = ["AlertaAdminRepo", "_build_idempotency_key"]
