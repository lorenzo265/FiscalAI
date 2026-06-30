"""Endpoints REST — Manifestação do Destinatário NF-e (MD-e).

PR1: POST registrar + GET listar.
PR2: POST sincronizar (DistribuiçãoDFe) + GET destinadas.
Transmissão ao SEFAZ: TODO PR3.

§8.12 — o endpoint POST registra e opcionalmente assina (fail-soft);
        status 'preparado' = assinatura pendente, 'assinado' = pronto para PR3.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.modules.manifestacao.distribuicao_repo import DistribuicaoRepo
from app.modules.manifestacao.distribuicao_service import DistribuicaoService
from app.modules.manifestacao.repo import ManifestacaoRepo
from app.modules.manifestacao.schemas import (
    ManifestacaoNFeOut,
    NfeDestinadaOut,
    RegistrarManifestacaoIn,
    SincronizacaoResultadoOut,
    SincronizarManifestacaoIn,
    TipoEventoManifestacaoIn,
)
from app.modules.manifestacao.service import ManifestacaoService
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.db.models import Empresa
from app.shared.exceptions import EmpresaNaoEncontrada
from app.shared.integrations.sefaz_mde.provider import build_sefaz_mde_provider

router = APIRouter(prefix="/v1/empresas", tags=["manifestacao_nfe"])


@router.post(
    "/{empresa_id}/manifestacao",
    response_model=ManifestacaoNFeOut,
    status_code=201,
    summary="Registra evento de Manifestação do Destinatário (MD-e)",
    description=(
        "Valida a chave NF-e (44 dígitos), monta o XML ``envEvento`` conforme "
        "NT 2014.002 / NT 2020.001 e tenta assinar via XMLDSig (cert A1). "
        "Fail-soft: sem certificado configurado, persiste em ``status='preparado'``. "
        "**Transmissão ao webservice SEFAZ: PR3 (pendência consciente)**. "
        "Idempotente por ``idempotency_key`` (quando fornecida). "
        "Tipos de evento: 210200 Confirmação, 210210 Ciência, "
        "210220 Desconhecimento, 210240 Não Realizada (exige justificativa)."
    ),
)
async def registrar_manifestacao(
    empresa_id: UUID,
    payload: RegistrarManifestacaoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ManifestacaoNFeOut:
    manifestacao = await ManifestacaoService().registrar(
        session,
        ctx.tenant_id,
        empresa_id,
        payload,
        # Cert A1 não é resolvido aqui ainda — mesma pendência do eSocial/Reinf.
        # Pre-piloto: cert virá do storage cifrado (PR3).
        cert_p12_bytes=None,
        cert_senha=None,
        transmissao_ativa=False,
    )
    return ManifestacaoNFeOut.model_validate(manifestacao)


@router.get(
    "/{empresa_id}/manifestacao",
    response_model=list[ManifestacaoNFeOut],
    summary="Lista eventos MD-e da empresa",
    description=(
        "Filtra por chave NF-e, tipo de evento e/ou status. "
        "Ordenado por criado_em DESC. Limite padrão: 100."
    ),
)
async def listar_manifestacoes(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    chave_nfe: str | None = Query(default=None, description="Filtra por chave de acesso NF-e (44 dígitos)."),
    tipo_evento: TipoEventoManifestacaoIn | None = Query(default=None, description="Filtra por tipo de evento."),
    status: str | None = Query(default=None, description="Filtra por status (preparado/assinado/transmitido/aceito/rejeitado)."),
    limite: int = Query(default=100, ge=1, le=500, description="Máximo de registros retornados."),
) -> list[ManifestacaoNFeOut]:
    tipo_str = tipo_evento.value if tipo_evento else None
    rows = await ManifestacaoRepo(session).listar_empresa(
        empresa_id,
        chave_nfe=chave_nfe,
        tipo_evento=tipo_str,
        status=status,
        limite=limite,
    )
    return [ManifestacaoNFeOut.model_validate(r) for r in rows]


# ── PR2: Descoberta (DistribuiçãoDFe) ────────────────────────────────────────


@router.post(
    "/{empresa_id}/manifestacao/sincronizar",
    response_model=SincronizacaoResultadoOut,
    status_code=200,
    summary="Sincroniza NF-es recebidas via DistribuiçãoDFe",
    description=(
        "Consulta o serviço DistribuiçãoDFe (SEFAZ Ambiente Nacional) a partir "
        "do último NSU persistido no cursor da empresa. Faz upsert idempotente "
        "de cada NF-e descoberta em ``nfe_destinada``. Em dev/CI usa o "
        "``_FakeSefazMdeProvider`` (sem rede); com ``FOCUS_NFE_TOKEN`` configurado "
        "usa o provider real (best-effort — endpoint a confirmar na doc Focus NFe "
        "[follow-up PR3]). "
        "``truncado=true`` indica que o sync foi interrompido pelo cap de páginas; "
        "chame novamente para continuar de onde parou."
    ),
)
async def sincronizar_manifestacao(
    empresa_id: UUID,
    payload: SincronizarManifestacaoIn,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> SincronizacaoResultadoOut:
    # Resolve o CNPJ da empresa — necessário para chamar o DistribuiçãoDFe.
    stmt = select(Empresa.cnpj).where(Empresa.id == empresa_id)
    cnpj_row = (await session.execute(stmt)).scalar_one_or_none()
    if cnpj_row is None:
        raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

    settings = request.app.state.settings
    provider = build_sefaz_mde_provider(settings)

    return await DistribuicaoService().sincronizar(
        session,
        ctx.tenant_id,
        empresa_id,
        cnpj_row,
        provider,
    )


@router.get(
    "/{empresa_id}/manifestacao/destinadas",
    response_model=list[NfeDestinadaOut],
    summary="Lista NF-es destinadas descobertas pelo DistribuiçãoDFe",
    description=(
        "Retorna NF-es emitidas contra o CNPJ da empresa, descobertas pelo sync. "
        "``pendentes=true`` filtra apenas as que ainda não possuem nenhum evento "
        "de manifestação em ``manifestacao_nfe`` para a mesma chave. "
        "Ordenado por NSU decrescente."
    ),
)
async def listar_destinadas(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    pendentes: bool = Query(
        default=False,
        description=(
            "Se true, retorna apenas NF-es sem nenhum evento de manifestação "
            "(Confirmação/Ciência/Desconhecimento/Não Realizada). "
            "Se false, retorna todas as NF-es descobertas."
        ),
    ),
    limite: int = Query(
        default=100, ge=1, le=500, description="Máximo de registros retornados."
    ),
) -> list[NfeDestinadaOut]:
    rows = await DistribuicaoRepo(session).listar_destinadas(
        empresa_id,
        pendentes=pendentes,
        limite=limite,
    )
    return [NfeDestinadaOut.model_validate(r) for r in rows]
