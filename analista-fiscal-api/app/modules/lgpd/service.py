"""Service do modulo LGPD -- exportacao (portabilidade, LGPD art. 18, II).

Reune TODOS os dados do tenant num JSON estruturado (direito de portabilidade)
e registra a solicitacao na trilha de auditoria ``lgpd_solicitacao``.

Isolamento: a sessao e RLS-scoped por tenant (``get_session`` faz SET ROLE
fiscal_app + app.tenant_id), entao cada ``select(Modelo)`` ja devolve SOMENTE
as linhas do tenant autenticado -- todas as entidades exportadas tem coluna
``tenant_id`` com policy RLS. O ``tenant`` (linha unica) e filtrado por id.

Serializacao generica por introspeccao do mapper: exporta todas as colunas de
cada entidade, EXCETO o denylist de PII sensivel (``senha_hash``) e os blobs
binarios (XML/PDF), que ficam fora do JSON (disponiveis via storage proprio).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lgpd.repo import LgpdSolicitacaoRepo
from app.shared.db.base import Base
from app.shared.db.models import (
    ApuracaoFiscal,
    Certidao,
    DistribuicaoLucros,
    DocumentoFiscal,
    Empresa,
    FolhaMensal,
    Funcionario,
    GuiaPagamento,
    Holerite,
    ProlaboreMensal,
    Socio,
    Tenant,
    Usuario,
)
from app.shared.types import JsonObject, JsonValue

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")

# Colunas que NUNCA saem no export (hash de credencial nao e dado do titular).
_NUNCA_EXPORTA = frozenset({"senha_hash"})

# (secao, modelo) -- toda entidade tem ``tenant_id`` + policy RLS, entao um
# ``select`` simples ja vem isolado por tenant. Ordem = leitura humana.
_ENTIDADES: tuple[tuple[str, type[Base]], ...] = (
    ("usuarios", Usuario),
    ("empresas", Empresa),
    ("socios", Socio),
    ("funcionarios", Funcionario),
    ("documentos_fiscais", DocumentoFiscal),
    ("apuracoes_fiscais", ApuracaoFiscal),
    ("guias_pagamento", GuiaPagamento),
    ("folhas_mensais", FolhaMensal),
    ("holerites", Holerite),
    ("prolabores", ProlaboreMensal),
    ("distribuicoes_lucros", DistribuicaoLucros),
    ("certidoes", Certidao),
)


def _coerce(valor: object) -> JsonValue:
    """Converte um valor de coluna para um tipo JSON-serializavel."""
    if valor is None or isinstance(valor, bool | int | str):
        return valor
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    if isinstance(valor, UUID):
        return str(valor)
    if isinstance(valor, dict | list):  # JSONB
        return valor
    if isinstance(valor, bytes | bytearray | memoryview):
        return None  # blobs binarios (XML/PDF) ficam fora do JSON
    return str(valor)


def _serializar(obj: Base) -> JsonObject:
    """Serializa uma linha do ORM em dict JSON-safe, menos o denylist de PII."""
    out: JsonObject = {}
    for coluna in sa_inspect(type(obj)).columns:
        nome = coluna.key
        if nome in _NUNCA_EXPORTA:
            continue
        out[nome] = _coerce(getattr(obj, nome))
    return out


class LgpdService:
    async def exportar(
        self, session: AsyncSession, *, tenant_id: UUID, usuario_id: UUID
    ) -> JsonObject:
        """Reune os dados do tenant e registra a solicitacao de portabilidade."""
        dados: JsonObject = {}
        resumo: dict[str, int] = {}

        tenant = (
            await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one_or_none()
        dados["tenant"] = _serializar(tenant) if tenant is not None else None

        for secao, modelo in _ENTIDADES:
            linhas = (await session.execute(select(modelo))).scalars().all()
            dados[secao] = [_serializar(linha) for linha in linhas]
            resumo[secao] = len(linhas)

        await LgpdSolicitacaoRepo(session).registrar(
            tenant_id=tenant_id,
            tipo="exportacao",
            usuario_id=usuario_id,
            status="concluida",
            detalhes={"resumo": resumo},
        )
        await session.commit()

        log.info(
            "lgpd.exportacao",
            tenant_id=str(tenant_id),
            usuario_id=str(usuario_id),
            total_registros=sum(resumo.values()),
        )
        return {
            "gerado_em": datetime.now(tz=_TZ_BR).isoformat(),
            "tenant_id": str(tenant_id),
            "resumo": resumo,
            "dados": dados,
        }
