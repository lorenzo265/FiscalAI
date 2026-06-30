"""Testes — Transmissão de Evento MD-e ao SEFAZ RecepcaoEvento (PR3).

Cobertura:
  1. Happy path: assinador fake (retorna bytes) + Fake provider (cStat 135)
     + MemoryStorage + transmissao_ativa=True →
     assina → grava XML → transmite → grava recibo → status='aceito'.
  2. Caminho rejeitado: cStat 218 → status='rejeitado', protocolo=None.
  3. Fail-closed: transmissao_ativa=False → ManifestacaoTransmissaoDesativada (412).
  4. Fail-soft: signer levanta XmldsigSigningError →
     ManifestacaoAssinaturaIndisponivel (412), status fica 'preparado'.
  5. Idempotência: manifestação já 'aceita' → no-op (retorna como está,
     sem rechamar provider nem storage).
  6. Keys de storage: XML gravado em xml_evento_storage_key;
     recibo em xml_recibo_storage_key (path determinístico).

Sem rede, sem DB real — signer fake + provider fake + MemoryStorage +
mock de session (AsyncMock). Segue o padrão de test_distribuicao.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.manifestacao.transmissao_manifestacao_service import (
    TransmissaoManifestacaoService,
)
from app.shared.crypto.xmldsig import XmldsigSigningError
from app.shared.db.models import ManifestacaoNFe
from app.shared.exceptions import (
    ManifestacaoAssinaturaIndisponivel,
    ManifestacaoTransmissaoDesativada,
)
from app.shared.integrations.sefaz_mde.provider import _FakeSefazMdeProvider
from app.shared.integrations.sefaz_mde.types import ResultadoTransmissaoEvento
from app.shared.storage.backend import MemoryStorage

# ── Fixtures / helpers ───────────────────────────────────────────────────────

_TENANT_ID: UUID = uuid4()
_EMPRESA_ID: UUID = uuid4()

# Chave NF-e fictícia de 44 dígitos (NT 2014.002)
_CHAVE: str = "35260612345678000195550010000123451234567890"
_CNPJ: str = "12345678000195"
_DH: datetime = datetime(2026, 6, 29, 14, 0, 0, tzinfo=UTC)


# ── Signer fakes ─────────────────────────────────────────────────────────────


class _FakeXmldsigSigner:
    """Assinador fake: retorna bytes determinísticos sem criptografia real."""

    def assinar(self, xml_canonico: str, *, id_referencia: str) -> bytes:
        return f"<SIGNED id='{id_referencia}'>{xml_canonico}</SIGNED>".encode()


class _FailingXmldsigSigner:
    """Assinador que sempre falha (simula cert ausente)."""

    def assinar(self, xml_canonico: str, *, id_referencia: str) -> bytes:
        raise XmldsigSigningError("cert ausente — teste fail-soft")


# ── ManifestacaoNFe factory ──────────────────────────────────────────────────


def _make_manifestacao(
    *,
    status: str = "preparado",
    manifestacao_id: UUID | None = None,
    empresa_id: UUID | None = None,
    tipo_evento: str = "210200",
    sequencial: int = 1,
    justificativa: str | None = None,
    xml_evento_storage_key: str | None = None,
) -> ManifestacaoNFe:
    """Cria um ManifestacaoNFe em memória (sem DB) com os campos essenciais."""
    m = ManifestacaoNFe(
        tenant_id=_TENANT_ID,
        empresa_id=empresa_id or _EMPRESA_ID,
        chave_nfe=_CHAVE,
        cnpj_destinatario=_CNPJ,
        tipo_evento=tipo_evento,
        sequencial=sequencial,
        justificativa=justificativa,
        status=status,
        algoritmo_versao="mde.xml.v1",
        xml_evento_storage_key=xml_evento_storage_key,
        xml_recibo_storage_key=None,
        criado_em=_DH,
    )
    # Sobrescreve o id gerado pelo default uuid4 se fornecido
    if manifestacao_id is not None:
        m.id = manifestacao_id
    return m


def _mock_session(manifestacao: ManifestacaoNFe | None) -> AsyncMock:
    """Cria um AsyncMock de AsyncSession que devolve ``manifestacao`` no execute."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = manifestacao
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _make_service() -> TransmissaoManifestacaoService:
    return TransmissaoManifestacaoService()


