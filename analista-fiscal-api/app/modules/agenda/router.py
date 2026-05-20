from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Query

from app.modules.agenda.schemas import AgendaGerarIn, AgendaListaOut
from app.modules.agenda.service import gerar_e_salvar_agenda, listar_agenda_empresa
from app.shared.db.deps import SessionDep, TenantDep

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/empresas/{empresa_id}/agenda", tags=["agenda"])


@router.get("", response_model=AgendaListaOut, summary="Lista o calendário fiscal")
async def listar_agenda(
    empresa_id: UUID,
    _tenant: TenantDep,
    session: SessionDep,
    ano: int | None = Query(default=None, ge=2024, le=2030),
) -> AgendaListaOut:
    """Lista todos os itens do calendário fiscal da empresa, opcionalmente filtrado por ano."""
    return await listar_agenda_empresa(empresa_id, ano, session)


@router.post(
    "/gerar",
    response_model=AgendaListaOut,
    status_code=201,
    summary="Gera (ou regenera) o calendário fiscal do ano",
)
async def gerar_agenda(
    empresa_id: UUID,
    payload: AgendaGerarIn,
    tenant: TenantDep,
    session: SessionDep,
) -> AgendaListaOut:
    """Gera todos os itens de calendário fiscal para o ano informado.

    A operação é idempotente — chamar novamente substitui os itens do ano.
    """
    log.info("agenda.gerar", empresa_id=str(empresa_id), ano=payload.ano)
    return await gerar_e_salvar_agenda(empresa_id, tenant.tenant_id, payload, session)
