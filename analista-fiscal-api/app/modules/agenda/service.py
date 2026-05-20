from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agenda.gerar_calendario import gerar_calendario_anual
from app.modules.agenda.repo import (
    buscar_regime_empresa,
    deletar_agenda_ano,
    listar_agenda,
    salvar_itens,
)
from app.modules.agenda.schemas import AgendaGerarIn, AgendaItemOut, AgendaListaOut
from app.shared.db.models import AgendaItem
from app.shared.exceptions import DomainError


class RegimeNaoSuportadoError(DomainError):
    http_status = 422

    def __init__(self, regime: str) -> None:
        super().__init__(
            mensagem=f"Regime {regime!r} não suportado para geração de calendário",
            codigo="REGIME_NAO_SUPORTADO_AGENDA",
        )


async def gerar_e_salvar_agenda(
    empresa_id: UUID,
    tenant_id: UUID,
    payload: AgendaGerarIn,
    session: AsyncSession,
) -> AgendaListaOut:
    """Gera (ou regenera) o calendário fiscal de um ano para a empresa."""
    try:
        regime = await buscar_regime_empresa(session, empresa_id)
    except ValueError as exc:
        from app.shared.exceptions import EmpresaNaoEncontrada
        raise EmpresaNaoEncontrada(str(exc)) from exc

    try:
        itens_calendario = gerar_calendario_anual(
            regime,
            payload.ano,
            tem_funcionarios=payload.tem_funcionarios,
            parcelar_irpj=payload.parcelar_irpj,
        )
    except ValueError as exc:
        raise RegimeNaoSuportadoError(regime) from exc

    # Substitui itens existentes do ano (idempotente)
    await deletar_agenda_ano(session, empresa_id, payload.ano)

    db_itens = [
        AgendaItem(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            titulo=item.titulo,
            descricao=item.descricao,
            data_vencimento=item.data_vencimento,
            regime=item.regime,
            tipo_obrigacao=item.tipo_obrigacao,
        )
        for item in itens_calendario
    ]
    await salvar_itens(session, db_itens)
    await session.commit()

    return AgendaListaOut(
        empresa_id=empresa_id,
        ano=payload.ano,
        total=len(db_itens),
        itens=[
            AgendaItemOut(
                id=item.id,
                titulo=item.titulo,
                descricao=item.descricao,
                data_vencimento=item.data_vencimento,
                regime=item.regime,
                tipo_obrigacao=item.tipo_obrigacao,
                status=item.status,
            )
            for item in db_itens
        ],
    )


async def listar_agenda_empresa(
    empresa_id: UUID,
    ano: int | None,
    session: AsyncSession,
) -> AgendaListaOut:
    itens = await listar_agenda(session, empresa_id, ano)
    return AgendaListaOut(
        empresa_id=empresa_id,
        ano=ano or 0,
        total=len(itens),
        itens=[
            AgendaItemOut(
                id=item.id,
                titulo=item.titulo,
                descricao=item.descricao,
                data_vencimento=item.data_vencimento,
                regime=item.regime,
                tipo_obrigacao=item.tipo_obrigacao,
                status=item.status,
            )
            for item in itens
        ],
    )
