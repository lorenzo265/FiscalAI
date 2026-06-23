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

import secrets
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lgpd.anonimizacao import NOME_ANONIMO, cpf_anonimo, email_anonimo
from app.modules.lgpd.repo import LgpdSolicitacaoRepo
from app.shared.auth.password import hash_senha
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

# Retencao legal antes do expurgo fisico: a LGPD (esquecimento) cede a guarda
# fiscal de 5 anos -- ate la a conta fica anonimizada e desativada, nao apagada.
_RETENCAO_ANOS = 5

# Colunas que NUNCA saem no export (hash de credencial nao e dado do titular).
_NUNCA_EXPORTA = frozenset({"senha_hash"})


def _mais_n_anos(d: date, anos: int) -> date:
    try:
        return d.replace(year=d.year + anos)
    except ValueError:  # 29/02 em ano de destino nao-bissexto -> 28/02
        return d.replace(year=d.year + anos, day=28)

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

    async def excluir(
        self, session: AsyncSession, *, tenant_id: UUID, usuario_id: UUID
    ) -> JsonObject:
        """Direito ao esquecimento por ANONIMIZACAO (LGPD art. 18, VI).

        NAO deleta fatos fiscais (imutabilidade, principio 8.2) nem viola a
        guarda fiscal de 5 anos: sobrescreve a PII de pessoas naturais por
        tokens irreversiveis, invalida a credencial, desativa a conta e agenda
        o expurgo fisico para depois da retencao. As linhas PERMANECEM (os
        valores fiscais ficam intactos) -- so a PII some.
        """
        resumo: dict[str, int] = {}

        usuarios = (await session.execute(select(Usuario))).scalars().all()
        for usuario in usuarios:
            usuario.email = email_anonimo(usuario.id)
            usuario.nome = NOME_ANONIMO
            usuario.senha_hash = hash_senha(secrets.token_hex(32))  # login impossivel
            usuario.ativo = False
        resumo["usuarios"] = len(usuarios)

        socios = (await session.execute(select(Socio))).scalars().all()
        for socio in socios:
            socio.nome = NOME_ANONIMO
            socio.cpf = cpf_anonimo(socio.id)
        resumo["socios"] = len(socios)

        funcionarios = (await session.execute(select(Funcionario))).scalars().all()
        for funcionario in funcionarios:
            funcionario.nome = NOME_ANONIMO
            funcionario.cpf = cpf_anonimo(funcionario.id)
        resumo["funcionarios"] = len(funcionarios)

        # Empresa: telefone de contato (PII de pessoa) some. CNPJ/razao_social
        # FICAM -- entidade juridica exigida pela guarda fiscal de 5 anos.
        empresas = (await session.execute(select(Empresa))).scalars().all()
        for empresa in empresas:
            empresa.whatsapp_phone = None
        resumo["empresas"] = len(empresas)

        tenant = (
            await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one_or_none()
        if tenant is not None:
            tenant.ativo = False

        agora = datetime.now(tz=_TZ_BR)
        expurgo_apos = _mais_n_anos(agora.date(), _RETENCAO_ANOS)
        await LgpdSolicitacaoRepo(session).registrar(
            tenant_id=tenant_id,
            tipo="exclusao",
            usuario_id=usuario_id,
            status="agendada",
            detalhes={"resumo": resumo, "expurgo_apos": expurgo_apos.isoformat()},
        )
        await session.commit()

        log.info(
            "lgpd.exclusao",
            tenant_id=str(tenant_id),
            total_anonimizado=sum(resumo.values()),
            expurgo_apos=expurgo_apos.isoformat(),
        )
        return {
            "status": "agendada",
            "anonimizado_em": agora.isoformat(),
            "expurgo_apos": expurgo_apos.isoformat(),
            "resumo": resumo,
        }