# ── Testes ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transmitir_aceito_cstat_135() -> None:
    """Happy path: cStat 135 → status='aceito', protocolo preenchido."""
    manifestacao = _make_manifestacao(status="preparado")
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider()

    result = await _make_service().transmitir(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        manifestacao.id,
        signer=_FakeXmldsigSigner(),
        provider=provider,
        storage=storage,
        transmissao_ativa=True,
    )

    assert result.status == "aceito"
    assert result.protocolo is not None
    assert result.codigo_status_sefaz == 135
    assert result.motivo_sefaz is not None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_transmitir_rejeitado_cstat_218() -> None:
    """Caminho de rejeição: cStat 218 → status='rejeitado', protocolo=None."""
    manifestacao = _make_manifestacao(status="preparado")
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider(rejeitar_evento=True)

    result = await _make_service().transmitir(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        manifestacao.id,
        signer=_FakeXmldsigSigner(),
        provider=provider,
        storage=storage,
        transmissao_ativa=True,
    )

    assert result.status == "rejeitado"
    assert result.protocolo is None
    assert result.codigo_status_sefaz == 218
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_transmitir_fail_closed_sem_flag() -> None:
    """transmissao_ativa=False → ManifestacaoTransmissaoDesativada (412)."""
    manifestacao = _make_manifestacao(status="preparado")
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider()

    with pytest.raises(ManifestacaoTransmissaoDesativada) as exc_info:
        await _make_service().transmitir(
            session,
            _TENANT_ID,
            _EMPRESA_ID,
            manifestacao.id,
            signer=_FakeXmldsigSigner(),
            provider=provider,
            storage=storage,
            transmissao_ativa=False,
        )

    assert exc_info.value.http_status == 412
    # Nem chegou a acessar o DB
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_transmitir_fail_soft_sem_cert() -> None:
    """Signer sem cert → ManifestacaoAssinaturaIndisponivel (412), status 'preparado'."""
    manifestacao = _make_manifestacao(status="preparado")
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider()

    with pytest.raises(ManifestacaoAssinaturaIndisponivel) as exc_info:
        await _make_service().transmitir(
            session,
            _TENANT_ID,
            _EMPRESA_ID,
            manifestacao.id,
            signer=_FailingXmldsigSigner(),
            provider=provider,
            storage=storage,
            transmissao_ativa=True,
        )

    assert exc_info.value.http_status == 412
    # Status não foi alterado (falhou antes de qualquer write)
    assert manifestacao.status == "preparado"
    # Storage não recebeu nenhum arquivo
    assert not storage._items
    # Session não foi commitada
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_transmitir_idempotente_ja_aceito() -> None:
    """Manifestação já 'aceita' → no-op (retorna como está, sem commit)."""
    manifestacao = _make_manifestacao(status="aceito")
    manifestacao.protocolo = "NFEMDEABC123"
    manifestacao.codigo_status_sefaz = 135
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider()

    result = await _make_service().transmitir(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        manifestacao.id,
        signer=_FakeXmldsigSigner(),
        provider=provider,
        storage=storage,
        transmissao_ativa=True,
    )

    # Retorna o mesmo objeto sem modificar
    assert result.status == "aceito"
    assert result.protocolo == "NFEMDEABC123"
    # Provider e storage NÃO foram chamados
    assert not storage._items
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_transmitir_idempotente_ja_transmitido() -> None:
    """Manifestação já 'transmitida' → no-op (mesmo comportamento que 'aceito')."""
    manifestacao = _make_manifestacao(status="transmitido")
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider()

    result = await _make_service().transmitir(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        manifestacao.id,
        signer=_FakeXmldsigSigner(),
        provider=provider,
        storage=storage,
        transmissao_ativa=True,
    )

    assert result.status == "transmitido"
    assert not storage._items
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_transmitir_xml_gravado_na_key_correta() -> None:
    """XML assinado é gravado em xml_evento_storage_key com path determinístico."""
    manifestacao = _make_manifestacao(status="preparado")
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider()

    await _make_service().transmitir(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        manifestacao.id,
        signer=_FakeXmldsigSigner(),
        provider=provider,
        storage=storage,
        transmissao_ativa=True,
    )

    # Verifica que a key esperada existe no storage
    expected_key = (
        f"tenant/{_TENANT_ID}/empresa/{_EMPRESA_ID}/manifestacao/"
        f"{_CHAVE}/210200/01.xml"
    )
    assert await storage.exists(expected_key), (
        f"XML não foi gravado em '{expected_key}'. Keys no storage: {list(storage._items)}"
    )
    xml_bytes = await storage.get_bytes(expected_key)
    # O fake signer envolve o XML em <SIGNED>...</SIGNED>
    assert b"<SIGNED" in xml_bytes


@pytest.mark.asyncio
async def test_transmitir_recibo_gravado_na_key_correta() -> None:
    """Recibo (retEvento) é gravado em xml_recibo_storage_key."""
    manifestacao = _make_manifestacao(status="preparado")
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider()

    await _make_service().transmitir(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        manifestacao.id,
        signer=_FakeXmldsigSigner(),
        provider=provider,
        storage=storage,
        transmissao_ativa=True,
    )

    expected_key = (
        f"tenant/{_TENANT_ID}/empresa/{_EMPRESA_ID}/manifestacao/"
        f"{_CHAVE}/210200/01_recibo.xml"
    )
    assert await storage.exists(expected_key), (
        f"Recibo não foi gravado em '{expected_key}'. Keys: {list(storage._items)}"
    )
    recibo_bytes = await storage.get_bytes(expected_key)
    assert b"<retEvento>" in recibo_bytes
    assert b"135" in recibo_bytes


