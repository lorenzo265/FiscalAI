"""Cliente HTTP eSocial — envio de lote + consulta de recibo.

Sprint 19.7 PR2 (#13). Camada 4 (integrações externas).

API oficial eSocial expõe SOAP+XML — esta implementação adota o WS
RESTful equivalente (mesmas operações canônicas, payload XML):

  * ``POST {base}/lotes/eventos`` — envia até 50 eventos por lote
    (limite oficial). Retorna ``nrProtocolo``.

  * ``GET  {base}/lotes/eventos/{protocolo}`` — consulta status de
    processamento + recibos individuais por evento.

Idempotência §8.9: o lote inteiro envia com header
``X-Idempotency-Key`` (deduplicado pelo serviço; mesma chave devolve o
mesmo ``nrProtocolo`` sem reprocessar). Service eSocial gera a chave
via UUID5 sobre o conjunto ordenado de ``id_evento`` do lote.

Sandbox vs prod: controlado por ``ESOCIAL_SANDBOX`` (default True =
produção restrita / tpAmb=2). Flag ``ESOCIAL_TRANSMISSAO_ATIVA`` é
**superior** — service nunca instancia este cliente sem ela.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405 — usado só para construir/serializar XML
from datetime import UTC, datetime
from typing import Final

import defusedxml.ElementTree as _dET  # para parsear respostas externas (XXE-safe)
import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import Settings
from app.shared.integrations.esocial.types import (
    EstadoLote,
    EventoLote,
    LoteEnviado,
    ReciboEvento,
    ReciboLote,
)

ALGORITMO_VERSAO: Final = "esocial.client.v1"

log = structlog.get_logger(__name__)

_NS_ENVIO: Final = "http://www.esocial.gov.br/schema/lote/eventos/envio/v1_1_1"


class EsocialError(RuntimeError):
    """Erro irrecuperável do eSocial (4xx/5xx ou XML inválido)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class EsocialClient:
    """Cliente assíncrono para a API eSocial.

    Idempotência: ``enviar_lote`` aceita ``idempotency_key`` (header
    ``X-Idempotency-Key``) — eSocial deduplica internamente.
    Retry: apenas erros de transporte (httpx.TransportError).
    """

    def __init__(
        self,
        settings: Settings,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = (
            settings.ESOCIAL_BASE_URL_SANDBOX
            if settings.ESOCIAL_SANDBOX
            else settings.ESOCIAL_BASE_URL_PROD
        )
        self._sandbox = settings.ESOCIAL_SANDBOX
        self._max_eventos = settings.ESOCIAL_LOTE_MAX_EVENTOS
        self._http = http or httpx.AsyncClient(
            timeout=float(settings.ESOCIAL_TIMEOUT_SEC),
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
        cnpj_empregador: str,
    ) -> bytes:
        """Monta `<eSocial xmlns="...envio/v1_1_1"><envioLoteEventos...>`.

        Função pura (apesar de instance method) — facilita golden test.
        """
        if not eventos:
            raise EsocialError("Lote vazio — passe pelo menos um evento")
        if len(eventos) > self._max_eventos:
            raise EsocialError(
                f"Lote excede o máximo oficial de {self._max_eventos} eventos"
            )

        root = ET.Element("eSocial", {"xmlns": _NS_ENVIO})
        envio = ET.SubElement(root, "envioLoteEventos", {"grupo": "1"})
        ide_emp = ET.SubElement(envio, "ideEmpregador")
        ET.SubElement(ide_emp, "tpInsc").text = "1"
        ET.SubElement(ide_emp, "nrInsc").text = cnpj_empregador

        ide_trans = ET.SubElement(envio, "ideTransmissor")
        ET.SubElement(ide_trans, "tpInsc").text = "1"
        ET.SubElement(ide_trans, "nrInsc").text = cnpj_empregador

        eventos_el = ET.SubElement(envio, "eventos")
        for ev in eventos:
            evento = ET.SubElement(eventos_el, "evento", {"Id": ev.id_evento})
            # Injeta o XML do evento como sub-tree.
            try:
                sub: ET.Element = _dET.fromstring(ev.xml_assinado)
            except ET.ParseError as exc:
                raise EsocialError(
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
        cnpj_empregador: str,
        idempotency_key: str,
    ) -> LoteEnviado:
        """POST /lotes/eventos — envia até ``max_eventos_por_lote``.

        Idempotente via ``X-Idempotency-Key``.

        Returns:
            LoteEnviado com ``protocolo`` e estado inicial=1 (ENVIADO).
        """
        url = f"{self._base}/lotes/eventos"
        envelope = self.construir_envelope_lote(
            eventos, cnpj_empregador=cnpj_empregador
        )
        try:
            resp = await self._http.post(
                url,
                content=envelope,
                headers={"X-Idempotency-Key": idempotency_key},
            )
        except httpx.TransportError as exc:
            raise EsocialError(f"Transport error no envio: {exc}") from exc

        if resp.status_code not in (200, 201, 202):
            raise EsocialError(
                f"eSocial respondeu {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )

        protocolo = self._parse_protocolo(resp.text)
        log.info(
            "esocial.lote.enviado",
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
        """GET /lotes/eventos/{protocolo} — polling do estado.

        Estado 1/2 = ainda processando; 3/4/5 = finalizado.
        """
        url = f"{self._base}/lotes/eventos/{protocolo}"
        try:
            resp = await self._http.get(url)
        except httpx.TransportError as exc:
            raise EsocialError(
                f"Transport error na consulta: {exc}"
            ) from exc

        if resp.status_code == 404:
            raise EsocialError(
                f"Protocolo {protocolo!r} não encontrado",
                status_code=404,
            )
        if resp.status_code != 200:
            raise EsocialError(
                f"eSocial respondeu {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )

        recibo = self._parse_recibo(resp.text, protocolo=protocolo)
        log.info(
            "esocial.recibo.consultado",
            protocolo=protocolo,
            estado=int(recibo.estado),
            total_eventos=len(recibo.eventos),
        )
        return recibo

    # ── Parsing ──────────────────────────────────────────────────────────

    def _parse_protocolo(self, xml: str) -> str:
        try:
            doc: ET.Element = _dET.fromstring(xml)
        except ET.ParseError as exc:
            raise EsocialError(
                f"Resposta de envio não-XML: {exc}"
            ) from exc
        # Schema oficial: <retornoEnvioLoteEventos><dadosRecepcaoLote><protocoloEnvio>.
        for el in doc.iter():
            tag = el.tag.split("}", 1)[-1]
            if tag in ("protocoloEnvio", "nrProtocolo") and el.text:
                return el.text.strip()
        raise EsocialError("Resposta de envio sem 'protocoloEnvio'")

    def _parse_recibo(self, xml: str, *, protocolo: str) -> ReciboLote:
        try:
            doc: ET.Element = _dET.fromstring(xml)
        except ET.ParseError as exc:
            raise EsocialError(
                f"Resposta de recibo não-XML: {exc}"
            ) from exc

        estado_raw: int | None = None
        eventos: list[ReciboEvento] = []
        for el in doc.iter():
            tag = el.tag.split("}", 1)[-1]
            if tag == "cdResposta" and el.text and estado_raw is None:
                try:
                    estado_raw = int(el.text.strip())
                except ValueError as exc:
                    raise EsocialError(
                        f"cdResposta não numérico: {el.text!r}"
                    ) from exc
            if tag == "retornoEvento":
                eventos.append(self._parse_retorno_evento(el))

        try:
            estado = EstadoLote(estado_raw) if estado_raw is not None else EstadoLote.EM_PROCESSAMENTO
        except ValueError as exc:
            raise EsocialError(
                f"cdResposta inválido: {estado_raw}"
            ) from exc

        return ReciboLote(
            protocolo=protocolo,
            estado=estado,
            consultado_em=datetime.now(UTC),
            eventos=tuple(eventos),
        )

    def _parse_retorno_evento(self, el: ET.Element) -> ReciboEvento:
        id_evento = el.attrib.get("Id", "")
        numero_recibo: str | None = None
        codigo: str = ""
        descricao: str = ""
        ocorrencias: list[str] = []
        for child in el.iter():
            tag = child.tag.split("}", 1)[-1]
            if tag == "nrRecibo" and child.text:
                numero_recibo = child.text.strip()
            elif tag == "cdResposta" and child.text and not codigo:
                codigo = child.text.strip()
            elif tag == "descResposta" and child.text and not descricao:
                descricao = child.text.strip()
            elif tag == "ocorrencia" and child.text:
                ocorrencias.append(child.text.strip())
        return ReciboEvento(
            id_evento=id_evento,
            numero_recibo=numero_recibo,
            codigo_retorno=codigo or "??",
            descricao=descricao,
            ocorrencias=tuple(ocorrencias),
        )
