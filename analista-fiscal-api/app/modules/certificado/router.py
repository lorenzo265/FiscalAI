"""Endpoints REST — cofre de certificado A1 por empresa.

  POST   /v1/empresas/{empresa_id}/certificado   → sobe/substitui o .p12 (201)
  GET    /v1/empresas/{empresa_id}/certificado   → status (metadados) ou 404
  DELETE /v1/empresas/{empresa_id}/certificado   → desativa (204)

O .p12 e a senha são guardados cifrados (envelope AES-256-GCM, §8.7); a saída
nunca expõe material sensível. O certificado destrava a transmissão real
(eSocial/Reinf/MD-e) via ``carregar_cert_a1`` — mas cada módulo só transmite
com seu flag ``*_TRANSMISSAO_ATIVA`` ligado (§8.12, ato consciente).
"""

from __future__ import annotations

import base64
import binascii
from uuid import UUID

from fastapi import APIRouter

from app.modules.certificado.schemas import (
    CertificadoStatusOut,
    CertificadoUploadIn,
    RemocaoCertificadoOut,
)
from app.modules.certificado.service import CertificadoService
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.exceptions import CertificadoA1Invalido, CertificadoA1NaoEncontrado

router = APIRouter(prefix="/v1/empresas", tags=["certificado_a1"])


@router.post(
    "/{empresa_id}/certificado",
    response_model=CertificadoStatusOut,
    status_code=201,
    summary="Sobe (ou substitui) o certificado A1 da empresa",
    description=(
        "Recebe o arquivo .p12/.pfx em base64 + senha. Valida abrindo o "
        "certificado, confere a validade e (quando extraível) o CNPJ do titular "
        "contra o da empresa, e guarda o material **cifrado em repouso** "
        "(AES-256-GCM, §8.7). Substitui o certificado anterior (o antigo é "
        "desativado, histórico preservado). A resposta traz só metadados — "
        "nunca o .p12 nem a senha."
    ),
)
async def subir_certificado(
    empresa_id: UUID,
    payload: CertificadoUploadIn,
    ctx: TenantDep,
    session: SessionDep,
) -> CertificadoStatusOut:
    try:
        pfx_bytes = base64.b64decode(payload.pfx_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CertificadoA1Invalido(
            "O conteúdo enviado não é um base64 válido do arquivo .p12."
        ) from exc
    if not pfx_bytes:
        raise CertificadoA1Invalido("Arquivo .p12 vazio.")

    cert = await CertificadoService().salvar(
        session,
        ctx.tenant_id,
        empresa_id,
        pfx_bytes=pfx_bytes,
        senha=payload.senha,
    )
    return CertificadoStatusOut.model_validate(cert)


@router.get(
    "/{empresa_id}/certificado",
    response_model=CertificadoStatusOut,
    summary="Status do certificado A1 da empresa",
    description=(
        "Retorna os metadados do certificado ativo (CN, CNPJ, validade, "
        "fingerprint). 404 se a empresa não tem certificado configurado."
    ),
)
async def status_certificado(
    empresa_id: UUID,
    session: SessionDep,
) -> CertificadoStatusOut:
    cert = await CertificadoService().obter_status(session, empresa_id)
    if cert is None:
        raise CertificadoA1NaoEncontrado(
            f"Empresa {empresa_id} não tem certificado A1 ativo."
        )
    return CertificadoStatusOut.model_validate(cert)


@router.delete(
    "/{empresa_id}/certificado",
    response_model=RemocaoCertificadoOut,
    summary="Remove (desativa) o certificado A1 da empresa",
    description=(
        "Desativa o certificado ativo — as transmissões voltam a ficar inertes "
        "até um novo upload. O registro é mantido (histórico/auditoria). "
        "404 se a empresa não tem certificado ativo."
    ),
)
async def remover_certificado(
    empresa_id: UUID,
    session: SessionDep,
) -> RemocaoCertificadoOut:
    await CertificadoService().remover(session, empresa_id)
    return RemocaoCertificadoOut(removido=True)
