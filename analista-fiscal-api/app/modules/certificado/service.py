"""Serviço do cofre de certificado A1 — valida, cifra e persiste.

Fluxo de upload: inspeciona o .p12 (abre com a senha, extrai metadados) →
checa validade e CNPJ → cifra (.p12 em base64 + senha) com o envelope
AES-256-GCM → desativa o cert anterior e insere o novo. Nunca loga material
sensível (.p12/senha/CNPJ) — §8.7.
"""

from __future__ import annotations

import base64
import re
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.certificado.inspeciona_p12 import inspecionar_p12
from app.modules.certificado.repo import CertificadoA1Repo
from app.shared.crypto.envelope import carregar_chave, cifrar
from app.shared.db.models import CertificadoA1, Empresa
from app.shared.exceptions import (
    CertificadoA1CnpjDivergente,
    CertificadoA1Expirado,
    CertificadoA1NaoEncontrado,
    EmpresaNaoEncontrada,
)

log = structlog.get_logger(__name__)


def _so_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor)


class CertificadoService:
    async def salvar(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        *,
        pfx_bytes: bytes,
        senha: str,
    ) -> CertificadoA1:
        """Valida e guarda o certificado A1 cifrado, substituindo o anterior."""
        info = inspecionar_p12(pfx_bytes, senha)  # CertificadoA1Invalido se ruim

        if info.validade_fim <= datetime.now(UTC):
            raise CertificadoA1Expirado(
                f"Certificado vencido em {info.validade_fim.date().isoformat()}. "
                "Envie um certificado A1 dentro da validade."
            )

        cnpj_empresa = await self._cnpj_empresa(session, empresa_id)
        if (
            info.cnpj_titular is not None
            and _so_digitos(info.cnpj_titular) != _so_digitos(cnpj_empresa)
        ):
            raise CertificadoA1CnpjDivergente(
                "O CNPJ do certificado não corresponde ao CNPJ da empresa."
            )

        chave = carregar_chave(get_settings().PII_ENCRYPTION_KEY)
        pfx_cifrado = cifrar(base64.b64encode(pfx_bytes).decode("ascii"), chave)
        senha_cifrada = cifrar(senha, chave)

        repo = CertificadoA1Repo(session)
        await repo.desativar_ativos(empresa_id)
        cert = await repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            pfx_cifrado=pfx_cifrado,
            senha_cifrada=senha_cifrada,
            cn_titular=info.cn_titular,
            cnpj_titular=info.cnpj_titular,
            validade_inicio=info.validade_inicio,
            validade_fim=info.validade_fim,
            fingerprint=info.fingerprint,
        )
        # Log sem PII: empresa_id (UUID), fingerprint e validade — nunca cert/senha/CNPJ.
        log.info(
            "cert_a1.salvo",
            empresa_id=str(empresa_id),
            fingerprint=info.fingerprint,
            validade_fim=info.validade_fim.isoformat(),
        )
        return cert

    async def obter_status(
        self, session: AsyncSession, empresa_id: UUID
    ) -> CertificadoA1 | None:
        """O certificado ativo (metadados), ou None se a empresa não tem cert."""
        return await CertificadoA1Repo(session).obter_ativo(empresa_id)

    async def remover(self, session: AsyncSession, empresa_id: UUID) -> None:
        """Desativa o certificado ativo da empresa."""
        repo = CertificadoA1Repo(session)
        cert = await repo.obter_ativo(empresa_id)
        if cert is None:
            raise CertificadoA1NaoEncontrado(
                f"Empresa {empresa_id} não tem certificado A1 ativo."
            )
        await repo.desativar_ativos(empresa_id)
        log.info("cert_a1.removido", empresa_id=str(empresa_id))

    async def _cnpj_empresa(self, session: AsyncSession, empresa_id: UUID) -> str:
        stmt = select(Empresa.cnpj).where(Empresa.id == empresa_id)
        cnpj = (await session.execute(stmt)).scalar_one_or_none()
        if cnpj is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        return cnpj
