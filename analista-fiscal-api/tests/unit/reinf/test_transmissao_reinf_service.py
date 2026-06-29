"""Testes do TransmissaoReinfService (Marco 4 PR2 #11).

Mock-based — banco e cliente HTTP são fakes. Foco em:
  * Fail-closed quando REINF_TRANSMISSAO_ATIVA=false.
  * Empacotamento + idempotency key estável.
  * Aplicação de recibo aceita (nrRecibo presente) / rejeita (ausente).
  * Fail-soft quando assinador é NotImplemented.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.config import Settings
from app.modules.reinf.esocial_payload import (
    BeneficiarioPjInput,
    ContratanteInput,
    RetencaoR4020Input,
    gerar_r4020,
)
from app.modules.reinf.transmissao_reinf_service import TransmissaoReinfService
from app.shared.crypto.xmldsig import NotImplementedXmldsigSigner
from app.shared.db.models import EfdReinfEvento
from app.shared.exceptions import (
    ReinfAssinaturaIndisponivel,
    ReinfEventoNaoEncontrado,
    ReinfLoteInvalido,
    ReinfTransmissaoDesativada,
)
from app.shared.integrations.reinf.types import (
    EstadoLote,
    EventoLote,
    LoteEnviado,
    ReciboEvento,
    ReciboLote,
)


def _settings(**over: object) -> Settings:
    defaults: dict[str, object] = {
        "REINF_TRANSMISSAO_ATIVA": True,
        "REINF_SANDBOX": True,
        "REINF_LOTE_MAX_EVENTOS": 50,
    }
    defaults.update(over)
    return Settings(**defaults)  # type: ignore[arg-type]


def _payload_r4020() -> dict[str, object]:
    return gerar_r4020(
        ContratanteInput(cnpj="11222333000144", razao_social="Tomador LTDA"),
        BeneficiarioPjInput(cnpj="99888777000166", razao_social="Prestador SA"),
        RetencaoR4020Input(
            competencia=date(2026, 4, 1),
            valor_bruto_servico=Decimal("10000.00"),
            ir_retido=Decimal("150.00"),
            pis_retido=Decimal("65.00"),
            cofins_retido=Decimal("300.00"),
            csll_retido=Decimal("100.00"),
        ),
    )


def _evento_fake(
    *,
    status: str = "preparado",
    xml_assinado: bytes | None = None,
) -> EfdReinfEvento:
    return EfdReinfEvento(
        id=uuid4(),
        tenant_id=uuid4(),
        empresa_id=uuid4(),
        tipo_evento="R-4020",
        referencia_tipo="pagamento_servico_pj",
        referencia_id=uuid4(),
        periodo_apuracao=date(2026, 4, 1),
        valor_bruto_servico=Decimal("10000.00"),
        ir_retido=Decimal("150.00"),
        pis_retido=Decimal("65.00"),
        cofins_retido=Decimal("300.00"),
        csll_retido=Decimal("100.00"),
        payload=_payload_r4020(),
        status=status,
        algoritmo_versao="reinf.skeleton.v1",
        criado_em=datetime.now(UTC),
        xml_assinado=xml_assinado,
    )


def _cliente_mock(*, max_eventos: int = 50) -> MagicMock:
    c = MagicMock()
    c.max_eventos_por_lote = max_eventos
    c.enviar_lote = AsyncMock(
        return_value=LoteEnviado(
            protocolo="PROT-R",
            enviado_em=datetime.now(UTC),
            estado=EstadoLote.ENVIADO,
        )
    )
    c.consultar_recibo = AsyncMock(
        return_value=ReciboLote(
            protocolo="PROT-R",
            estado=EstadoLote.EM_PROCESSAMENTO,
            consultado_em=datetime.now(UTC),
        )
    )
    return c


def monkeypatch_repo(mod: object, fake_repo: MagicMock) -> None:
    """Substitui EfdReinfRepo no módulo por uma factory que devolve fake."""

    class _Factory:
        def __init__(self, _session: object) -> None:
            pass

        def __getattr__(self, name: str) -> object:
            return getattr(fake_repo, name)

    mod.EfdReinfRepo = _Factory  # type: ignore[attr-defined]


# ── Fail-closed §8.12 ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transmitir_lote_levanta_quando_flag_off() -> None:
    service = TransmissaoReinfService(
        settings=_settings(REINF_TRANSMISSAO_ATIVA=False),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    with pytest.raises(ReinfTransmissaoDesativada):
        await service.transmitir_lote(
            MagicMock(), empresa_id=uuid4(), cnpj_contribuinte="11222333000144"
        )


# ── Assinatura fail-soft ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assinar_evento_signer_not_implemented_levanta_412() -> None:
    ev = _evento_fake(status="preparado")
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    import app.modules.reinf.transmissao_reinf_service as mod

    fake_repo = MagicMock()
    fake_repo.por_id = AsyncMock(return_value=ev)
    monkeypatch_repo(mod, fake_repo)

    service = TransmissaoReinfService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="grupo off"),
        cliente=_cliente_mock(),
    )
    with pytest.raises(ReinfAssinaturaIndisponivel):
        await service.assinar_evento(session, ev.id)
    # Evento permanece em 'preparado' (xml_assinado fica None).
    assert ev.status == "preparado"
    assert ev.xml_assinado is None
    # Mas hash_xml é gravado pra idempotência forte.
    assert ev.hash_xml is not None
    assert len(ev.hash_xml) == 64


@pytest.mark.asyncio
async def test_assinar_evento_inexistente_levanta_404() -> None:
    import app.modules.reinf.transmissao_reinf_service as mod

    fake_repo = MagicMock()
    fake_repo.por_id = AsyncMock(return_value=None)
    monkeypatch_repo(mod, fake_repo)

    service = TransmissaoReinfService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    with pytest.raises(ReinfEventoNaoEncontrado):
        await service.assinar_evento(MagicMock(), uuid4())


# ── Empacotamento + idempotency key ──────────────────────────────────────


@pytest.mark.asyncio
async def test_transmitir_lote_envia_apenas_assinados() -> None:
    xml_a = b"<Reinf><evtPgtoBenefPJ Id='IDA'/></Reinf>"
    xml_b = b"<Reinf><evtPgtoBenefPJ Id='IDB'/></Reinf>"
    eventos = [
        _evento_fake(status="assinado", xml_assinado=xml_a),
        _evento_fake(status="assinado", xml_assinado=xml_b),
    ]
    import app.modules.reinf.transmissao_reinf_service as mod

    fake_repo = MagicMock()
    fake_repo.listar_por_status = AsyncMock(return_value=eventos)
    monkeypatch_repo(mod, fake_repo)

    session = MagicMock()
    session.commit = AsyncMock()

    cliente = _cliente_mock()
    service = TransmissaoReinfService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=cliente,
    )

    recibo = await service.transmitir_lote(
        session,
        empresa_id=eventos[0].empresa_id,
        cnpj_contribuinte="11222333000144",
    )

    args, kwargs = cliente.enviar_lote.call_args
    pacote = args[0]
    assert len(pacote) == 2
    assert {ev.id_evento for ev in pacote} == {"IDA", "IDB"}
    assert kwargs["cnpj_contribuinte"] == "11222333000144"
    # Idempotency key é UUID5 estável.
    assert kwargs["idempotency_key"] == service._idempotency_key_do_lote(
        list(pacote)
    )
    for ev in eventos:
        assert ev.status == "em_lote"
        assert ev.lote_protocolo == "PROT-R"
        assert ev.transmitido_em is not None
    assert recibo is not None
    assert recibo.estado == EstadoLote.EM_PROCESSAMENTO


@pytest.mark.asyncio
async def test_transmitir_lote_sem_pendentes_devolve_none() -> None:
    import app.modules.reinf.transmissao_reinf_service as mod

    fake_repo = MagicMock()
    fake_repo.listar_por_status = AsyncMock(return_value=[])
    monkeypatch_repo(mod, fake_repo)

    service = TransmissaoReinfService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    out = await service.transmitir_lote(
        MagicMock(), empresa_id=uuid4(), cnpj_contribuinte="11222333000144"
    )
    assert out is None


@pytest.mark.asyncio
async def test_transmitir_lote_evento_sem_xml_levanta() -> None:
    ev = _evento_fake(status="assinado", xml_assinado=None)
    import app.modules.reinf.transmissao_reinf_service as mod

    fake_repo = MagicMock()
    fake_repo.listar_por_status = AsyncMock(return_value=[ev])
    monkeypatch_repo(mod, fake_repo)

    service = TransmissaoReinfService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    with pytest.raises(ReinfLoteInvalido):
        await service.transmitir_lote(
            MagicMock(), empresa_id=ev.empresa_id, cnpj_contribuinte="11222333000144"
        )


def test_idempotency_key_estavel() -> None:
    service = TransmissaoReinfService(
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
    assert service._idempotency_key_do_lote(a) == service._idempotency_key_do_lote(b)


# ── Aplicação de recibo ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_aplicar_recibo_marca_aceito_quando_tem_recibo() -> None:
    xml_a = b"<Reinf><evtPgtoBenefPJ Id='IDA'/></Reinf>"
    ev = _evento_fake(status="em_lote", xml_assinado=xml_a)
    ev.lote_protocolo = "PROT-R"
    import app.modules.reinf.transmissao_reinf_service as mod

    fake_repo = MagicMock()
    fake_repo.listar_por_lote = AsyncMock(return_value=[ev])
    monkeypatch_repo(mod, fake_repo)

    recibo = ReciboLote(
        protocolo="PROT-R",
        estado=EstadoLote.PROCESSADO,
        consultado_em=datetime.now(UTC),
        eventos=(
            ReciboEvento(
                id_evento="IDA",
                numero_recibo="REC-001",
                codigo_retorno="0",
                descricao="Sucesso",
            ),
        ),
    )
    session = MagicMock()
    session.commit = AsyncMock()
    service = TransmissaoReinfService(
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
async def test_aplicar_recibo_marca_rejeitado_quando_sem_recibo() -> None:
    xml_a = b"<Reinf><evtPgtoBenefPJ Id='IDA'/></Reinf>"
    ev = _evento_fake(status="em_lote", xml_assinado=xml_a)
    ev.lote_protocolo = "PROT-R"
    import app.modules.reinf.transmissao_reinf_service as mod

    fake_repo = MagicMock()
    fake_repo.listar_por_lote = AsyncMock(return_value=[ev])
    monkeypatch_repo(mod, fake_repo)

    recibo = ReciboLote(
        protocolo="PROT-R",
        estado=EstadoLote.PROCESSADO_COM_ERROS,
        consultado_em=datetime.now(UTC),
        eventos=(
            ReciboEvento(
                id_evento="IDA",
                numero_recibo=None,
                codigo_retorno="201",
                descricao="Schema inválido",
                ocorrencias=("regra-X-violada",),
            ),
        ),
    )
    session = MagicMock()
    session.commit = AsyncMock()
    service = TransmissaoReinfService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    n = await service.aplicar_recibo(session, recibo)
    assert n == 1
    assert ev.status == "rejeitado"
    assert ev.resposta is not None
    assert "regra-X-violada" in str(ev.resposta)


@pytest.mark.asyncio
async def test_aplicar_recibo_skip_enquanto_processando() -> None:
    """Lote ainda em processamento + evento sem retorno → não mexe no evento."""
    xml_a = b"<Reinf><evtPgtoBenefPJ Id='IDA'/></Reinf>"
    ev = _evento_fake(status="em_lote", xml_assinado=xml_a)
    ev.lote_protocolo = "PROT-R"
    import app.modules.reinf.transmissao_reinf_service as mod

    fake_repo = MagicMock()
    fake_repo.listar_por_lote = AsyncMock(return_value=[ev])
    monkeypatch_repo(mod, fake_repo)

    recibo = ReciboLote(
        protocolo="PROT-R",
        estado=EstadoLote.EM_PROCESSAMENTO,  # não finalizado
        consultado_em=datetime.now(UTC),
        eventos=(),  # sem retorno individual ainda
    )
    session = MagicMock()
    session.commit = AsyncMock()
    service = TransmissaoReinfService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    n = await service.aplicar_recibo(session, recibo)
    assert n == 0
    assert ev.status == "em_lote"  # intacto
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_aplicar_recibo_finalizado_sem_retorno_individual_rejeita() -> None:
    """Lote finalizado mas sem o retorno do evento → rejeição de lote."""
    xml_a = b"<Reinf><evtPgtoBenefPJ Id='IDA'/></Reinf>"
    ev = _evento_fake(status="em_lote", xml_assinado=xml_a)
    ev.lote_protocolo = "PROT-R"
    import app.modules.reinf.transmissao_reinf_service as mod

    fake_repo = MagicMock()
    fake_repo.listar_por_lote = AsyncMock(return_value=[ev])
    monkeypatch_repo(mod, fake_repo)

    recibo = ReciboLote(
        protocolo="PROT-R",
        estado=EstadoLote.REJEITADO,  # finalizado
        consultado_em=datetime.now(UTC),
        eventos=(),  # nenhum retorno individual
    )
    session = MagicMock()
    session.commit = AsyncMock()
    service = TransmissaoReinfService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    n = await service.aplicar_recibo(session, recibo)
    assert n == 1
    assert ev.status == "rejeitado"
    assert ev.resposta == {"erro": "sem retorno individual no lote"}
    assert ev.processado_em is not None


# ── Helpers ────────────────────────────────────────────────────────────────


def test_extrair_id_evento_sem_id_levanta() -> None:
    service = TransmissaoReinfService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    with pytest.raises(ReinfLoteInvalido):
        service._extrair_id_evento("<Reinf><evtPgtoBenefPJ/></Reinf>")


def test_extrair_id_evento_padrao() -> None:
    service = TransmissaoReinfService(
        settings=_settings(),
        assinador=NotImplementedXmldsigSigner(motivo="off"),
        cliente=_cliente_mock(),
    )
    out = service._extrair_id_evento(
        "<Reinf xmlns='x'><evtPgtoBenefPJ Id=\"ID12345\"><x/></evtPgtoBenefPJ></Reinf>"
    )
    assert out == "ID12345"
