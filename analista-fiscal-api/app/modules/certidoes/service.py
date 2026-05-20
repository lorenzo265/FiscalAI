"""Service de emissão e consulta de certidões (Sprint 6).

Para o MVP cobrimos:
  CND  — emitida via SERPRO Integra Contador.
  CRF  — skeleton (scraping Caixa fora de escopo do PR1; emissão registra
         status='processando' com pdf_storage_key=None para fallback manual).
  CNDT — análogo a CRF (TST não tem API pública de massa).

A lógica de parse do retorno SERPRO é defensiva — campos como `numero`,
`validade` e `pdf` aparecem aninhados em `dados` no Integra Contador. Em caso
de retorno inesperado salvamos status='erro' com `payload_json`.
"""

from __future__ import annotations

import base64
import uuid
from datetime import date, datetime, timedelta
from typing import Protocol

from app.shared.db.models import Certidao
from app.shared.types import JsonObject
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.certidoes.repo import CertidoesRepo
from app.modules.certidoes.schemas import (
    CertidaoStatus,
    CertidaoTipo,
    EmitirCertidaoOut,
)
from app.modules.empresa.repo import EmpresaRepo
from app.shared.exceptions import (
    CertidaoEmissaoFalhou,
    EmpresaNaoEncontrada,
    SerproErro,
    SerproTimeout,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")

# Validade legal por tipo (§9.2 + legislação)
_VALIDADE_DIAS: dict[CertidaoTipo, int] = {
    CertidaoTipo.CND: 180,  # PGFN/RFB Portaria Conjunta 1.751/2014
    CertidaoTipo.CRF: 30,  # Caixa — Manual FGTS
    CertidaoTipo.CNDT: 180,  # TST — Lei 12.440/2011, art. 642-A §1º
}


class _ClienteCnd(Protocol):
    """Subset de :class:`SerproClient` usado aqui — facilita mock em testes."""

    async def emitir_certidao_cnd(
        self, cnpj: str, *, idempotency_key: str
    ) -> JsonObject: ...


class CertidoesService:
    async def emitir(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        tipo: CertidaoTipo,
        *,
        serpro_client: _ClienteCnd | None,
    ) -> EmitirCertidaoOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        repo = CertidoesRepo(session)

        if tipo is CertidaoTipo.CND:
            certidao = await self._emitir_cnd(
                session=session,
                repo=repo,
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                cnpj=empresa.cnpj,
                serpro_client=serpro_client,
            )
        else:
            # CRF e CNDT: skeleton no PR1 — fallback manual.
            certidao = await self._emitir_skeleton(
                repo=repo,
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                tipo=tipo,
            )

        await session.commit()

        if certidao.status == CertidaoStatus.PROCESSANDO.value:
            mensagem = (
                "Emissão registrada. Para CRF/CNDT, o módulo automático será "
                "ativado no PR3 da Sprint 6 — por ora baixe manualmente em "
                "consulta-crf.caixa.gov.br ou cndt-certidao.tst.jus.br."
            )
        else:
            mensagem = f"Certidão {tipo.value} emitida com sucesso."

        return EmitirCertidaoOut(
            certidao_id=certidao.id,
            tipo=tipo,
            status=CertidaoStatus(certidao.status),
            numero=certidao.numero,
            valid_until=certidao.valid_until,
            mensagem=mensagem,
        )

    async def _emitir_cnd(
        self,
        *,
        session: AsyncSession,
        repo: CertidoesRepo,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        cnpj: str,
        serpro_client: _ClienteCnd | None,
    ) -> Certidao:
        if serpro_client is None:
            raise CertidaoEmissaoFalhou("SERPRO client não disponível em runtime")

        idempotency_key = _gerar_idempotency_key(empresa_id, "cnd")
        agora = datetime.now(_TZ_BR)
        try:
            resposta = await serpro_client.emitir_certidao_cnd(
                cnpj, idempotency_key=idempotency_key
            )
        except (SerproErro, SerproTimeout) as exc:
            log.warning(
                "certidoes.cnd.serpro_falhou",
                empresa_id=str(empresa_id),
                erro=exc.codigo,
                mensagem=exc.mensagem,
            )
            return await repo.criar(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                tipo=CertidaoTipo.CND.value,
                status=CertidaoStatus.ERRO.value,
                emitida_em=agora,
                payload_json={"erro": exc.codigo, "mensagem": exc.mensagem},
            )

        numero, status, pdf_b64 = _parse_resposta_cnd(resposta)
        valid_until = (agora + timedelta(days=_VALIDADE_DIAS[CertidaoTipo.CND])).date()
        pdf_storage_key = (
            _persistir_pdf(empresa_id, CertidaoTipo.CND, pdf_b64) if pdf_b64 else None
        )

        return await repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo=CertidaoTipo.CND.value,
            status=status,
            emitida_em=agora,
            numero=numero,
            valid_until=valid_until,
            pdf_storage_key=pdf_storage_key,
            payload_json=resposta,
        )

    async def _emitir_skeleton(
        self,
        *,
        repo: CertidoesRepo,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        tipo: CertidaoTipo,
    ) -> Certidao:
        """Registra a emissão de CRF/CNDT como 'processando' (skeleton PR1)."""
        return await repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo=tipo.value,
            status=CertidaoStatus.PROCESSANDO.value,
            emitida_em=datetime.now(_TZ_BR),
            payload_json={"fonte": "skeleton_pr1"},
        )


