"""Orquestrador do pipeline de transmissão EFD-Reinf (Marco 4 PR2 #11).

Camada 2 (imperative shell). Espelha ``TransmissaoEsocialService``.
Coordena os estágios:

  1. **Preparar** — busca evento `status='preparado'`, materializa XML
     canônico via ``reinf_xml.serializar_para_xml``.
  2. **Assinar** — aplica XMLDSig via ``XmldsigSigner`` (fail-soft: sem
     cert/flag, evento fica em `status='preparado'` com warning).
  3. **Empacotar** — agrupa até ``REINF_LOTE_MAX_EVENTOS`` eventos da
     empresa num lote.
  4. **Enviar** — POST de recepção via ``ReinfClient``. Idempotency key =
     UUID5 sobre o conjunto ordenado de ``id_evento``.
  5. **Poll recibo** — consulta o protocolo; aplica status final por evento.

**Princípios cravados:**

  * §8.2 — XML assinado é imutável; status final atualiza só metadados
    operacionais (`transmitido_em`, `processado_em`).
  * §8.9 — idempotency_key UUID5 garante que reenviar o mesmo lote devolve
    o mesmo protocolo (a recepção EFD-Reinf deduplica).
  * §8.12 — flag ``REINF_TRANSMISSAO_ATIVA`` decide se o pipeline chega à
    etapa 4. Sem ela, evento fica em `status='assinado'` pronto pra admin
    baixar e transmitir manualmente. Default False até admin opt-in.

Aceitação por evento: EFD-Reinf emite ``nrRecibo`` apenas para eventos
aceitos. O service marca ``aceito`` quando há ``numero_recibo``; senão
``rejeitado`` (com as ocorrências na ``resposta``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final
from uuid import UUID, uuid5

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.reinf.reinf_xml import serializar_para_xml
from app.modules.reinf.repo import EfdReinfRepo
from app.shared.crypto.xmldsig import (
    XmldsigSigner,
    XmldsigSigningError,
    hash_xml_canonico,
)
from app.shared.db.models import EfdReinfEvento
from app.shared.exceptions import (
    ReinfAssinaturaIndisponivel,
    ReinfErroAPI,
    ReinfEventoNaoEncontrado,
    ReinfLoteInvalido,
    ReinfTransmissaoDesativada,
)
from app.shared.integrations.reinf.client import ReinfClient, ReinfError
from app.shared.integrations.reinf.types import EventoLote, ReciboLote

log = structlog.get_logger(__name__)

ALGORITMO_VERSAO: Final = "reinf.transmissao.v1"

# Namespace UUID5 — idempotência do lote (distinto do eSocial).
_NS_LOTE_REINF: Final = UUID("7c1d2e3f-9b8a-4c6d-bf0e-1a2b3c4d5e6f")


class TransmissaoReinfService:
    """Orquestra assinatura + envio + poll de recibo de eventos EFD-Reinf."""

    def __init__(
        self,
        *,
        settings: Settings,
        assinador: XmldsigSigner,
        cliente: ReinfClient,
    ) -> None:
        self._settings = settings
        self._assinador = assinador
        self._cliente = cliente

    # ── Estágio 1+2: serializar + assinar ───────────────────────────────

    async def assinar_evento(
        self,
        session: AsyncSession,
        evento_id: UUID,
    ) -> EfdReinfEvento:
        """Materializa XML + aplica XMLDSig + persiste hash + bytes.

        Fail-soft: ``NotImplementedXmldsigSigner`` levanta
        ``XmldsigSigningError`` → service traduz em
        ``ReinfAssinaturaIndisponivel`` (HTTP 412), preservando evento em
        ``status='preparado'`` pra retry após admin opt-in.
        """
        repo = EfdReinfRepo(session)
        evento = await repo.por_id(evento_id)
        if evento is None:
            raise ReinfEventoNaoEncontrado(
                f"Evento EFD-Reinf {evento_id} não encontrado"
            )
        if evento.status not in ("preparado", "rejeitado_xsd"):
            log.warning(
                "reinf.assinar.status_invalido",
                evento_id=str(evento_id),
                status=evento.status,
            )
            return evento

        # Serializa XML canônico (Camada 1 pura).
        try:
            xml_canonico = serializar_para_xml(evento.payload)
        except ValueError as exc:
            evento.status = "rejeitado_xsd"
            evento.resposta = {"erro_serializacao": str(exc)}
            await session.commit()
            raise ReinfLoteInvalido(
                f"Payload de evento {evento_id} inválido: {exc}"
            ) from exc

        evento.hash_xml = hash_xml_canonico(xml_canonico)
        id_referencia = self._extrair_id_evento(xml_canonico)

        # Aplica XMLDSig — pode levantar XmldsigSigningError.
        try:
            xml_assinado = self._assinador.assinar(
                xml_canonico, id_referencia=id_referencia
            )
        except XmldsigSigningError as exc:
            log.warning(
                "reinf.assinar.indisponivel",
                evento_id=str(evento_id),
                motivo=str(exc),
            )
            await session.commit()  # persiste hash_xml mesmo sem assinar
            raise ReinfAssinaturaIndisponivel(str(exc)) from exc

        evento.xml_assinado = xml_assinado
        evento.status = "assinado"
        await session.commit()
        await session.refresh(evento)
        log.info(
            "reinf.assinado",
            evento_id=str(evento_id),
            tipo=evento.tipo_evento,
            hash_xml=evento.hash_xml,
        )
        return evento

    # ── Estágio 3+4+5: empacotar + enviar + poll ────────────────────────

    async def transmitir_lote(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        *,
        cnpj_contribuinte: str,
    ) -> ReciboLote | None:
        """Pipeline completo de uma rodada de transmissão.

        Coleta eventos ``status='assinado'`` da empresa (até
        ``REINF_LOTE_MAX_EVENTOS``), envia, atualiza ``status='em_lote'`` +
        ``lote_protocolo``, faz uma única consulta inicial de recibo. Poll
        posterior é responsabilidade do worker Celery.

        Returns:
            ReciboLote da consulta inicial, ou ``None`` se não havia
            eventos pendentes.

        Raises:
            ReinfTransmissaoDesativada: flag opt-in desligada (412).
            ReinfErroAPI: API EFD-Reinf respondeu 4xx/5xx (502).
            ReinfLoteInvalido: evento sem xml_assinado.
        """
        if not self._settings.REINF_TRANSMISSAO_ATIVA:
            raise ReinfTransmissaoDesativada(
                "REINF_TRANSMISSAO_ATIVA=false — habilite no .env "
                "ou baixe XMLs pra transmissão manual (§8.12)."
            )

        repo = EfdReinfRepo(session)
        eventos_db = await repo.listar_por_status(
            empresa_id,
            status="assinado",
            limite=self._cliente.max_eventos_por_lote,
        )
        if not eventos_db:
            log.info("reinf.lote.sem_pendentes", empresa_id=str(empresa_id))
            return None

        # Empacota.
        pacote: list[EventoLote] = []
        for ev in eventos_db:
            if ev.xml_assinado is None:
                raise ReinfLoteInvalido(
                    f"Evento {ev.id} marcado como assinado mas sem xml_assinado"
                )
            id_ref = self._extrair_id_evento(
                ev.xml_assinado.decode("utf-8", errors="replace")
            )
            pacote.append(
                EventoLote(id_evento=id_ref, xml_assinado=ev.xml_assinado)
            )

        idempotency_key = self._idempotency_key_do_lote(pacote)

        # Envia.
        try:
            lote = await self._cliente.enviar_lote(
                tuple(pacote),
                cnpj_contribuinte=cnpj_contribuinte,
                idempotency_key=idempotency_key,
            )
        except ReinfError as exc:
            raise ReinfErroAPI(f"Falha no envio: {exc}") from exc

        # Atualiza status dos eventos enviados.
        agora = datetime.now(UTC)
        for ev in eventos_db:
            ev.status = "em_lote"
            ev.lote_protocolo = lote.protocolo
            ev.transmitido_em = agora
        await session.commit()

        log.info(
            "reinf.lote.transmitido",
            empresa_id=str(empresa_id),
            protocolo=lote.protocolo,
            total_eventos=len(eventos_db),
            idempotency_key=idempotency_key,
        )

        # Tentativa imediata de poll.
        try:
            return await self._cliente.consultar_recibo(lote.protocolo)
        except ReinfError as exc:
            log.warning(
                "reinf.recibo.poll_inicial_falhou",
                protocolo=lote.protocolo,
                erro=str(exc),
            )
            return None

    async def aplicar_recibo(
        self,
        session: AsyncSession,
        recibo: ReciboLote,
    ) -> int:
        """Aplica recibo aos eventos do lote — atualiza status final.

        Returns:
            Quantidade de eventos atualizados.
        """
        repo = EfdReinfRepo(session)
        eventos = await repo.listar_por_lote(recibo.protocolo)
        if not eventos:
            log.warning(
                "reinf.recibo.lote_sem_eventos",
                protocolo=recibo.protocolo,
            )
            return 0

        por_id = {r.id_evento: r for r in recibo.eventos}
        agora = datetime.now(UTC)
        atualizados = 0
        for ev in eventos:
            id_ref = (
                self._extrair_id_evento(
                    ev.xml_assinado.decode("utf-8", errors="replace")
                )
                if ev.xml_assinado
                else None
            )
            retorno = por_id.get(id_ref) if id_ref else None
            if retorno is None and not recibo.finalizado:
                # ainda processando — skip
                continue
            if retorno is None:
                # finalizado mas sem retorno desse evento — rejeição de lote
                ev.status = "rejeitado"
                ev.resposta = {"erro": "sem retorno individual no lote"}
                ev.processado_em = agora
                atualizados += 1
                continue
            ev.recibo_numero = retorno.numero_recibo
            ev.resposta = {
                "codigo_retorno": retorno.codigo_retorno,
                "descricao": retorno.descricao,
                "ocorrencias": list(retorno.ocorrencias),
            }
            # EFD-Reinf: recibo presente = aceito; ausente = rejeitado.
            ev.status = "aceito" if retorno.numero_recibo else "rejeitado"
            ev.processado_em = agora
            atualizados += 1

        if atualizados > 0:
            await session.commit()
        log.info(
            "reinf.recibo.aplicado",
            protocolo=recibo.protocolo,
            estado=int(recibo.estado),
            atualizados=atualizados,
        )
        return atualizados

    # ── Helpers ──────────────────────────────────────────────────────────

    def _extrair_id_evento(self, xml: str) -> str:
        """Extrai o atributo ``Id`` do `<evt*>` raiz (pra <ds:Reference>)."""
        import re

        m = re.search(r"""<evt[^>]+\bId=['"]([A-Za-z0-9]+)['"]""", xml)
        if not m:
            raise ReinfLoteInvalido(
                "XML do evento sem atributo Id no <evt*> raiz"
            )
        return m.group(1)

    def _idempotency_key_do_lote(self, pacote: list[EventoLote]) -> str:
        """UUID5 estável sobre o conjunto ordenado de id_evento."""
        nome = "|".join(sorted(ev.id_evento for ev in pacote))
        return str(uuid5(_NS_LOTE_REINF, nome))
