"""Helper único de carregamento de certificado A1 ICP-Brasil por empresa.

**Único ponto de entrada** do cert A1 no sistema. Todos os módulos que assinam
XMLDSig (eSocial, EFD-Reinf, MD-e) passam por aqui — não inventar outro caminho
de carregamento. Garante um só lugar para auditar acesso ao cert (§8.7), um só
lugar para trocar a implementação (Vault/HSM no futuro) e rastreabilidade no log
estruturado (sem material sensível).

Implementação (épico cert A1, 2026-06-30): lê o certificado ATIVO e dentro da
validade da empresa em ``certificado_a1`` e decifra o .p12 (base64) e a senha
com o envelope AES-256-GCM (§8.7). Retorna ``None`` quando a empresa não tem
cert configurado ou o cert ativo está vencido — caller cai em
``NotImplementedXmldsigSigner`` (fail-soft §8.12), transmissão inerte.
"""

from __future__ import annotations

import base64
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.config import get_settings
from app.shared.crypto.envelope import carregar_chave, decifrar
from app.shared.db.models import CertificadoA1

log = structlog.get_logger(__name__)


async def carregar_cert_a1(
    session: AsyncSession,
    empresa_id: UUID,
) -> tuple[bytes, str] | None:
    """Carrega o certificado A1 (.p12) ativo e válido da empresa, decifrado.

    Args:
        session: sessão async com RLS ativo (SET LOCAL app.tenant_id).
        empresa_id: empresa cujo cert deve ser carregado.

    Returns:
        ``(p12_bytes, senha)`` quando há cert ativo e dentro da validade;
        ``None`` quando indisponível (empresa sem cert ou cert vencido). O
        caller usa ``construir_assinador`` com os bytes; ``None`` resulta em
        ``NotImplementedXmldsigSigner`` (fail-soft §8.12).
    """
    stmt = select(CertificadoA1).where(
        CertificadoA1.empresa_id == empresa_id,
        CertificadoA1.ativo.is_(True),
        CertificadoA1.validade_fim > func.now(),
    )
    cert = (await session.execute(stmt)).scalar_one_or_none()
    if cert is None:
        # debug (não info): emitido em todo request de transmissão.
        log.debug(
            "cert.indisponivel",
            empresa_id=str(empresa_id),
            motivo="sem certificado A1 ativo e válido para a empresa",
        )
        return None

    chave = carregar_chave(get_settings().PII_ENCRYPTION_KEY)
    pfx_bytes = base64.b64decode(decifrar(cert.pfx_cifrado, chave))
    senha = decifrar(cert.senha_cifrada, chave)
    log.debug("cert.carregado", empresa_id=str(empresa_id), fingerprint=cert.fingerprint)
    return (pfx_bytes, senha)