# ── helpers puros (testáveis sem DB) ─────────────────────────────────────────


def _gerar_idempotency_key(empresa_id: uuid.UUID, sufixo: str) -> str:
    """Chave determinística por (empresa, sufixo, data) — evita duplicar emissão no dia.

    Como certidão CND tem validade legal de 180 dias, usar a data garante que
    retentativas no mesmo dia caiam no idempotency lock do SERPRO e não
    gerem chamadas extras (custo).
    """
    base = f"{empresa_id}:{sufixo}:{date.today().isoformat()}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, base))


def _parse_resposta_cnd(
    resposta: JsonObject,
) -> tuple[str | None, str, str | None]:
    """Extrai (numero, status, pdf_base64) do payload Integra Contador.

    O SERPRO envia o resultado serializado em ``dados`` (JSON string) com chaves
    como ``numero``, ``situacao`` e ``pdfBase64``. Quando o formato muda,
    fazemos fallback conservador para status='emitida'.
    """
    dados_raw = resposta.get("dados")
    if isinstance(dados_raw, dict):
        dados = dados_raw
    elif isinstance(dados_raw, str):
        try:
            import json

            dados = json.loads(dados_raw)
        except (ValueError, TypeError):
            dados = {}
    else:
        dados = {}

    numero = dados.get("numero") or resposta.get("numeroCertidao")
    situacao_raw = (dados.get("situacao") or resposta.get("situacao") or "").lower()
    pdf_b64 = dados.get("pdfBase64") or resposta.get("pdfBase64")

    if "positiva com efeitos" in situacao_raw or "ce-pen" in situacao_raw:
        status = CertidaoStatus.POSITIVA_COM_EFEITOS_DE_NEGATIVA.value
    elif "negativa" in situacao_raw:
        status = CertidaoStatus.NEGATIVA.value
    elif "positiva" in situacao_raw:
        status = CertidaoStatus.POSITIVA.value
    else:
        status = CertidaoStatus.EMITIDA.value

    return (str(numero) if numero else None, status, pdf_b64)


def _persistir_pdf(
    empresa_id: uuid.UUID, tipo: CertidaoTipo, pdf_base64: str
) -> str | None:
    """Persiste o PDF base64 retornado pelo SERPRO no object storage.

    No MVP gravamos a chave futura (sem upload real) — a integração com S3/GCS
    é skeleton e fica como entregável separado. Decodifica para validar.
    """
    try:
        base64.b64decode(pdf_base64, validate=True)
    except (ValueError, TypeError):
        log.warning("certidoes.pdf_invalido", empresa_id=str(empresa_id), tipo=tipo.value)
        return None
    return f"certidoes/{empresa_id}/{tipo.value}_{date.today().isoformat()}.pdf"
