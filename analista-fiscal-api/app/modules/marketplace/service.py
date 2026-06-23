"""Service de cadastro + curadoria + auth + dashboard (Sprint 13 PR1+PR3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.marketplace.especialidades import validar_especialidades
from app.modules.marketplace.repo import ContadorParceiroRepo
from app.modules.marketplace.schemas import (
    AprovarParceiroIn,
    CadastrarParceiroIn,
    DashboardParceiroOut,
    LoginParceiroIn,
)
from app.shared.auth.jwt import ParceiroContext, criar_token_parceiro
from app.shared.auth.password import hash_senha, verificar_senha
from app.shared.db.models import ConsultaMarketplace, ContadorParceiro
from app.shared.exceptions import (
    ContadorParceiroNaoEncontrado,
    CrcJaCadastrado,
    CredenciaisParceiroInvalidas,
    EmailParceiroJaCadastrado,
    EspecialidadeInvalida,
    ParceiroSemSenhaDefinida,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


class ContadorParceiroService:
    """Cadastro + curadoria do pool global de parceiros."""

    async def cadastrar(
        self,
        session: AsyncSession,
        payload: CadastrarParceiroIn,
    ) -> ContadorParceiro:
        try:
            validar_especialidades(payload.especialidades)
        except ValueError as exc:
            raise EspecialidadeInvalida(str(exc)) from exc

        repo = ContadorParceiroRepo(session)

        if await repo.por_email(payload.email) is not None:
            raise EmailParceiroJaCadastrado(
                f"Já existe parceiro com email {payload.email}"
            )
        if await repo.por_crc(payload.crc_numero, payload.crc_uf) is not None:
            raise CrcJaCadastrado(
                f"Já existe parceiro com CRC {payload.crc_numero}/{payload.crc_uf}"
            )

        parceiro = ContadorParceiro(
            nome=payload.nome,
            email=str(payload.email),
            telefone=payload.telefone,
            cpf=payload.cpf,
            cnpj=payload.cnpj,
            crc_numero=payload.crc_numero,
            crc_uf=payload.crc_uf,
            especialidades=list(payload.especialidades),
            uf_atuacao=list(payload.uf_atuacao) if payload.uf_atuacao else None,
            oab_numero=payload.oab_numero,
            oab_uf=payload.oab_uf,
            sla_resposta_horas=payload.sla_resposta_horas,
            ativo=False,  # nasce inativo — aguarda curadoria (§10.4)
        )
        try:
            await repo.criar(parceiro)
            await session.commit()
        except IntegrityError as exc:
            # Race entre duas requests simultâneas com mesmo email/CRC.
            await session.rollback()
            raise EmailParceiroJaCadastrado(
                "Conflito de unicidade (email ou CRC já registrado em paralelo)"
            ) from exc
        await session.refresh(parceiro)

        log.info(
            "marketplace.parceiro.cadastrado",
            parceiro_id=str(parceiro.id),
            crc=f"{payload.crc_numero}/{payload.crc_uf}",
            especialidades=parceiro.especialidades,
        )
        return parceiro

    async def aprovar(
        self,
        session: AsyncSession,
        parceiro_id: UUID,
        payload: AprovarParceiroIn,
    ) -> ContadorParceiro:
        """Ato administrativo — flipa ``ativo=True`` + registra NDA opcional."""
        repo = ContadorParceiroRepo(session)
        parceiro = await repo.por_id(parceiro_id)
        if parceiro is None:
            raise ContadorParceiroNaoEncontrado(
                f"Parceiro {parceiro_id} não encontrado"
            )

        if parceiro.ativo:
            return parceiro  # idempotente

        agora = datetime.now(tz=_TZ_BR)
        parceiro.ativo = True
        if payload.registrar_aceite_nda_lgpd and parceiro.aceitou_nda_lgpd_em is None:
            parceiro.aceitou_nda_lgpd_em = agora
        await session.commit()
        await session.refresh(parceiro)

        log.info(
            "marketplace.parceiro.aprovado",
            parceiro_id=str(parceiro.id),
            nda_registrado=parceiro.aceitou_nda_lgpd_em is not None,
        )
        return parceiro

    async def definir_senha(
        self,
        session: AsyncSession,
        parceiro_id: UUID,
        senha: str,
    ) -> ContadorParceiro:
        """Admin define ou redefine a senha do parceiro (bcrypt cost 12)."""
        repo = ContadorParceiroRepo(session)
        parceiro = await repo.por_id(parceiro_id)
        if parceiro is None:
            raise ContadorParceiroNaoEncontrado(
                f"Parceiro {parceiro_id} não encontrado"
            )
        parceiro.senha_hash = hash_senha(senha)
        await session.commit()
        await session.refresh(parceiro)
        log.info(
            "marketplace.parceiro.senha_definida",
            parceiro_id=str(parceiro.id),
        )
        return parceiro

    async def login(
        self,
        session: AsyncSession,
        payload: LoginParceiroIn,
    ) -> tuple[str, int, ContadorParceiro]:
        """Autentica parceiro por email + senha. Retorna (token, exp_sec, parceiro)."""
        repo = ContadorParceiroRepo(session)
        parceiro = await repo.por_email(str(payload.email))
        if parceiro is None:
            raise CredenciaisParceiroInvalidas("E-mail ou senha incorretos")
        if not parceiro.ativo:
            raise CredenciaisParceiroInvalidas(
                "Parceiro inativo — aguardando curadoria ou suspenso"
            )
        if parceiro.senha_hash is None:
            raise ParceiroSemSenhaDefinida(
                "Senha ainda não definida — solicite ao admin"
            )
        if not verificar_senha(payload.senha, parceiro.senha_hash):
            raise CredenciaisParceiroInvalidas("E-mail ou senha incorretos")

        token, expires_in = criar_token_parceiro(
            ParceiroContext(contador_id=parceiro.id)
        )
        log.info(
            "marketplace.parceiro.login",
            parceiro_id=str(parceiro.id),
        )
        return token, expires_in, parceiro

    async def dashboard(
        self,
        session: AsyncSession,
        contador_id: UUID,
    ) -> DashboardParceiroOut:
        """Agregados consumidos pelo painel do parceiro.

        Sessão chamadora já é ``ParceiroSessionDep`` (GUC contador_id + role
        marketplace_partner) — RLS já filtra ``consulta_marketplace`` para o
        contador certo.
        """
        parceiro = await ContadorParceiroRepo(session).por_id(contador_id)
        if parceiro is None:
            raise ContadorParceiroNaoEncontrado(
                f"Parceiro {contador_id} não encontrado"
            )

        # Consultas abertas (atribuida/aceita/em_andamento).
        agora = datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
        inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        stmt_abertas = select(func.count()).where(
            ConsultaMarketplace.contador_id == contador_id,
            ConsultaMarketplace.status.in_(
                ("atribuida", "aceita", "em_andamento")
            ),
        )
        abertas = (await session.execute(stmt_abertas)).scalar_one() or 0

        stmt_concluidas = select(func.count()).where(
            ConsultaMarketplace.contador_id == contador_id,
            ConsultaMarketplace.status == "concluida",
            ConsultaMarketplace.respondida_em >= inicio_mes,
        )
        concluidas_mes = (await session.execute(stmt_concluidas)).scalar_one() or 0

        # Valor líquido = soma(valor - comissao) das consultas PAGAS no mês.
        stmt_liquido = select(
            func.coalesce(
                func.sum(
                    ConsultaMarketplace.valor_consulta
                    - ConsultaMarketplace.comissao_plataforma
                ),
                Decimal("0"),
            )
        ).where(
            ConsultaMarketplace.contador_id == contador_id,
            ConsultaMarketplace.status == "concluida",
            ConsultaMarketplace.paga_em.is_not(None),
            ConsultaMarketplace.paga_em >= inicio_mes,
        )
        valor_liquido: Decimal = (await session.execute(stmt_liquido)).scalar_one()

        return DashboardParceiroOut(
            contador_id=parceiro.id,
            nome=parceiro.nome,
            rating_medio=parceiro.rating_medio,
            total_consultas=parceiro.total_consultas,
            taxa_resposta_horas=parceiro.taxa_resposta_horas,
            consultas_abertas=int(abertas),
            consultas_concluidas_mes=int(concluidas_mes),
            valor_liquido_mes=valor_liquido,
        )
