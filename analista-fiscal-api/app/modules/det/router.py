"""Endpoints REST — DET (Sprint 11 PR3)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.modules.det.repo import MensagemDetRepo
from app.modules.det.schemas import MensagemDetOut, RegistrarMensagemDetIn
from app.modules.det.service import DetService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["det"])


@router.post(
    "/{empresa_id}/det/mensagens",
    response_model=MensagemDetOut,
    status_code=201,
    summary="Registra mensagem DET (caixa postal trabalhista)",
    description=(
        "Idempotente por (empresa, id_externo_det). Origem padrão: MTE. "
        "Classificação automática por LLM (tipo/prioridade/prazo) ocorre "
        "em fluxo separado."
    ),
)
async def registrar_mensagem(
    empresa_id: UUID,
    payload: RegistrarMensagemDetIn,
    ctx: TenantDep,
    session: SessionDep,
) -> MensagemDetOut:
    mensagem = await DetService().registrar(
        session, ctx.tenant_id, empresa_id, payload
    )
    return MensagemDetOut.model_validate(mensagem)


@router.get(
    "/{empresa_id}/det/mensagens",
    response_model=list[MensagemDetOut],
    summary="Lista mensagens DET da empresa",
)
async def listar_mensagens(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    somente_nao_lidas: bool = False,
    limite: int = 100,
) -> list[MensagemDetOut]:
    rows = await MensagemDetRepo(session).listar(
        empresa_id, somente_nao_lidas=somente_nao_lidas, limite=limite,
    )
    return [MensagemDetOut.model_validate(r) for r in rows]


@router.post(
    "/{empresa_id}/det/mensagens/{mensagem_id}/lida",
    response_model=MensagemDetOut,
    summary="Marca mensagem DET como lida",
)
async def marcar_lida(
    empresa_id: UUID,
    mensagem_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> MensagemDetOut:
    mensagem = await DetService().marcar_lida(session, empresa_id, mensagem_id)
    if mensagem is None:
        raise HTTPException(
            status_code=404, detail="Mensagem DET não encontrada"
        )
    return MensagemDetOut.model_validate(mensagem)
