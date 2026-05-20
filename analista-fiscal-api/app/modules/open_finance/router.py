"""Endpoints REST Open Finance (Sprint 7)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request

from app.modules.open_finance.repo import PluggyItemRepo
from app.modules.open_finance.schemas import (
    ConnectTokenOut,
    ContaBancariaOut,
    PluggyItemOut,
    RegistrarItemIn,
    StatusItem,
    StatusTransacao,
    SyncOut,
    TipoConta,
    TipoTransacao,
    TransacaoBancariaOut,
    WebhookAckOut,
)
from app.modules.open_finance.service import OpenFinanceService
from app.modules.open_finance.sync_service import SyncService
from app.modules.open_finance.transacoes_repo import (
    ContaBancariaRepo,
    TransacoesRepo,
)
from app.modules.open_finance.webhook_service import WebhookService
from app.shared.db.deps import AnonSessionDep, SessionDep, TenantDep
from app.shared.exceptions import WebhookPluggyAssinaturaInvalida
from app.shared.integrations.pluggy.webhook import (
    extrair_evento,
    verificar_assinatura_pluggy,
)

router = APIRouter(prefix="/v1/empresas", tags=["open-finance"])
webhook_router = APIRouter(prefix="/v1/open-finance", tags=["open-finance"])


@router.post(
    "/{empresa_id}/open-finance/connect-token",
    response_model=ConnectTokenOut,
    status_code=201,
    summary="Gera connect_token para o widget Pluggy",
    description=(
        "Retorna token de curta duração (~30 min) que o frontend usa para "
        "abrir o widget Open Finance da Pluggy. Após o cliente autorizar a "
        "conexão bancária, o widget devolve o pluggy_item_id que deve ser "
        "registrado via POST /open-finance/items."
    ),
)
async def connect_token(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> ConnectTokenOut:
    pluggy_client = getattr(request.app.state, "pluggy_client", None)
    return await OpenFinanceService().emitir_connect_token(
        session, empresa_id, pluggy_client=pluggy_client
    )


@router.post(
    "/{empresa_id}/open-finance/items",
    response_model=PluggyItemOut,
    status_code=201,
    summary="Registra item Pluggy após sucesso do widget",
)
async def registrar_item(
    empresa_id: UUID,
    payload: RegistrarItemIn,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> PluggyItemOut:
    pluggy_client = getattr(request.app.state, "pluggy_client", None)
    return await OpenFinanceService().registrar_item(
        session,
        ctx.tenant_id,
        empresa_id,
        payload,
        pluggy_client=pluggy_client,
    )


@router.get(
    "/{empresa_id}/open-finance/items",
    response_model=list[PluggyItemOut],
    summary="Lista items Open Finance da empresa",
)
async def listar_items(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> list[PluggyItemOut]:
    items = await PluggyItemRepo(session).listar(empresa_id)
    return [
        PluggyItemOut(
            id=i.id,
            empresa_id=i.empresa_id,
            pluggy_item_id=i.pluggy_item_id,
            connector_id=i.connector_id,
            connector_nome=i.connector_nome,
            status=_status_seguro(i.status),
            last_sync_at=i.last_sync_at,
            ativo=i.ativo,
            criado_em=i.criado_em,
        )
        for i in items
    ]


def _status_seguro(raw: str) -> StatusItem:
    """Mapeia string do banco para enum; fallback para CREATING se desconhecido."""
    try:
        return StatusItem(raw)
    except ValueError:
        return StatusItem.CREATING


# ── PR2: sync, contas, transações, webhook ──────────────────────────────────


@router.post(
    "/{empresa_id}/open-finance/items/{item_uuid}/sync",
    response_model=SyncOut,
    status_code=202,
    summary="Força sync manual de contas + transações para um item",
)
async def sync_item(
    empresa_id: UUID,
    item_uuid: UUID,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
    desde: date | None = Query(default=None, description="Data inicial (AAAA-MM-DD)"),
    ate: date | None = Query(default=None, description="Data final (AAAA-MM-DD)"),
) -> SyncOut:
    pluggy_client = getattr(request.app.state, "pluggy_client", None)
    resultado = await SyncService().sincronizar_item(
        session,
        ctx.tenant_id,
        item_uuid,
        pluggy_client=pluggy_client,
        from_date=desde,
        to_date=ate,
    )
    return SyncOut(
        contas_processadas=resultado.contas_processadas,
        contas_novas=resultado.contas_novas,
        transacoes_processadas=resultado.transacoes_processadas,
    )


@router.get(
    "/{empresa_id}/contas-bancarias",
    response_model=list[ContaBancariaOut],
    summary="Lista contas bancárias conectadas via Open Finance",
)
async def listar_contas(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> list[ContaBancariaOut]:
    rows = await ContaBancariaRepo(session).listar(empresa_id)
    return [
        ContaBancariaOut(
            id=c.id,
            pluggy_item_id=c.pluggy_item_id,
            pluggy_account_id=c.pluggy_account_id,
            banco_nome=c.banco_nome,
            agencia=c.agencia,
            numero=c.numero,
            tipo=TipoConta(c.tipo) if c.tipo in TipoConta.__members__ else TipoConta.CHECKING,
            subtipo=c.subtipo,
            moeda=c.moeda,
            saldo_atual=c.saldo_atual,
            saldo_disponivel=c.saldo_disponivel,
            saldo_atualizado_em=c.saldo_atualizado_em,
        )
        for c in rows
    ]


@router.get(
    "/{empresa_id}/transacoes",
    response_model=list[TransacaoBancariaOut],
    summary="Lista transações bancárias da empresa",
)
async def listar_transacoes(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    conta_id: UUID | None = Query(default=None),
    desde: date | None = Query(default=None),
    ate: date | None = Query(default=None),
    limite: int = Query(default=200, ge=1, le=1000),
) -> list[TransacaoBancariaOut]:
    rows = await TransacoesRepo(session).listar(
        empresa_id,
        conta_id=conta_id,
        desde=desde,
        ate=ate,
        limite=limite,
    )
    return [
        TransacaoBancariaOut(
            id=t.id,
            conta_bancaria_id=t.conta_bancaria_id,
            pluggy_transaction_id=t.pluggy_transaction_id,
            data_transacao=t.data_transacao,
            valor=t.valor,
            descricao=t.descricao,
            tipo=TipoTransacao(t.tipo),
            status=StatusTransacao(t.status),
            categoria_pluggy=t.categoria_pluggy,
            merchant_cnpj=t.merchant_cnpj,
            merchant_nome=t.merchant_nome,
        )
        for t in rows
    ]


@webhook_router.post(
    "/webhook",
    response_model=WebhookAckOut,
    status_code=200,
    summary="Webhook Pluggy — recebe eventos de items e transações",
    description=(
        "Endpoint público cross-tenant. Validação HMAC obrigatória via "
        "header X-Pluggy-Signature. Eventos duplicados (mesmo event_id) "
        "retornam recebido=true mas duplicado=true."
    ),
)
async def pluggy_webhook(
    request: Request,
    anon_session: AnonSessionDep,
    x_pluggy_signature: str = Header(default=""),
) -> WebhookAckOut:
    body = await request.body()
    settings = request.app.state.settings
    if not verificar_assinatura_pluggy(
        body, x_pluggy_signature, settings.PLUGGY_WEBHOOK_SECRET
    ):
        raise WebhookPluggyAssinaturaInvalida(
            "Assinatura HMAC do webhook Pluggy inválida"
        )

    import json

    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Body inválido (não é JSON)")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body deve ser objeto JSON")

    event_id, item_pluggy_id, event_type = extrair_evento(payload)
    if not event_id or not item_pluggy_id or not event_type:
        raise HTTPException(
            status_code=400,
            detail="Payload Pluggy sem campos obrigatórios (id, itemId, event)",
        )

    resultado = await WebhookService().persistir(
        anon_session,
        event_id=event_id,
        item_pluggy_id=item_pluggy_id,
        event_type=event_type,
        payload=payload,
    )
    return WebhookAckOut(recebido=True, duplicado=resultado.duplicado)