@pytest.mark.asyncio
async def test_transmitir_storage_key_xml_definida_no_manifestacao() -> None:
    """Após transmitir, xml_evento_storage_key fica preenchida no objeto."""
    manifestacao = _make_manifestacao(status="preparado")
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider()

    result = await _make_service().transmitir(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        manifestacao.id,
        signer=_FakeXmldsigSigner(),
        provider=provider,
        storage=storage,
        transmissao_ativa=True,
    )

    assert result.xml_evento_storage_key is not None
    assert _CHAVE in result.xml_evento_storage_key
    assert "210200" in result.xml_evento_storage_key


@pytest.mark.asyncio
async def test_transmitir_usa_xml_evento_storage_key_existente() -> None:
    """Se xml_evento_storage_key já está definida, usa a mesma key (não cria nova)."""
    chave_pre_definida = f"tenant/{_TENANT_ID}/empresa/{_EMPRESA_ID}/manifestacao/custom.xml"
    manifestacao = _make_manifestacao(
        status="preparado",
        xml_evento_storage_key=chave_pre_definida,
    )
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider()

    await _make_service().transmitir(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        manifestacao.id,
        signer=_FakeXmldsigSigner(),
        provider=provider,
        storage=storage,
        transmissao_ativa=True,
    )

    # O XML deve ter sido gravado na key pre-definida
    assert await storage.exists(chave_pre_definida), (
        f"XML não foi gravado na key pré-definida '{chave_pre_definida}'"
    )


@pytest.mark.asyncio
async def test_transmitir_respondido_em_preenchido() -> None:
    """respondido_em é preenchido após a transmissão."""
    manifestacao = _make_manifestacao(status="preparado")
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider()

    result = await _make_service().transmitir(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        manifestacao.id,
        signer=_FakeXmldsigSigner(),
        provider=provider,
        storage=storage,
        transmissao_ativa=True,
    )

    assert result.respondido_em is not None
    assert result.transmitido_em is not None


@pytest.mark.asyncio
async def test_transmitir_tipo_nao_realizada_com_justificativa() -> None:
    """Tipo 210240 (Não Realizada) com justificativa → transmissão funciona."""
    justificativa = "Mercadoria recusada no recebimento por nao conformidade"
    manifestacao = _make_manifestacao(
        status="preparado",
        tipo_evento="210240",
        justificativa=justificativa,
    )
    session = _mock_session(manifestacao)
    storage = MemoryStorage()
    provider = _FakeSefazMdeProvider()

    result = await _make_service().transmitir(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        manifestacao.id,
        signer=_FakeXmldsigSigner(),
        provider=provider,
        storage=storage,
        transmissao_ativa=True,
    )

    assert result.status == "aceito"
    # Verifica que o XML foi gerado com a justificativa (inclui 210240 na key)
    expected_key = (
        f"tenant/{_TENANT_ID}/empresa/{_EMPRESA_ID}/manifestacao/"
        f"{_CHAVE}/210240/01.xml"
    )
    assert await storage.exists(expected_key)


@pytest.mark.asyncio
async def test_fake_provider_protocolo_deterministico() -> None:
    """Mesmo idempotency_key → mesmo protocolo no resultado fake."""
    provider = _FakeSefazMdeProvider()
    r1 = await provider.transmitir_evento(_CNPJ, b"<xml/>", "key-abc")
    r2 = await provider.transmitir_evento(_CNPJ, b"<xml/>", "key-abc")
    assert r1.protocolo == r2.protocolo
    assert r1.aceito is True


@pytest.mark.asyncio
async def test_resultado_transmissao_evento_cstat_aceitos() -> None:
    """ResultadoTransmissaoEvento: cStat 135 e 136 são aceitos; 218 é rejeitado."""
    from app.shared.integrations.sefaz_mde.types import CSTAT_ACEITOS_MDE

    assert 135 in CSTAT_ACEITOS_MDE
    assert 136 in CSTAT_ACEITOS_MDE
    assert 218 not in CSTAT_ACEITOS_MDE

    # Cria instâncias para verificar a propriedade aceito
    r_aceito = ResultadoTransmissaoEvento(
        protocolo="NFEPROT123",
        codigo_status=135,
        motivo="Evento registrado e vinculado a NF-e",
        xml_recibo=b"<retEvento/>",
        aceito=True,
    )
    r_rejeitado = ResultadoTransmissaoEvento(
        protocolo=None,
        codigo_status=218,
        motivo="Rejeicao: Duplicidade de evento",
        xml_recibo=b"<retEvento/>",
        aceito=False,
    )
    assert r_aceito.aceito is True
    assert r_rejeitado.aceito is False


@pytest.mark.asyncio
async def test_cert_loader_retorna_none() -> None:
    """carregar_cert_a1 retorna None quando a empresa não tem cert ativo/válido.

    Desde o épico cert A1, o helper consulta ``certificado_a1`` — aqui o mock
    devolve nenhuma linha (``scalar_one_or_none`` → None), então o resultado é
    None (fail-soft §8.12). O caminho com cert real vai na suíte de integração.
    """
    from unittest.mock import MagicMock

    from app.shared.crypto.cert_loader import carregar_cert_a1

    # `execute` é async (awaitable); o Result e `scalar_one_or_none` são sync.
    resultado = MagicMock()
    resultado.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=resultado)
    empresa_id = uuid4()
    result = await carregar_cert_a1(session, empresa_id)
    assert result is None
