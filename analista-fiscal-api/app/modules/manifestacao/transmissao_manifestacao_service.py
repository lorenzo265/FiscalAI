"""Serviço de transmissão do evento MD-e ao webservice SEFAZ RecepcaoEvento.

MD-e PR3 — pipeline completo: (re)assina → grava XML → transmite → grava
recibo → atualiza status.

Espelha 1:1 o padrão ``TransmissaoReinfService`` (Marco 4 PR2 #11).

Princípios cravados:

  * §8.12 — flag ``MANIFESTACAO_TRANSMISSAO_ATIVA`` default False.
            Sem a flag, o pipeline levanta ``ManifestacaoTransmissaoDesativada``
            (412 — fail-closed).
  * §8.9  — idempotência: manifestação já 'aceita'/'transmitida' → no-op
            (retorna como está, sem retransmissão).
  * §8.2  — XML assinado é imutável; status final atualiza só metadados
            operacionais (protocolo, cStat, timestamps).
  * DI-first: ``signer``, ``provider``, ``storage`` são injetados pelo
            caller (router ou test) — o service nunca instancia o assinador
            real internamente.

Critério de aceite (NT 2014.002 §6.1 / MOC NF-e v7.0):
  cStat 135 — Evento registrado e vinculado a NF-e → 'aceito'
  cStat 136 — Evento registrado, mas NF-e não encontrada no AN → 'aceito'
  outros    — Rejeição → 'rejeitado'
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.manifestacao.manifestacao_xml import gerar_xml_evento
from app.modules.manifestacao.repo import ManifestacaoRepo
from app.shared.crypto.xmldsig import XmldsigSigner, XmldsigSigningError
from app.shared.db.models import ManifestacaoNFe
from app.shared.exceptions import (
    ManifestacaoAssinaturaIndisponivel,
    ManifestacaoNaoEncontrada,
    ManifestacaoTransmissaoDesativada,
)
from app.shared.integrations.sefaz_mde.provider import SefazMdeProvider
from app.shared.integrations.sefaz_mde.types import ResultadoTransmissaoEvento
from app.shared.storage.backend import ObjectStorage

log = structlog.get_logger(__name__)

ALGORITMO_VERSAO = "mde.transmissao.v1"

# Namespace UUID5 para idempotência do evento MD-e.
# Distinto dos namespaces do eSocial e EFD-Reinf para evitar colisão
# entre sistemas distintos que usam a mesma lógica UUID5.
_NS_EVENTO_MDE: UUID = UUID("a3b4c5d6-e7f8-4901-b234-c56789012345")


class TransmissaoManifestacaoService:
    """Pipeline de transmissão de evento MD-e ao SEFAZ RecepcaoEvento.

    DI-first: ``signer``, ``provider``, ``storage`` são injetados pelo
    caller. O router constrói os objetos via factories (cert + settings),
    os testes injetam fakes — sem acoplamento a implementações concretas.
    """

    async def transmitir(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        manifestacao_id: UUID,
        *,
        signer: XmldsigSigner,
        provider: SefazMdeProvider,
        storage: ObjectStorage,
        transmissao_ativa: bool,
        tp_amb: str = "1",
    ) -> ManifestacaoNFe:
        """Pipeline completo: assina → grava XML → transmite → grava recibo.

        Args:
            session: sessão async com RLS ativo (SET LOCAL app.tenant_id).
            tenant_id: UUID do tenant (herdado do JWT).
            empresa_id: UUID da empresa que manifesta.
            manifestacao_id: UUID da manifestação a transmitir.
            signer: assinador XMLDSig injetado (DI). Pode ser Fake nos testes.
            provider: provider SEFAZ MD-e injetado (DI). Pode ser Fake nos testes.
            storage: object storage injetado (DI). MemoryStorage nos testes.
            transmissao_ativa: flag §8.12 (False = fail-closed 412).
            tp_amb: ambiente SEFAZ ('1'=produção, '2'=homologação). Default '1'.

        Returns:
            ``ManifestacaoNFe`` com status atualizado ('aceito' ou 'rejeitado').
            Se a manifestação já estava 'aceita'/'transmitida', retorna
            como está (idempotência §8.9).

        Raises:
            ManifestacaoTransmissaoDesativada: flag opt-in desligada (412).
            ManifestacaoNaoEncontrada: manifestação não existe (404).
            ManifestacaoAssinaturaIndisponivel: cert A1 ausente ou assinador
                indisponível (412). Status fica 'preparado' (fail-soft §8.12).
        """
        # ── 1. Fail-closed §8.12 ─────────────────────────────────────────────
        if not transmissao_ativa:
            raise ManifestacaoTransmissaoDesativada(
                "MANIFESTACAO_TRANSMISSAO_ATIVA=false — habilite no .env "
                "quando cert A1 ICP-Brasil e credenciais SEFAZ estiverem "
                "prontos para produção. Baixe os XMLs para transmissão manual "
                "(§8.12)."
            )

        repo = ManifestacaoRepo(session)

        # ── 2. Carregar manifestação ─────────────────────────────────────────
        manifestacao = await repo.por_id(manifestacao_id)
        if manifestacao is None:
            raise ManifestacaoNaoEncontrada(
                f"Manifestação {manifestacao_id} não encontrada."
            )
        if manifestacao.empresa_id != empresa_id:
            # RLS cobre cross-tenant; este check é defesa extra cross-empresa.
            raise ManifestacaoNaoEncontrada(
                f"Manifestação {manifestacao_id} não pertence à empresa {empresa_id}."
            )

        # ── 3. Idempotência: já concluída → no-op §8.9 ──────────────────────
        if manifestacao.status in ("aceito", "transmitido"):
            log.info(
                "manifestacao.transmissao.idempotente",
                manifestacao_id=str(manifestacao_id),
                status=manifestacao.status,
            )
            return manifestacao

        # ── 4. Re-gerar XML canônico a partir dos dados persistidos ──────────
        # Usa ``criado_em`` como ``dh_evento`` para manter determinismo
        # entre chamadas: o Id do infEvento é baseado em tipo/chave/seq
        # (não muda), e dhEvento não afeta a deduplicação pelo SEFAZ.
        xml_str, id_infevento = gerar_xml_evento(
            cnpj_destinatario=manifestacao.cnpj_destinatario,
            chave_nfe=manifestacao.chave_nfe,
            tipo_evento=manifestacao.tipo_evento,
            sequencial=manifestacao.sequencial,
            tp_amb=tp_amb,
            dh_evento=manifestacao.criado_em,
            justificativa=manifestacao.justificativa,
        )

        log.debug(
            "manifestacao.transmissao.xml_gerado",
            manifestacao_id=str(manifestacao_id),
            id_infevento=id_infevento,
        )

        # ── 5. Assinar XMLDSig (fail-soft §8.12) ────────────────────────────
        try:
            xml_assinado_bytes = signer.assinar(xml_str, id_referencia=id_infevento)
        except XmldsigSigningError as exc:
            # Fail-soft: sem cert/grupo opt-in, status fica 'preparado'.
            # O caller verifica o status retornado — não é exceção de negócio
            # silenciosa, mas é controlada (412).
            log.warning(
                "manifestacao.transmissao.assinatura.indisponivel",
                manifestacao_id=str(manifestacao_id),
                empresa_id=str(empresa_id),
                motivo=str(exc),
            )
            raise ManifestacaoAssinaturaIndisponivel(str(exc)) from exc

        # ── 6. Gravar XML assinado no object storage ─────────────────────────
        storage_key_xml = (
            manifestacao.xml_evento_storage_key
            or (
                f"tenant/{tenant_id}/empresa/{empresa_id}/manifestacao/"
                f"{manifestacao.chave_nfe}/{manifestacao.tipo_evento}/"
                f"{manifestacao.sequencial:02d}.xml"
            )
        )
        await storage.put_bytes(
            storage_key_xml,
            xml_assinado_bytes,
            content_type="application/xml",
        )
        manifestacao.xml_evento_storage_key = storage_key_xml
        manifestacao.assinado_em = manifestacao.assinado_em or datetime.now(UTC)

        log.info(
            "manifestacao.transmissao.xml_gravado",
            manifestacao_id=str(manifestacao_id),
            storage_key=storage_key_xml,
        )

        # ── 7. Transmitir ao SEFAZ via provider ─────────────────────────────
        idempotency_key = self._idempotency_key(manifestacao)

        resultado: ResultadoTransmissaoEvento = await provider.transmitir_evento(
            manifestacao.cnpj_destinatario,
            xml_assinado_bytes,
            idempotency_key,
        )

        agora = datetime.now(UTC)
        manifestacao.transmitido_em = agora

        log.info(
            "manifestacao.transmissao.enviado",
            manifestacao_id=str(manifestacao_id),
            codigo_status=resultado.codigo_status,
            aceito=resultado.aceito,
            protocolo=resultado.protocolo,
        )

        # ── 8. Gravar recibo no object storage ──────────────────────────────
        if resultado.xml_recibo is not None:
            storage_key_recibo = (
                f"tenant/{tenant_id}/empresa/{empresa_id}/manifestacao/"
                f"{manifestacao.chave_nfe}/{manifestacao.tipo_evento}/"
                f"{manifestacao.sequencial:02d}_recibo.xml"
            )
            await storage.put_bytes(
                storage_key_recibo,
                resultado.xml_recibo,
                content_type="application/xml",
            )
            manifestacao.xml_recibo_storage_key = storage_key_recibo

            log.info(
                "manifestacao.transmissao.recibo_gravado",
                manifestacao_id=str(manifestacao_id),
                storage_key=storage_key_recibo,
                bytes=len(resultado.xml_recibo),
            )

        # ── 9. Atualizar status final §8.2 ───────────────────────────────────
        manifestacao.status = "aceito" if resultado.aceito else "rejeitado"
        manifestacao.protocolo = resultado.protocolo
        manifestacao.codigo_status_sefaz = resultado.codigo_status
        manifestacao.motivo_sefaz = resultado.motivo
        manifestacao.respondido_em = agora

        await session.commit()
        await session.refresh(manifestacao)

        log.info(
            "manifestacao.transmissao.concluida",
            manifestacao_id=str(manifestacao_id),
            empresa_id=str(empresa_id),
            status=manifestacao.status,
            protocolo=manifestacao.protocolo,
            codigo_status=resultado.codigo_status,
        )

        return manifestacao

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _idempotency_key(self, manifestacao: ManifestacaoNFe) -> str:
        """UUID5 estável sobre (empresa_id, chave_nfe, tipo_evento, sequencial).

        Garante deduplicação no SEFAZ mesmo em caso de retry (§8.9).
        Namespace distinto do eSocial e EFD-Reinf para evitar colisão
        entre sistemas.
        """
        nome = (
            f"{manifestacao.empresa_id}|"
            f"{manifestacao.chave_nfe}|"
            f"{manifestacao.tipo_evento}|"
            f"{manifestacao.sequencial}"
        )
        return str(uuid5(_NS_EVENTO_MDE, nome))
