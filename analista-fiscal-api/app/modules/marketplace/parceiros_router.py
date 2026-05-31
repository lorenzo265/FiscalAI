"""Endpoints REST do contador parceiro autenticado (Sprint 13 PR3).

Auth: ``POST /v1/parceiros/login`` devolve JWT com claim ``typ='parceiro'``.
Demais endpoints aceitam Bearer <token> e exigem ``ParceiroSessionDep``
(role PG ``marketplace_partner`` + GUC ``app.contador_id``).

Endpoints:

  * ``POST /v1/parceiros/login`` — email + senha → JWT.
  * ``GET  /v1/parceiros/me`` — visão administrativa do próprio cadastro.
  * ``GET  /v1/parceiros/me/dashboard`` — agregados (abertas, mês, líquido).
  * ``GET  /v1/parceiros/me/consultas`` — lista consultas atribuídas.
  * ``POST /v1/parceiros/me/consultas/{id}/aceitar`` — substitui stub do PR2.
  * ``POST /v1/parceiros/me/consultas/{id}/responder`` — substitui stub do PR2.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.modules.marketplace.consulta_service import ConsultaService
from app.modules.marketplace.repo import ConsultaRepo, ContadorParceiroRepo
from app.modules.marketplace.schemas import (
    ConsultaOut,
    DashboardParceiroOut,
    LoginParceiroIn,
    ParceiroAdminOut,
    ResponderConsultaIn,
    StatusConsultaIn,
    TokenParceiroOut,
)
from app.modules.marketplace.service import ContadorParceiroService
from app.shared.db.deps import (
    AnonSessionDep,
    ParceiroDep,
    ParceiroSessionDep,
)
from app.shared.exceptions import (
    ConsultaNaoEncontrada,
    ContadorParceiroNaoEncontrado,
)

router = APIRouter(prefix="/v1/parceiros", tags=["marketplace-parceiros"])


@router.post(
    "/login",
    response_model=TokenParceiroOut,
    summary="Login do contador parceiro (email + senha → JWT)",
)
async def login_parceiro(
    payload: LoginParceiroIn,
    session: AnonSessionDep,
) -> TokenParceiroOut:
    token, expires_in, _parceiro = await ContadorParceiroService().login(
        session, payload
    )
    return TokenParceiroOut(access_token=token, expires_in=expires_in)


@router.get(
    "/me",
    response_model=ParceiroAdminOut,
    summary="Dados do próprio parceiro autenticado",
)
async def meu_perfil(
    ctx: ParceiroDep,
    session: ParceiroSessionDep,
) -> ParceiroAdminOut:
    parceiro = await ContadorParceiroRepo(session).por_id(ctx.contador_id)
    if parceiro is None:
        raise ContadorParceiroNaoEncontrado(
            f"Parceiro {ctx.contador_id} não encontrado"
        )
    return ParceiroAdminOut.model_validate(parceiro)


@router.get(
    "/me/dashboard",
    response_model=DashboardParceiroOut,
    summary="Agregados do painel (abertas, concluídas no mês, valor líquido)",
)
async def meu_dashboard(
    ctx: ParceiroDep,
    session: ParceiroSessionDep,
) -> DashboardParceiroOut:
    return await ContadorParceiroService().dashboard(session, ctx.contador_id)


@router.get(
    "/me/consultas",
    response_model=list[ConsultaOut],
    summary="Lista consultas atribuídas ao parceiro",
)
async def minhas_consultas(
    ctx: ParceiroDep,
    session: ParceiroSessionDep,
    status: StatusConsultaIn | None = None,
) -> list[ConsultaOut]:
    status_str = status.value if status else None
    rows = await ConsultaRepo(session).listar_por_contador(
        ctx.contador_id, status=status_str
    )
    return [ConsultaOut.model_validate(r) for r in rows]


@router.post(
    "/me/consultas/{consulta_id}/aceitar",
    response_model=ConsultaOut,
    summary="Parceiro aceita consulta (substitui stub admin do PR2)",
)
async def aceitar_consulta_parceiro(
    consulta_id: UUID,
    ctx: ParceiroDep,
    session: ParceiroSessionDep,
) -> ConsultaOut:
    consulta = await ConsultaService().aceitar(
        session,
        consulta_id=consulta_id,
        contador_id=ctx.contador_id,
    )
    return ConsultaOut.model_validate(consulta)


@router.post(
    "/me/consultas/{consulta_id}/responder",
    response_model=ConsultaOut,
    summary="Parceiro responde consulta (substitui stub admin do PR2)",
)
async def responder_consulta_parceiro(
    consulta_id: UUID,
    payload: ResponderConsultaIn,
    ctx: ParceiroDep,
    session: ParceiroSessionDep,
) -> ConsultaOut:
    if payload.contador_id != ctx.contador_id:
        # Payload veio com contador_id divergente do JWT — defesa em profundidade.
        raise ConsultaNaoEncontrada(
            "contador_id no payload não bate com o JWT"
        )
    anexos: list[dict[str, object]] | None
    if payload.arquivos_anexos is None:
        anexos = None
    else:
        anexos = [dict(item) for item in payload.arquivos_anexos]
    consulta = await ConsultaService().responder(
        session,
        consulta_id=consulta_id,
        contador_id=ctx.contador_id,
        resposta_resumo=payload.resposta_resumo,
        arquivos_anexos=anexos,
    )
    return ConsultaOut.model_validate(consulta)
