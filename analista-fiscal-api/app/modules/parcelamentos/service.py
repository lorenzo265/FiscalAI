"""Service — parcelamentos (Sprint 11 PR3)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.parcelamentos.calcula_parcelamento import (
    TipoContribuinte,
    gerar_parcelamento_ordinario,
)
from app.modules.parcelamentos.repo import ParcelamentoRepo
from app.modules.parcelamentos.schemas import (
    CancelarParcelamentoIn,
    CriarParcelamentoIn,
    TipoContribuinteIn,
    TipoParcelamentoIn,
)
from app.shared.db.models import ParcelaFiscal, ParcelamentoFiscal
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    ParcelamentoInvalido,
    ParcelamentoJaCancelado,
    ParcelamentoNaoEncontrado,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


class ParcelamentoService:
    async def criar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: CriarParcelamentoIn,
    ) -> ParcelamentoFiscal:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        # PR3 modela apenas ordinário; demais tipos persistem com parcela_base
        # calculada pela mesma fórmula simples (sem regras especiais ainda).
        contribuinte = (
            TipoContribuinte.PJ
            if payload.contribuinte is TipoContribuinteIn.PJ
            else TipoContribuinte.PF
        )
        try:
            resultado = gerar_parcelamento_ordinario(
                divida_consolidada=payload.divida_consolidada,
                num_parcelas=payload.num_parcelas,
                data_adesao=payload.data_adesao,
                contribuinte=contribuinte,
            )
        except ValueError as exc:
            raise ParcelamentoInvalido(str(exc)) from exc

        parcelamento = ParcelamentoFiscal(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo=payload.tipo.value,
            identificador_externo=payload.identificador_externo,
            data_adesao=payload.data_adesao,
            divida_consolidada=payload.divida_consolidada,
            num_parcelas=payload.num_parcelas,
            parcela_base=resultado.parcela_base,
            algoritmo_versao=resultado.algoritmo_versao,
        )
        parcelas = [
            ParcelaFiscal(
                tenant_id=tenant_id,
                parcelamento_id=parcelamento.id,
                numero=p.numero,
                vencimento=p.vencimento,
                valor_projetado=p.valor_projetado,
            )
            for p in resultado.parcelas
        ]
        await ParcelamentoRepo(session).criar(parcelamento, parcelas)
        await session.commit()
        await session.refresh(parcelamento)

        log.info(
            "parcelamento.criado",
            parcelamento_id=str(parcelamento.id),
            empresa_id=str(empresa_id),
            tipo=payload.tipo.value,
            divida=str(payload.divida_consolidada),
            num=payload.num_parcelas,
            parcela_base=str(resultado.parcela_base),
        )
        return parcelamento

    async def cancelar(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        parcelamento_id: UUID,
        payload: CancelarParcelamentoIn,
    ) -> ParcelamentoFiscal:
        parcelamento = await ParcelamentoRepo(session).por_id(parcelamento_id)
        if parcelamento is None or parcelamento.empresa_id != empresa_id:
            raise ParcelamentoNaoEncontrado(
                f"Parcelamento {parcelamento_id} não encontrado nesta empresa"
            )
        if parcelamento.status in ("cancelado", "rescindido"):
            raise ParcelamentoJaCancelado(
                f"Parcelamento já está em estado {parcelamento.status}"
            )

        parcelamento.status = "cancelado"
        parcelamento.cancelado_em = datetime.now(tz=_TZ_BR)
        parcelamento.motivo_cancelamento = payload.motivo
        await session.commit()
        await session.refresh(parcelamento)

        log.info(
            "parcelamento.cancelado",
            parcelamento_id=str(parcelamento_id),
            empresa_id=str(empresa_id),
            motivo=payload.motivo,
        )
        return parcelamento
