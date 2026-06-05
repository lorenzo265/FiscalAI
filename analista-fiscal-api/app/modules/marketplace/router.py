"""Endpoints REST — marketplace (Sprint 13 PR1).

Três grupos de endpoints:

  * ``POST /v1/marketplace/parceiros`` — cadastro público (sem auth). Cria
    parceiro inativo aguardando curadoria.
  * ``POST /v1/admin/marketplace/parceiros/{id}/aprovar`` — aprovação.
  * ``GET  /v1/admin/marketplace/parceiros`` — listagem administrativa.

Auth admin: header ``X-Admin-Token`` comparado contra
``settings.MARKETPLACE_ADMIN_TOKEN``. Se a env var estiver vazia, qualquer
chamada admin retorna 503 — fail-closed por construção. JWT-based admin auth
fica para sprint futura junto com painel interno.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.config import Settings
from app.modules.marketplace.categorias import pricing_para
from app.modules.marketplace.consulta_service import ConsultaService
from app.modules.marketplace.matching import top_parceiros
from app.modules.marketplace.pagamento import ConsultaPagamentoService
from app.modules.marketplace.repo import ConsultaRepo, ContadorParceiroRepo
from app.modules.marketplace.schemas import (
    AceitarConsultaIn,
    AprovarParceiroIn,
    AvaliarConsultaIn,
    CadastrarParceiroIn,
    CobrancaOut,
    ConsultaOut,
    CriarConsultaIn,
    DefinirSenhaParceiroIn,
    ParceiroAdminOut,
    ParceiroOut,
    ParceiroSugeridoOut,
    ResponderConsultaIn,
    StatusConsultaIn,
    WebhookPagamentoIn,
)
from app.modules.marketplace.service import ContadorParceiroService
from app.modules.empresa.repo import EmpresaRepo
from app.shared.db.deps import (
    AnonSessionDep,
    SessionDep,
    TenantDep,
    WebhookSessionDep,
)
from app.shared.exceptions import (
    ConsultaNaoEncontrada,
    ContadorParceiroNaoEncontrado,
    EmpresaNaoEncontrada,
    SemParceirosDisponiveis,
    WebhookPagamentoAssinaturaInvalida,
)
from uuid import UUID

router = APIRouter(prefix="/v1", tags=["marketplace"])


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def require_admin_token(
    request: Request,
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> None:
    """Compara o header com ``settings.MARKETPLACE_ADMIN_TOKEN`` em tempo constante.

    Token vazio em settings → 503 (fail-closed). Token inválido → 401.
    """
    settings = _settings(request)
    expected = settings.MARKETPLACE_ADMIN_TOKEN
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Endpoints administrativos do marketplace desabilitados "
            "(MARKETPLACE_ADMIN_TOKEN não configurado).",
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="X-Admin-Token inválido")


AdminDep = Annotated[None, Depends(require_admin_token)]


@router.post(
    "/marketplace/parceiros",
    response_model=ParceiroOut,
    status_code=201,
    summary="Auto-cadastro de contador parceiro (público)",
    description=(
        "Cria o parceiro com ``ativo=False`` — aguarda curadoria via "
        "POST /v1/admin/marketplace/parceiros/{id}/aprovar."
    ),
)
async def cadastrar_parceiro(
    payload: CadastrarParceiroIn,
    session: AnonSessionDep,
) -> ParceiroOut:
    parceiro = await ContadorParceiroService().cadastrar(session, payload)
    return ParceiroOut.model_validate(parceiro)


@router.post(
    "/admin/marketplace/parceiros/{parceiro_id}/aprovar",
    response_model=ParceiroAdminOut,
    summary="Aprova parceiro na curadoria (admin)",
)
async def aprovar_parceiro(
    parceiro_id: UUID,
    payload: AprovarParceiroIn,
    session: AnonSessionDep,
    _admin: AdminDep,
) -> ParceiroAdminOut:
    parceiro = await ContadorParceiroService().aprovar(session, parceiro_id, payload)
    return ParceiroAdminOut.model_validate(parceiro)


@router.get(
    "/admin/marketplace/parceiros",
    response_model=list[ParceiroAdminOut],
    summary="Lista parceiros (admin)",
)
async def listar_parceiros(
    session: AnonSessionDep,
    _admin: AdminDep,
    somente_ativos: bool = False,
    limite: int = 100,
) -> list[ParceiroAdminOut]:
    rows = await ContadorParceiroRepo(session).listar(
        somente_ativos=somente_ativos, limite=limite
    )
    return [ParceiroAdminOut.model_validate(r) for r in rows]


@router.get(
    "/admin/marketplace/parceiros/{parceiro_id}",
    response_model=ParceiroAdminOut,
    summary="Detalha parceiro (admin)",
)
async def detalhar_parceiro(
    parceiro_id: UUID,
    session: AnonSessionDep,
    _admin: AdminDep,
) -> ParceiroAdminOut:
    parceiro = await ContadorParceiroRepo(session).por_id(parceiro_id)
    if parceiro is None:
        raise ContadorParceiroNaoEncontrado(f"Parceiro {parceiro_id} não encontrado")
    return ParceiroAdminOut.model_validate(parceiro)


@router.post(
    "/admin/marketplace/parceiros/{parceiro_id}/definir-senha",
    response_model=ParceiroAdminOut,
    summary="Admin define/redefine senha do parceiro (Sprint 13 PR3)",
)
async def definir_senha_parceiro(
    parceiro_id: UUID,
    payload: DefinirSenhaParceiroIn,
    session: AnonSessionDep,
    _admin: AdminDep,
) -> ParceiroAdminOut:
    parceiro = await ContadorParceiroService().definir_senha(
        session, parceiro_id, payload.senha
    )
    return ParceiroAdminOut.model_validate(parceiro)


# ── Consulta marketplace (PR2) ──────────────────────────────────────────────


@router.get(
    "/empresas/{empresa_id}/marketplace/parceiros-sugeridos",
    response_model=list[ParceiroSugeridoOut],
    summary="Top-k parceiros aptos para a categoria (cliente PME)",
    description=(
        "Devolve os 3 parceiros melhor ranqueados que cobrem a categoria + "
        "UF da empresa. Usado pelo assistente quando detecta out-of-scope."
    ),
)
async def parceiros_sugeridos(
    empresa_id: UUID,
    categoria: str,
    ctx: TenantDep,
    session: SessionDep,
    k: int = 3,
) -> list[ParceiroSugeridoOut]:
    pricing = pricing_para(categoria)
    empresa = await EmpresaRepo(session).por_id(empresa_id)
    if empresa is None:
        raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
    # Listar parceiros usa anon session (pool global, sem RLS) — para isso
    # criamos uma query direta com o factory. Aqui, segurança não é problema:
    # o pool de parceiros é público por design (cliente precisa ver opções).
    parceiros = await ContadorParceiroRepo(session).listar_ativos(limite=500)
    top = top_parceiros(
        parceiros,
        categoria=categoria,
        uf=empresa.uf,
        k=k,
        sla_aceitar_horas=int(pricing.sla_aceitar.total_seconds() // 3600),
    )
    return [ParceiroSugeridoOut.model_validate(p) for p in top]


@router.post(
    "/empresas/{empresa_id}/marketplace/consultas",
    response_model=ConsultaOut,
    status_code=201,
    summary="Abre uma nova consulta no marketplace",
    description=(
        "Idempotente: mesma pergunta + mesma categoria + mesmo dia retorna a "
        "consulta já existente (sem 409). Cliente deve marcar consentimento "
        "explícito (§8.7). Se ``contador_id`` for informado, sistema valida "
        "que o parceiro está apto."
    ),
)
async def criar_consulta(
    empresa_id: UUID,
    payload: CriarConsultaIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ConsultaOut:
    consulta = await ConsultaService().criar(
        session,
        tenant_id=ctx.tenant_id,
        empresa_id=empresa_id,
        usuario_id=ctx.usuario_id,
        categoria=payload.categoria.value,
        pergunta=payload.pergunta,
        consentimento=payload.consentimento_compartilhamento,
        contador_id=payload.contador_id,
        valor_consulta=payload.valor_consulta,
    )
    return ConsultaOut.model_validate(consulta)


@router.get(
    "/empresas/{empresa_id}/marketplace/consultas",
    response_model=list[ConsultaOut],
    summary="Lista consultas da empresa (cliente PME)",
)
async def listar_consultas(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    status: StatusConsultaIn | None = None,
) -> list[ConsultaOut]:
    status_str = status.value if status else None
    rows = await ConsultaRepo(session).listar_por_empresa(
        empresa_id, status=status_str
    )
    return [ConsultaOut.model_validate(r) for r in rows]


@router.get(
    "/empresas/{empresa_id}/marketplace/consultas/{consulta_id}",
    response_model=ConsultaOut,
    summary="Detalha consulta (cliente PME)",
)
async def detalhar_consulta(
    empresa_id: UUID,
    consulta_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> ConsultaOut:
    consulta = await ConsultaRepo(session).por_id(consulta_id)
    if consulta is None or consulta.empresa_id != empresa_id:
        raise ConsultaNaoEncontrada(
            f"Consulta {consulta_id} não encontrada nesta empresa"
        )
    return ConsultaOut.model_validate(consulta)


@router.post(
    "/empresas/{empresa_id}/marketplace/consultas/{consulta_id}/avaliar",
    response_model=ConsultaOut,
    summary="Cliente avalia consulta concluída (1–5)",
)
async def avaliar_consulta(
    empresa_id: UUID,
    consulta_id: UUID,
    payload: AvaliarConsultaIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ConsultaOut:
    # FIX #10: empresa_id é passado ao service e validado ANTES de qualquer
    # mutação/commit (§8.1). RLS bloqueia cross-tenant; o service bloqueia
    # cross-empresa same-tenant sem efeito colateral.
    consulta = await ConsultaService().avaliar(
        session,
        consulta_id=consulta_id,
        empresa_id=empresa_id,
        rating=payload.rating,
        comentario=payload.comentario,
    )
    return ConsultaOut.model_validate(consulta)


# ── Endpoints do parceiro (stub PR2 — auth real entra no PR3) ───────────────
#
# Por enquanto exigem X-Admin-Token (mesmo guard do CRUD administrativo).
# PR3 troca para ``ParceiroSessionDep`` com ``app.contador_id`` GUC + role
# ``marketplace_partner``.


@router.post(
    "/marketplace/consultas/{consulta_id}/aceitar",
    response_model=ConsultaOut,
    summary="Parceiro aceita consulta (PR2: admin-token; PR3: parceiro auth)",
)
async def aceitar_consulta(
    consulta_id: UUID,
    payload: AceitarConsultaIn,
    session: AnonSessionDep,
    _admin: AdminDep,
) -> ConsultaOut:
    consulta = await ConsultaService().aceitar(
        session,
        consulta_id=consulta_id,
        contador_id=payload.contador_id,
    )
    return ConsultaOut.model_validate(consulta)


@router.post(
    "/marketplace/consultas/{consulta_id}/responder",
    response_model=ConsultaOut,
    summary="Parceiro responde consulta (PR2: admin-token; PR3: parceiro auth)",
)
async def responder_consulta(
    consulta_id: UUID,
    payload: ResponderConsultaIn,
    session: AnonSessionDep,
    _admin: AdminDep,
) -> ConsultaOut:
    anexos: list[dict[str, object]] | None
    if payload.arquivos_anexos is None:
        anexos = None
    else:
        anexos = [dict(item) for item in payload.arquivos_anexos]
    consulta = await ConsultaService().responder(
        session,
        consulta_id=consulta_id,
        contador_id=payload.contador_id,
        resposta_resumo=payload.resposta_resumo,
        arquivos_anexos=anexos,
    )
    return ConsultaOut.model_validate(consulta)


# ── Pagamento (Sprint 13 PR3) ──────────────────────────────────────────────


@router.post(
    "/empresas/{empresa_id}/marketplace/consultas/{consulta_id}/pagar",
    response_model=CobrancaOut,
    status_code=201,
    summary="Gera cobrança para consulta concluída (cliente PME)",
    description=(
        "Idempotente — chamadas repetidas na mesma consulta devolvem a "
        "cobrança existente. Provider real (Stripe Connect/Pagar.me) entra "
        "em sprint futura — ADR 0015 documenta. PR3 usa ``_FakeProvider``."
    ),
)
async def pagar_consulta(
    empresa_id: UUID,
    consulta_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> CobrancaOut:
    consulta = await ConsultaRepo(session).por_id(consulta_id)
    if consulta is None or consulta.empresa_id != empresa_id:
        raise ConsultaNaoEncontrada(
            f"Consulta {consulta_id} não encontrada nesta empresa"
        )
    cobranca = await ConsultaPagamentoService().gerar_cobranca(
        session,
        tenant_id=ctx.tenant_id,
        consulta_id=consulta_id,
    )
    return CobrancaOut.model_validate(cobranca)


@router.post(
    "/empresas/{empresa_id}/marketplace/consultas/{consulta_id}/revogar-consentimento",
    response_model=ConsultaOut,
    summary="Cliente revoga consentimento LGPD da consulta (§8.7)",
    description=(
        "Marca ``consentimento_revogado_em=now``. Task Celery diária expurga "
        "``pergunta`` e ``contexto_empresa_jsonb`` após 30 dias (PR3)."
    ),
)
async def revogar_consentimento(
    empresa_id: UUID,
    consulta_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> ConsultaOut:
    consulta = await ConsultaRepo(session).por_id(consulta_id)
    if consulta is None or consulta.empresa_id != empresa_id:
        raise ConsultaNaoEncontrada(
            f"Consulta {consulta_id} não encontrada nesta empresa"
        )
    from datetime import datetime
    from zoneinfo import ZoneInfo

    if consulta.consentimento_revogado_em is None:
        consulta.consentimento_revogado_em = datetime.now(
            tz=ZoneInfo("America/Sao_Paulo")
        )
        await session.commit()
        await session.refresh(consulta)
    return ConsultaOut.model_validate(consulta)


# Webhook do provider — sem auth de usuário; em prod usa HMAC do provider.
# Stub PR3 confia em ``X-Provider-Signature`` comparado contra um secret
# fixo (``settings.MARKETPLACE_PAGAMENTO_WEBHOOK_SECRET`` — adicionar).


webhook_router = APIRouter(prefix="/v1/webhooks", tags=["marketplace-webhooks"])


def _verificar_hmac_webhook_pagamento(
    body_bytes: bytes,
    signature: str | None,
    secret: str,
) -> bool:
    """Valida X-Provider-Signature contra HMAC-SHA256(body, secret).

    Reusa o padrão de ``verificar_assinatura_pluggy`` (mesma lógica: prefixo
    opcional ``sha256=``, comparação via ``hmac.compare_digest``). Fail-closed:
    secret vazio ou ausente → False (§8.9).
    """
    if not secret or not signature:
        return False
    esperado = hmac.new(
        secret.encode(), body_bytes, hashlib.sha256
    ).hexdigest()
    # Aceita com ou sem prefixo "sha256=" (compatibilidade Stripe/Pagar.me/outros).
    recebido = (
        signature[len("sha256="):]
        if signature.startswith("sha256=")
        else signature
    )
    return hmac.compare_digest(esperado, recebido.strip().lower())


@webhook_router.post(
    "/pagamento",
    response_model=CobrancaOut,
    summary="Webhook do provider de pagamento — atualiza status (Sprint 13 PR3)",
)
async def webhook_pagamento(
    request: Request,
    session: WebhookSessionDep,
    x_provider_signature: Annotated[str | None, Header(alias="X-Provider-Signature")] = None,
) -> CobrancaOut:
    """FIX #11 — HMAC validado ANTES de qualquer processamento.

    1. Lê o body bruto (bytes) — necessário para HMAC sobre payload não-parseado.
    2. Verifica X-Provider-Signature contra MARKETPLACE_PAGAMENTO_WEBHOOK_SECRET.
       Fail-closed: secret vazio → rejeita (401). Assinatura inválida → rejeita (401).
    3. Só depois deserializa WebhookPagamentoIn e chama o service.
    A sessão (WebhookSessionDep) continua sendo superuser (bypassa RLS) porque o
    provider não conhece o tenant — mas o acesso agora requer assinatura válida.
    """
    settings = _settings(request)
    body_bytes = await request.body()

    if not _verificar_hmac_webhook_pagamento(
        body_bytes, x_provider_signature, settings.MARKETPLACE_PAGAMENTO_WEBHOOK_SECRET
    ):
        raise WebhookPagamentoAssinaturaInvalida(
            "X-Provider-Signature ausente ou inválida — webhook rejeitado"
        )

    import json
    try:
        raw = json.loads(body_bytes)
    except (ValueError, TypeError) as exc:
        raise WebhookPagamentoAssinaturaInvalida(
            "Payload do webhook não é JSON válido"
        ) from exc

    payload = WebhookPagamentoIn.model_validate(raw)
    cobranca = await ConsultaPagamentoService().processar_webhook(
        session,
        provider_externo_id=payload.provider_externo_id,
        status=payload.status.value,
    )
    return CobrancaOut.model_validate(cobranca)
