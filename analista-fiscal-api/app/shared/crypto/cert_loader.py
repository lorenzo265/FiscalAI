"""Helper único de carregamento de certificado A1 ICP-Brasil por empresa.

Por ora retorna ``None`` — a gestão de cert A1 é um épico próprio.

TODO épico "gestão de cert A1 por empresa":
  - Tabela cifrada (ex.: ``PiiCifrada`` com campo ``cert_p12``) ou secret
    manager (Vault / AWS Secrets Manager) com upload do .p12 por empresa.
  - Decifra via AES-256-GCM com chave de app (§8.7 LGPD-first).
  - Retorna ``(p12_bytes, senha)`` pronto para ``construir_assinador``.

Este é o **único ponto de entrada** do cert A1 no sistema. Todos os módulos
que necessitam de assinatura XMLDSig devem passar por aqui — não inventar
outro caminho de carregamento. Isso garante:

  * Um único lugar para auditar acesso a cert (§8.7).
  * Um único lugar para substituir a implementação (Vault, HSM, etc.).
  * Rastreabilidade via log estruturado (sem PII sensível no log).

Módulos eSocial e EFD-Reinf hoje passam ``cert_p12_bytes=None`` direto no
router. Quando este helper estiver implementado, migrar para cá via:
  # TODO: migrar para carregar_cert_a1
  cert = await carregar_cert_a1(session, empresa_id)
  assinador = construir_assinador(
      cert_p12_bytes=cert[0] if cert else None,
      senha=cert[1] if cert else None,
      transmissao_ativa=settings.ESOCIAL_TRANSMISSAO_ATIVA,
  )
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


async def carregar_cert_a1(
    session: AsyncSession,
    empresa_id: UUID,
) -> tuple[bytes, str] | None:
    """Carrega o certificado A1 (.p12 ICP-Brasil) da empresa do storage cifrado.

    Args:
        session: sessão async com RLS ativo (SET LOCAL app.tenant_id).
            Necessária para buscar os bytes cifrados no DB, quando implementado.
        empresa_id: UUID da empresa cujo cert deve ser carregado.

    Returns:
        ``(p12_bytes, senha)`` quando o cert estiver disponível no storage
        cifrado; ``None`` quando indisponível (dev/CI ou empresa sem cert
        configurado). O caller deve usar ``construir_assinador`` com os bytes
        retornados; ``None`` resulta em ``NotImplementedXmldsigSigner``
        (fail-soft §8.12).

    TODO (épico "gestão de cert A1 por empresa"):
        1. Definir schema da tabela / secret manager (fora desta entrega).
        2. Buscar bytes cifrados via repo (usando ``session``).
        3. Decifrar com chave de app (AES-256-GCM, §8.7).
        4. Validar que o .p12 pertence à empresa (CNPJ no subject do cert).
        5. Retornar ``(p12_bytes, senha_descriptografada)``.
    """
    # TODO: buscar cert cifrado da empresa no storage/DB e decifrar.
    # Por ora, log em debug (não info — emitido em todo request de transmissão)
    # para não poluir os logs em dev/CI.
    log.debug(
        "cert.indisponivel",
        empresa_id=str(empresa_id),
        motivo=(
            "gestão de cert A1 por empresa não implementada — épico próprio. "
            "Transmissão permanece inerte (NotImplementedXmldsigSigner)."
        ),
    )
    return None
