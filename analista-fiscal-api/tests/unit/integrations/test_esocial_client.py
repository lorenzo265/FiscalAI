"""Testes do EsocialClient (Sprint 19.7 PR2 #13).

Cobre:
  * Construção do envelope <eSocial><envioLoteEventos>.
  * Limite oficial de 50 eventos por lote.
  * Idempotency-Key no header.
  * Parsing de protocolo e recibo.
  * Mapeamento sandbox/prod.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.config import Settings
from app.shared.integrations.esocial.client import EsocialClient, EsocialError
from app.shared.integrations.esocial.types import EstadoLote, EventoLote


def _settings(**over: object) -> Settings:
    defaults: dict[str, object] = {
        "ESOCIAL_TRANSMISSAO_ATIVA": True,
        "ESOCIAL_SANDBOX": True,
        "ESOCIAL_BASE_URL_SANDBOX": "https://ws.sandbox.esocial.test",
        "ESOCIAL_BASE_URL_PROD": "https://ws.prod.esocial.test",
        "ESOCIAL_LOTE_MAX_EVENTOS": 3,
    }
    defaults.update(over)
    return Settings(**defaults)  # type: ignore[arg-type]


def _xml_evt(id_: str = "ID1") -> bytes:
    return (
        f"<eSocial xmlns='ns'><evtRemun Id='{id_}'>"
        "<ideEvento><nrInsc>X</nrInsc></ideEvento>"
        "</evtRemun></eSocial>"
    ).encode()


# ── Construção do envelope ──────────────────────────────────────────────────


def test_envelope_inclui_grupo_e_empregador() -> None:
    client = EsocialClient(_settings(), http=MagicMock(spec=httpx.AsyncClient))
    envelope = client.construir_envelope_lote(
        (EventoLote(id_evento="ID1", xml_assinado=_xml_evt("ID1")),),
        cnpj_empregador="11222333000144",
    )
    s = envelope.decode("utf-8")
    assert "envioLoteEventos" in s
    assert 'grupo="1"' in s
    assert "11222333000144" in s
    assert "ID1" in s


def test_envelope_recusa_lote_vazio() -> None:
    client = EsocialClient(_settings(), http=MagicMock(spec=httpx.AsyncClient))
    with pytest.raises(EsocialError, match="Lote vazio"):
        client.construir_envelope_lote((), cnpj_empregador="11222333000144")


def test_envelope_respeita_max_eventos() -> None:
    client = EsocialClient(_settings(), http=MagicMock(spec=httpx.AsyncClient))
    eventos = tuple(
        EventoLote(id_evento=f"ID{i}", xml_assinado=_xml_evt(f"ID{i}"))
        for i in range(4)  # ESOCIAL_LOTE_MAX_EVENTOS=3
    )
    with pytest.raises(EsocialError, match="excede o máximo"):
        client.construir_envelope_lote(eventos, cnpj_empregador="11222333000144")


def test_envelope_recusa_xml_invalido() -> None:
    client = EsocialClient(_settings(), http=MagicMock(spec=httpx.AsyncClient))
    with pytest.raises(EsocialError, match="inválido"):
        client.construir_envelope_lote(
            (EventoLote(id_evento="ID1", xml_assinado=b"not-xml"),),
            cnpj_empregador="11222333000144",
        )


# ── Sandbox / prod ─────────────────────────────────────────────────────────


def test_base_url_sandbox_default() -> None:
    client = EsocialClient(_settings(), http=MagicMock(spec=httpx.AsyncClient))
    assert client.tpAmb == 2
    assert client.max_eventos_por_lote == 3


def test_base_url_prod_quando_sandbox_false() -> None:
    client = EsocialClient(
        _settings(ESOCIAL_SANDBOX=False),
        http=MagicMock(spec=httpx.AsyncClient),
    )
    assert client.tpAmb == 1


# ── Envio + idempotency ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enviar_lote_passa_idempotency_key_header() -> None:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 201
    response.text = (
        "<retornoEnvioLoteEventos>"
        "<dadosRecepcaoLote>"
        "<protocoloEnvio>PROT-123</protocoloEnvio>"
        "</dadosRecepcaoLote>"
        "</retornoEnvioLoteEventos>"
    )
    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    client = EsocialClient(_settings(), http=http)
    lote = await client.enviar_lote(
        (EventoLote(id_evento="ID1", xml_assinado=_xml_evt("ID1")),),
        cnpj_empregador="11222333000144",
        idempotency_key="key-abc",
    )

    assert lote.protocolo == "PROT-123"
    assert lote.estado == EstadoLote.ENVIADO
    args, kwargs = http.post.call_args
    assert kwargs["headers"]["X-Idempotency-Key"] == "key-abc"


@pytest.mark.asyncio
async def test_enviar_lote_levanta_em_5xx() -> None:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 500
    response.text = "internal error"
    http = MagicMock(spec=httpx.AsyncClient)
    http.post = AsyncMock(return_value=response)

    client = EsocialClient(_settings(), http=http)
    with pytest.raises(EsocialError) as ei:
        await client.enviar_lote(
            (EventoLote(id_evento="ID1", xml_assinado=_xml_evt("ID1")),),
            cnpj_empregador="11222333000144",
            idempotency_key="key",
        )
    assert ei.value.status_code == 500


# ── Consulta de recibo ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consultar_recibo_processado_com_evento_aceito() -> None:
    xml_resp = (
        "<consultaResultadoLote>"
        "<cdResposta>4</cdResposta>"
        "<retornoProcessamento>"
        "<retornoEventos>"
        "<retornoEvento Id='ID1'>"
        "<nrRecibo>1.2.0000000000000123</nrRecibo>"
        "<cdResposta>201</cdResposta>"
        "<descResposta>Sucesso</descResposta>"
        "</retornoEvento>"
        "</retornoEventos>"
        "</retornoProcessamento>"
        "</consultaResultadoLote>"
    )
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.text = xml_resp
    http = MagicMock(spec=httpx.AsyncClient)
    http.get = AsyncMock(return_value=response)

    client = EsocialClient(_settings(), http=http)
    rec = await client.consultar_recibo("PROT-123")

    assert rec.estado == EstadoLote.PROCESSADO
    assert rec.finalizado is True
    assert len(rec.eventos) == 1
    assert rec.eventos[0].id_evento == "ID1"
    assert rec.eventos[0].numero_recibo == "1.2.0000000000000123"
    assert rec.eventos[0].codigo_retorno == "201"


@pytest.mark.asyncio
async def test_consultar_recibo_em_processamento_sem_eventos() -> None:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.text = (
        "<consultaResultadoLote><cdResposta>2</cdResposta></consultaResultadoLote>"
    )
    http = MagicMock(spec=httpx.AsyncClient)
    http.get = AsyncMock(return_value=response)

    client = EsocialClient(_settings(), http=http)
    rec = await client.consultar_recibo("PROT-XX")
    assert rec.estado == EstadoLote.EM_PROCESSAMENTO
    assert rec.finalizado is False


@pytest.mark.asyncio
async def test_consultar_recibo_404_levanta() -> None:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 404
    response.text = "not found"
    http = MagicMock(spec=httpx.AsyncClient)
    http.get = AsyncMock(return_value=response)

    client = EsocialClient(_settings(), http=http)
    with pytest.raises(EsocialError) as ei:
        await client.consultar_recibo("PROT-INEXISTENTE")
    assert ei.value.status_code == 404
