"""Cliente HTTP EFD-Reinf — envio de lote assíncrono + consulta de recibo.

Marco 4 PR2 (#11). Camada 4 (integrações externas). Espelha o
``EsocialClient`` (Sprint 19.7 PR2) — mesmas operações canônicas, payload
XML, idempotência §8.9.

A API EFD-Reinf expõe a recepção assíncrona de lote de eventos (leiaute
v2.1.2):

  * ``POST {base}/recepcao/lotes`` — envia um lote de eventos assinados.
    Retorna o ``protocoloEnvio`` do lote.
  * ``GET  {base}/consulta/lotes/{protocolo}`` — consulta o andamento do
    processamento + recibos individuais por evento.

Idempotência §8.9: o lote envia com header ``X-Idempotency-Key`` (mesma
chave devolve o mesmo protocolo). O service gera a chave via UUID5 sobre o
conjunto ordenado de ``id_evento`` do lote.

Sandbox vs prod: ``REINF_SANDBOX`` (default True = produção restrita /
tpAmb=2). A flag ``REINF_TRANSMISSAO_ATIVA`` é **superior** — o service
nunca instancia este cliente sem ela.

> Os tags/endpoints exatos do leiaute devem ser confirmados no Manual
> EFD-Reinf antes de produção; o parser é tolerante a aliases comuns.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405 — usado só para construir/serializar XML próprio
from datetime import UTC, datetime
from typing import Final

import defusedxml.ElementTree as _dET  # parseia respostas externas (XXE-safe)
import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import Settings
from app.shared.integrations.reinf.types import (
    EstadoLote,
    EventoLote,
    LoteEnviado,
    ReciboEvento,
    ReciboLote,
)

ALGORITMO_VERSAO: Final = "reinf.client.v1"

log = structlog.get_logger(__name__)

_NS_ENVIO: Final = (
    "http://www.reinf.esocial.gov.br/schemas/envioLoteEventosAssincrono/v1_00_00"
)


class ReinfError(RuntimeError):
    """Erro irrecuperável do EFD-Reinf (4xx/5xx ou XML inválido)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ReinfClient:
    """Cliente assíncrono para a API EFD-Reinf.

    Idempotência: ``enviar_lote`` aceita ``idempotency_key`` (header
    ``X-Idempotency-Key``). Retry: apenas erros de transporte.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = (
            settings.REINF_BASE_URL_SANDBOX
            if settings.REINF_SANDBOX
            else settings.REINF_BASE_URL_PROD
        )
        self._sandbox = settings.REINF_SANDBOX
        self._max_eventos = settings.REINF_LOTE_MAX_EVENTOS
        self._http = http or httpx.AsyncClient(
            timeout=float(settings.REINF_TIMEOUT_SEC),
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )

    @property
    def tpAmb(self) -> int:
        """Código do ambiente (1=prod, 2=produção restrita/sandbox)."""
        return 2 if self._sandbox else 1

    @property
    def max_eventos_por_lote(self) -> int:
        return self._max_eventos

    async def aclose(self) -> None:
        await self._http.aclose()

    def construir_envelope_lote(
        self,
        eventos: tuple[EventoLote, ...],
        *,
        cnpj_contribuinte: str,
    ) -> bytes:
        """Monta `<Reinf xmlns="...assincrono"><envioLoteEventos>...`.

        Função pura (apesar de instance method) — facilita golden test.
        """
        if not eventos:
            raise ReinfError("Lote vazio — passe pelo menos um evento")
        if len(eventos) > self._max_eventos:
            raise ReinfError(
                f"Lote excede o máximo de {self._max_eventos} eventos"
            )

        root = ET.Element("Reinf", {"xmlns": _NS_ENVIO})
        envio = ET.SubElement(root, "envioLoteEventos")
        ide_contri = ET.SubElement(envio, "ideContribuinte")
        ET.SubElement(ide_contri, "tpInsc").text = "1"
        ET.SubElement(ide_contri, "nrInsc").text = cnpj_contribuinte

        eventos_el = ET.SubElement(envio, "eventos")
        for ev in eventos:
            evento = ET.SubElement(eventos_el, "evento", {"id": ev.id_evento})
            try:
                sub: ET.Element = _dET.fromstring(ev.xml_assinado)
            except ET.ParseError as exc:
                raise ReinfError(
                    f"XML do evento {ev.id_evento} inválido pra empacotamento: {exc}"
                ) from exc
            evento.append(sub)

        out = ET.tostring(root, encoding="utf-8", short_empty_elements=False)
        return bytes(out)

    @retry(
        wait=wait_exponential_jitter(initial=2, max=30),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def enviar_lote(
        self,
        eventos: tuple[EventoLote, ...],
        *,
        cnpj_contribuinte: str,
        idempotency_key: str,
    ) -> LoteEnviado:
        """POST /recepcao/lotes — envia até ``max_eventos_por_lote``.

        Idempotente via ``X-Idempotency-Key``.
        """
        url = f"{self._base}/recepcao/lotes"
        envelope = self.construir_envelope_lote(
            eventos, cnpj_contribuinte=cnpj_contribuinte
        )
        try:
            resp = await self._http.post(
                url,
                content=envelope,
                headers={"X-Idempotency-Key": idempotency_key},
            )
        except httpx.TransportError as exc:
            raise ReinfError(f"Transport error no envio: {exc}") from exc

        if resp.status_code not in (200, 201, 202):
            raise ReinfError(
                f"EFD-Reinf respondeu {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )

        protocolo = self._parse_protocolo(resp.text)
        log.info(
            "reinf.lote.enviado",
            protocolo=protocolo,
            total_eventos=len(eventos),
            idempotency_key=idempotency_key,
        )
        return LoteEnviado(
            protocolo=protocolo,
            enviado_em=datetime.now(UTC),
            estado=EstadoLote.ENVIADO,
        )

    @retry(
        wait=wait_exponential_jitter(initial=2, max=30),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def consultar_recibo(self, protocolo: str) -> ReciboLote:
        """GET /consulta/lotes/{protocolo} — polling do estado.

        Estado 1/2 = ainda processando; 3/4/5 = finalizado.
        """
        url = f"{self._base}/consulta/lotes/{protocolo}"
        try:
            resp = await self._http.get(url)
        except httpx.TransportError as exc:
            raise ReinfError(f"Transport error na consulta: {exc}") from exc

        if resp.status_code == 404:
            raise ReinfError(
                f"Protocolo {protocolo!r} não encontrado",
                status_code=404,
            )
        if resp.status_code != 200:
            raise ReinfError(
                f"EFD-Reinf respondeu {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )

        recibo = self._parse_recibo(resp.text, protocolo=protocolo)
        log.info(
            "reinf.recibo.consultado",
            protocolo=protocolo,
            estado=int(recibo.estado),
            total_eventos=len(recibo.eventos),
        )
        return recibo

    # ── Parsing (tolerante a aliases do leiaute) ─────────────────────────

    def _parse_protocolo(self, xml: str) -> str:
        try:
            doc: ET.Element = _dET.fromstring(xml)
        except ET.ParseError as exc:
            raise ReinfError(f"Resposta de envio não-XML: {exc}") from exc
        for el in doc.iter():
            tag = el.tag.split("}", 1)[-1]
            if tag in ("protocoloEnvio", "nrProtocolo", "protocolo") and el.text:
                return el.text.strip()
        raise ReinfError("Resposta de envio sem 'protocoloEnvio'")

    def _parse_recibo(self, xml: str, *, protocolo: str) -> ReciboLote:
        try:
            doc: ET.Element = _dET.fromstring(xml)
        except ET.ParseError as exc:
            raise ReinfError(f"Resposta de recibo não-XML: {exc}") from exc

        estado_raw: int | None = None
        eventos: list[ReciboEvento] = []
        for el in doc.iter():
            tag = el.tag.split("}", 1)[-1]
            if tag in ("cdStatus", "cdResposta") and el.text and estado_raw is None:
                try:
                    estado_raw = int(el.text.strip())
                except ValueError as exc:
                    raise ReinfError(
                        f"código de status não numérico: {el.text!r}"
                    ) from exc
            if tag in ("retornoEvento", "evento"):
                evt = self._parse_retorno_evento(el)
                if evt is not None:
                    eventos.append(evt)

        try:
            estado = (
                EstadoLote(estado_raw)
                if estado_raw is not None
                else EstadoLote.EM_PROCESSAMENTO
            )
        except ValueError as exc:
            raise ReinfError(f"código de status inválido: {estado_raw}") from exc

        return ReciboLote(
            protocolo=protocolo,
            estado=estado,
            consultado_em=datetime.now(UTC),
            eventos=tuple(eventos),
        )

    def _parse_retorno_evento(self, el: ET.Element) -> ReciboEvento | None:
        id_evento = el.attrib.get("id") or el.attrib.get("Id") or ""
        numero_recibo: str | None = None
        codigo: str = ""
        descricao: str = ""
        ocorrencias: list[str] = []
        for child in el.iter():
            tag = child.tag.split("}", 1)[-1]
            if tag == "nrRecibo" and child.text:
                numero_recibo = child.text.strip()
            elif tag in ("cdRetorno", "cdResposta") and child.text and not codigo:
                codigo = child.text.strip()
            elif tag in ("descRetorno", "descResposta") and child.text and not descricao:
                descricao = child.text.strip()
            elif tag in ("ocorrencia", "descricao") and child.text:
                ocorrencias.append(child.text.strip())
        # Um <evento> de wrapper sem nenhum dado de retorno não é recibo.
        if not id_evento and numero_recibo is None and not codigo:
            return None
        return ReciboEvento(
            id_evento=id_evento,
            numero_recibo=numero_recibo,
            codigo_retorno=codigo or "??",
            descricao=descricao,
            ocorrencias=tuple(ocorrencias),
        )
