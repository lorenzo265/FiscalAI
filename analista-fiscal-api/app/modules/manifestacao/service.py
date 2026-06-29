"""Service — Manifestação do Destinatário NF-e (MD-e).

Orquestra: valida → gera XML (puro) → assina (factory, fail-soft) → persiste.
Transmissão efetiva ao webservice SEFAZ fica para PR3 (TODO).

§8.12 — assinatura é ato consciente; sem cert A1 o service persiste o
XML não-assinado em status 'preparado' (fail-soft) sem levantar exceção
ao caller — o status retornado informa ao cliente que a assinatura
ainda está pendente.
§8.9  — idempotência: se idempotency_key já existe, devolve o registro
         sem novo INSERT.
§8.2  — append-only: a manifestação persistida é fato imutável.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.manifestacao.manifestacao_xml import (
    ALGORITMO_VERSAO,
    gerar_xml_evento,
)
from app.modules.manifestacao.repo import ManifestacaoRepo
from app.modules.manifestacao.schemas import RegistrarManifestacaoIn
from app.shared.crypto.xmldsig import (
    XmldsigSigningError,
    construir_assinador,
    hash_xml_canonico,
)
from app.shared.db.models import ManifestacaoNFe
from app.shared.exceptions import (
    ChaveNFeInvalida,
    ManifestacaoJustificativaObrigatoria,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")

# Chave NF-e: 44 dígitos numéricos (NT 2014.002 §4.1.1.2)
_RE_CHAVE = re.compile(r"^\d{44}$")


class ManifestacaoService:
    """Orquestrador do ciclo de vida de um evento MD-e.

    Constrói o ``ManifestacaoRepo`` a partir da ``session`` recebida em
    ``registrar`` — testes unitários injetam uma session fake/transacional.
    """

    async def registrar(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        payload: RegistrarManifestacaoIn,
        *,
        # Injeção opcional do assinador (default: factory do ambiente)
        cert_p12_bytes: bytes | None = None,
        cert_senha: str | None = None,
        transmissao_ativa: bool = False,
    ) -> ManifestacaoNFe:
        """Registra (e opcionalmente assina) um evento MD-e.

        Fluxo:
          1. Validação de domínio (chave 44 dígitos, justificativa para 210240).
          2. Idempotência: se idempotency_key já existe, devolve existente.
          3. Geração do XML canônico (função pura).
          4. Tentativa de assinatura XMLDSig via factory (fail-soft).
          5. Persistência com status 'assinado' (se ok) ou 'preparado' (falha).

        Transmissão ao webservice SEFAZ: TODO PR3.

        Args:
            session: sessão async com RLS ativo (SET LOCAL app.tenant_id).
            tenant_id: UUID do tenant (herdado do JWT).
            empresa_id: UUID da empresa que manifesta.
            payload: dados validados pelo schema Pydantic.
            cert_p12_bytes: bytes do .p12 ICP-Brasil (None = dev/fallback).
            cert_senha: senha do .p12 (None = dev/fallback).
            transmissao_ativa: flag §8.12 (default False em dev/CI).

        Returns:
            ManifestacaoNFe persistida (status 'preparado' ou 'assinado').
            Caller verifica ``status`` para saber se assinatura foi bem-sucedida.

        Raises:
            ChaveNFeInvalida: chave não tem 44 dígitos.
            ManifestacaoJustificativaObrigatoria: tipo 210240 sem justificativa.
        """
        repo = ManifestacaoRepo(session)

        # ── 1. Validação de domínio ───────────────────────────────────────────
        if not _RE_CHAVE.match(payload.chave_nfe):
            raise ChaveNFeInvalida(
                f"Chave NF-e deve ter 44 dígitos numéricos: {payload.chave_nfe!r}"
            )
        tipo = payload.tipo_evento.value
        if tipo == "210240" and not payload.justificativa:
            raise ManifestacaoJustificativaObrigatoria(
                "Evento 210240 (Operação não Realizada) exige campo justificativa."
            )

        # ── 2. Idempotência por chave opaca ───────────────────────────────────
        if payload.idempotency_key:
            existente = await repo.por_idempotency_key(
                empresa_id, payload.idempotency_key
            )
            if existente is not None:
                log.info(
                    "manifestacao.idempotente",
                    empresa_id=str(empresa_id),
                    idempotency_key=payload.idempotency_key,
                    manifestacao_id=str(existente.id),
                )
                return existente

        # ── 3. Geração do XML canônico ────────────────────────────────────────
        dh_evento = datetime.now(_TZ_BR)
        xml_str, id_infevento = gerar_xml_evento(
            cnpj_destinatario=payload.cnpj_destinatario,
            chave_nfe=payload.chave_nfe,
            tipo_evento=tipo,
            sequencial=payload.sequencial,
            tp_amb=payload.tp_amb,
            dh_evento=dh_evento,
            justificativa=payload.justificativa,
        )
        hash_xml = hash_xml_canonico(xml_str)

        log.info(
            "manifestacao.xml.gerado",
            empresa_id=str(empresa_id),
            tipo_evento=tipo,
            # Chave NF-e é pública (consta na NF-e em si), sem redação LGPD.
            chave_nfe=payload.chave_nfe,
            id_infevento=id_infevento,
            hash_xml=hash_xml[:16] + "...",
        )

        # ── 4. Tentativa de assinatura (fail-soft §8.12) ─────────────────────
        assinador = construir_assinador(
            cert_p12_bytes=cert_p12_bytes,
            senha=cert_senha,
            transmissao_ativa=transmissao_ativa,
        )
        status_final = "preparado"
        assinado_em: datetime | None = None

        try:
            _xml_assinado_bytes = assinador.assinar(
                xml_str, id_referencia=id_infevento
            )
            status_final = "assinado"
            assinado_em = datetime.now(_TZ_BR)
            log.info(
                "manifestacao.assinado",
                empresa_id=str(empresa_id),
                id_infevento=id_infevento,
            )
        except XmldsigSigningError as exc:
            # Fail-soft §8.12: sem cert/grupo opt-in → persiste em 'preparado'.
            # O caller verifica manifestacao.status — não é exceção de negócio.
            log.warning(
                "manifestacao.assinatura.indisponivel",
                empresa_id=str(empresa_id),
                id_infevento=id_infevento,
                motivo=str(exc),
            )

        # ── 5. Persistência ───────────────────────────────────────────────────
        # Chave determinística de storage — PR3 gravará o XML no object storage.
        # Aqui apenas definimos a chave; o write I/O acontecerá em PR3.
        storage_key = (
            f"tenant/{tenant_id}/empresa/{empresa_id}/manifestacao/"
            f"{payload.chave_nfe}/{tipo}/{payload.sequencial:02d}.xml"
        )

        manifestacao = await repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            chave_nfe=payload.chave_nfe,
            cnpj_destinatario=payload.cnpj_destinatario,
            tipo_evento=tipo,
            sequencial=payload.sequencial,
            justificativa=payload.justificativa,
            status=status_final,
            algoritmo_versao=ALGORITMO_VERSAO,
            xml_evento_storage_key=storage_key,
            idempotency_key=payload.idempotency_key,
            assinado_em=assinado_em,
        )
        await session.commit()

        log.info(
            "manifestacao.registrada",
            empresa_id=str(empresa_id),
            manifestacao_id=str(manifestacao.id),
            tipo_evento=tipo,
            status=status_final,
            algoritmo_versao=ALGORITMO_VERSAO,
        )

        return manifestacao
