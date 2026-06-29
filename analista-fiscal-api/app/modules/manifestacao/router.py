"""Endpoints REST — Manifestação do Destinatário NF-e (MD-e).

PR1: POST registrar + GET listar.
Transmissão ao SEFAZ: TODO PR3.

§8.12 — o endpoint POST registra e opcionalmente assina (fail-soft);
        status 'preparado' = assinatura pendente, 'assinado' = pronto para PR3.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.modules.manifestacao.repo import ManifestacaoRepo
from app.modules.manifestacao.schemas import (
    ManifestacaoNFeOut,
    RegistrarManifestacaoIn,
    TipoEventoManifestacaoIn,
)
from app.modules.manifestacao.service import ManifestacaoService
from app.shared.db.deps import SessionDep, TenantDep

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
