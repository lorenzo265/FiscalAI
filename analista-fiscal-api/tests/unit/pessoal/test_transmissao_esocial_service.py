"""Testes do TransmissaoEsocialService (Sprint 19.7 PR2 #13).

Mock-based — banco e cliente HTTP são fakes. Foco em:
  * Fail-closed quando ESOCIAL_TRANSMISSAO_ATIVA=false.
  * Empacotamento + idempotency key estável.
  * Aplicação de recibo aceita/rejeita.
  * Fail-soft quando assinador é NotImplemented.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.config import Settings
from app.modules.pessoal.transmissao_esocial_service import (
    TransmissaoEsocialService,
)
from app.shared.crypto.xmldsig import NotImplementedXmldsigSigner
from app.shared.db.models import EventoESocial
from app.shared.exceptions import (
    EsocialAssinaturaIndisponivel,
    EsocialEventoNaoEncontrado,
    EsocialLoteInvalido,
    EsocialTransmissaoDesativada,
)
from app.shared.integrations.esocial.types import (
    EstadoLote,
    EventoLote,
    LoteEnviado,
    ReciboEvento,
    ReciboLote,
)


def _settings(**over: object) -> Settings:
    defaults: dict[str, object] = {
        "ESOCIAL_TRANSMISSAO_ATIVA": True,
        "ESOCIAL_SANDBOX": True,
        "ESOCIAL_LOTE_MAX_EVENTOS": 50,
    }
    defaults.update(over)
    return Settings(**defaults)  # type: ignore[arg-type]


def _evento_fake(
    *,
    tipo: str = "S-1200",
    status: str = "preparado",
    xml_assinado: bytes | None = None,
) -> EventoESocial:
    ev = EventoESocial(
        id=uuid4(),
        tenant_id=uuid4(),
        empresa_id=uuid4(),
        tipo_evento=tipo,
        referencia_tipo="folha_mensal",
        referencia_id=uuid4(),
        payload={
            "tipo": tipo,
            "ide_evento": {"perApur": "2026-04"},
            "ide_empregador": {"tpInsc": 1, "nrInsc": "11222333000144"},
        },
        status=status,
        algoritmo_versao="esocial.skeleton.v3",
        criado_em=datetime.now(UTC),
        xml_assinado=xml_assinado,
    )
    return ev


def _cliente_mock(*, max_eventos: int = 50) -> MagicMock:
    c = MagicMock()
    c.max_eventos_por_lote = max_eventos
    c.enviar_lote = AsyncMock(
        return_value=LoteEnviado(
            protocolo="PROT-X",
            enviado_em=datetime.now(UTC),
            estado=EstadoLote.ENVIADO,
        )
    )
    c.consultar_recibo = AsyncMock(
        return_value=ReciboLote(
            protocolo="PROT-X",
            estado=EstadoLote.EM_PROCESSAMENTO,
            consultado_em=datetime.now(UTC),
        )
    )
    return c


# ── Fail-closed §8.12 ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transmitir_lote_levanta_quando_flag_off() -> None:
    service = TransmissaoEsocialService(
        settings=_settings(ESOCIAL_TRANSMISSAO_ATIVA=False),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    session = MagicMock()
    with pytest.raises(EsocialTransmissaoDesativada):
        await service.transmitir_lote(
            session, empresa_id=uuid4(), cnpj_empregador="11222333000144"
        )


# ── Assinatura fail-soft ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assinar_evento_com_signer_not_implemented_levanta_412() -> None:
    ev = _evento_fake(status="preparado")
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    # Patch o repo.
    import app.modules.pessoal.transmissao_esocial_service as mod

    fake_repo = MagicMock()
    fake_repo.por_id = AsyncMock(return_value=ev)
    monkeypatch_repo(mod, fake_repo)

    service = TransmissaoEsocialService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="grupo off"),
        cliente=_cliente_mock(),
    )
    with pytest.raises(EsocialAssinaturaIndisponivel):
        await service.assinar_evento(session, ev.id)
    # Evento permanece em 'preparado' (xml_assinado fica None).
    assert ev.status == "preparado"
    assert ev.xml_assinado is None
    # Mas hash_xml é gravado pra idempotência forte.
    assert ev.hash_xml is not None
    assert len(ev.hash_xml) == 64


@pytest.mark.asyncio
async def test_assinar_evento_inexistente_levanta_404() -> None:
    import app.modules.pessoal.transmissao_esocial_service as mod

    fake_repo = MagicMock()
    fake_repo.por_id = AsyncMock(return_value=None)
    monkeypatch_repo(mod, fake_repo)

    service = TransmissaoEsocialService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    with pytest.raises(EsocialEventoNaoEncontrado):
        await service.assinar_evento(MagicMock(), uuid4())


# ── Empacotamento + idempotency key ──────────────────────────────────────


@pytest.mark.asyncio
async def test_transmitir_lote_envia_apenas_assinados() -> None:
    xml_a = b"<eSocial><evtRemun Id='IDA'/></eSocial>"
    xml_b = b"<eSocial><evtRemun Id='IDB'/></eSocial>"
    eventos = [
        _evento_fake(status="assinado", xml_assinado=xml_a),
        _evento_fake(status="assinado", xml_assinado=xml_b),
    ]
    import app.modules.pessoal.transmissao_esocial_service as mod

    fake_repo = MagicMock()
    fake_repo.listar_por_status = AsyncMock(return_value=eventos)
    monkeypatch_repo(mod, fake_repo)

    session = MagicMock()
    session.commit = AsyncMock()

    cliente = _cliente_mock()
    service = TransmissaoEsocialService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=cliente,
    )

    recibo = await service.transmitir_lote(
        session,
        empresa_id=eventos[0].empresa_id,
        cnpj_empregador="11222333000144",
    )

    # Cliente foi chamado com 2 EventoLote, mesmos ids extraídos do XML.
    args, kwargs = cliente.enviar_lote.call_args
    pacote = args[0]
    assert len(pacote) == 2
    assert {ev.id_evento for ev in pacote} == {"IDA", "IDB"}
    assert kwargs["cnpj_empregador"] == "11222333000144"
    # Idempotency key é UUID5 estável (mesmas entradas = mesma chave).
    assert kwargs["idempotency_key"] == service._idempotency_key_do_lote(
        list(pacote)
    )
    # Eventos foram marcados como em_lote com protocolo.
    for ev in eventos:
        assert ev.status == "em_lote"
        assert ev.lote_protocolo == "PROT-X"
        assert ev.transmitido_em is not None
    # Recibo inicial = EM_PROCESSAMENTO.
    assert recibo is not None
    assert recibo.estado == EstadoLote.EM_PROCESSAMENTO


@pytest.mark.asyncio
async def test_transmitir_lote_sem_pendentes_devolve_none() -> None:
    import app.modules.pessoal.transmissao_esocial_service as mod

    fake_repo = MagicMock()
    fake_repo.listar_por_status = AsyncMock(return_value=[])
    monkeypatch_repo(mod, fake_repo)

    service = TransmissaoEsocialService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    out = await service.transmitir_lote(
        MagicMock(), empresa_id=uuid4(), cnpj_empregador="11222333000144"
    )
    assert out is None


def test_idempotency_key_estavel() -> None:
    service = TransmissaoEsocialService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    a = [
        EventoLote(id_evento="IDB", xml_assinado=b""),
        EventoLote(id_evento="IDA", xml_assinado=b""),
    ]
    b = [
        EventoLote(id_evento="IDA", xml_assinado=b""),
        EventoLote(id_evento="IDB", xml_assinado=b""),
    ]
    # Ordem não-importa: UUID5 é sobre conjunto ordenado.
    assert service._idempotency_key_do_lote(a) == service._idempotency_key_do_lote(b)


# ── Aplicação de recibo ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_aplicar_recibo_marca_aceito_quando_201() -> None:
    xml_a = b"<eSocial><evtRemun Id='IDA'/></eSocial>"
    ev = _evento_fake(status="em_lote", xml_assinado=xml_a)
    ev.lote_protocolo = "PROT-X"
    import app.modules.pessoal.transmissao_esocial_service as mod

    fake_repo = MagicMock()
    fake_repo.listar_por_lote = AsyncMock(return_value=[ev])
    monkeypatch_repo(mod, fake_repo)

    recibo = ReciboLote(
        protocolo="PROT-X",
        estado=EstadoLote.PROCESSADO,
        consultado_em=datetime.now(UTC),
        eventos=(
            ReciboEvento(
                id_evento="IDA",
                numero_recibo="REC-001",
                codigo_retorno="201",
                descricao="Sucesso",
            ),
        ),
    )

    session = MagicMock()
    session.commit = AsyncMock()

    service = TransmissaoEsocialService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    n = await service.aplicar_recibo(session, recibo)
    assert n == 1
    assert ev.status == "aceito"
    assert ev.recibo_numero == "REC-001"
    assert ev.processado_em is not None


@pytest.mark.asyncio
async def test_aplicar_recibo_marca_rejeitado_quando_nao_201() -> None:
    xml_a = b"<eSocial><evtRemun Id='IDA'/></eSocial>"
    ev = _evento_fake(status="em_lote", xml_assinado=xml_a)
    ev.lote_protocolo = "PROT-X"
    import app.modules.pessoal.transmissao_esocial_service as mod

    fake_repo = MagicMock()
    fake_repo.listar_por_lote = AsyncMock(return_value=[ev])
    monkeypatch_repo(mod, fake_repo)

    recibo = ReciboLote(
        protocolo="PROT-X",
        estado=EstadoLote.PROCESSADO_COM_ERROS,
        consultado_em=datetime.now(UTC),
        eventos=(
            ReciboEvento(
                id_evento="IDA",
                numero_recibo=None,
                codigo_retorno="401",
                descricao="Schema XML inválido",
                ocorrencias=("regra-X-violada",),
            ),
        ),
    )
    session = MagicMock()
    session.commit = AsyncMock()
    service = TransmissaoEsocialService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    n = await service.aplicar_recibo(session, recibo)
    assert n == 1
    assert ev.status == "rejeitado"
    assert ev.resposta is not None
    assert "regra-X-violada" in str(ev.resposta)


# ── Helpers ────────────────────────────────────────────────────────────────


def monkeypatch_repo(mod: object, fake_repo: MagicMock) -> None:
    """Substitui EventoESocialRepo no módulo por uma factory que devolve fake."""

    class _Factory:
        def __init__(self, _session: object) -> None:
            pass

        def __getattr__(self, name: str) -> object:
            return getattr(fake_repo, name)

    mod.EventoESocialRepo = _Factory


def test_extrair_id_evento_sem_id_levanta() -> None:
    service = TransmissaoEsocialService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    with pytest.raises(EsocialLoteInvalido):
        service._extrair_id_evento("<eSocial><evtRemun/></eSocial>")


def test_extrair_id_evento_padrao() -> None:
    service = TransmissaoEsocialService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    out = service._extrair_id_evento(
        "<eSocial xmlns='x'><evtRemun Id=\"ID12345\"><x/></evtRemun></eSocial>"
    )
    assert out == "ID12345"
