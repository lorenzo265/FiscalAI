"""Testes — DistribuiçãoDFe (MD-e PR2).

Cobertura:
  * _FakeSefazMdeProvider: determinístico, NSU crescente, batch size.
  * DistribuicaoService.sincronizar: upsert idempotente, cursor avança,
    criação de cursor na 1ª vez, cap max_paginas (truncado).
  * FocusSefazMdeProvider._parse_response: parser com payload exemplo.
  * Schemas: extra="forbid".

Sem rede, sem DB real — provider fake + mock de repo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.manifestacao.distribuicao_repo import DistribuicaoRepo
from app.modules.manifestacao.distribuicao_service import DistribuicaoService
from app.modules.manifestacao.schemas import (
    NfeDestinadaOut,
    SincronizacaoResultadoOut,
    SincronizarManifestacaoIn,
)
from app.shared.db.models import NfeDestinada, NfeDistribuicaoCursor
from app.shared.integrations.sefaz_mde.provider import (
    FocusSefazMdeProvider,
    _FakeSefazMdeProvider,
)

_CNPJ = "12345678000195"
_TENANT_ID = uuid4()
_EMPRESA_ID = uuid4()

# Chave NF-e fictícia de 44 dígitos para testes
_CHAVE_A = "35260612345678000195550010000000011000000001"
_CHAVE_B = "35260612345678000195550010000000021000000002"
_CHAVE_C = "35260612345678000195550010000000031000000003"

_DH = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)


# ── _FakeSefazMdeProvider ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fake_retorna_batch_tamanho_fixo() -> None:
    """Fake retorna exatamente 3 docs por chamada."""
    provider = _FakeSefazMdeProvider()
    result = await provider.baixar_documentos(_CNPJ, 0)
    assert len(result.documentos) == 3


@pytest.mark.asyncio
async def test_fake_nsu_crescente_a_partir_de_ult_nsu() -> None:
    """Docs retornados têm NSUs consecutivos a partir de ult_nsu+1."""
    provider = _FakeSefazMdeProvider()
    result = await provider.baixar_documentos(_CNPJ, 10)
    nsus = [d.nsu for d in result.documentos]
    assert nsus == [11, 12, 13]


@pytest.mark.asyncio
async def test_fake_deterministico_mesma_entrada() -> None:
    """Mesma entrada → mesmos docs (idempotência do provider fake)."""
    provider = _FakeSefazMdeProvider()
    r1 = await provider.baixar_documentos(_CNPJ, 5)
    r2 = await provider.baixar_documentos(_CNPJ, 5)
    assert r1.ult_nsu == r2.ult_nsu
    assert r1.max_nsu == r2.max_nsu
    for d1, d2 in zip(r1.documentos, r2.documentos, strict=False):
        assert d1.chave_nfe == d2.chave_nfe
        assert d1.nsu == d2.nsu
        assert d1.valor_total == d2.valor_total


@pytest.mark.asyncio
async def test_fake_loop_termina_sem_extra_batches() -> None:
    """Com extra_batches=0 (default), ult_nsu == max_nsu → loop para."""
    provider = _FakeSefazMdeProvider()
    result = await provider.baixar_documentos(_CNPJ, 0)
    assert result.ult_nsu >= result.max_nsu


@pytest.mark.asyncio
async def test_fake_extra_batches_ult_nsu_menor_que_max_nsu() -> None:
    """Com extra_batches=2, max_nsu > ult_nsu → loop continua."""
    provider = _FakeSefazMdeProvider(extra_batches=2)
    result = await provider.baixar_documentos(_CNPJ, 0)
    assert result.ult_nsu < result.max_nsu


@pytest.mark.asyncio
async def test_fake_chave_44_digitos() -> None:
    """Chaves geradas pelo fake têm exatamente 44 dígitos."""
    import re

    provider = _FakeSefazMdeProvider()
    result = await provider.baixar_documentos(_CNPJ, 0)
    for doc in result.documentos:
        assert re.match(r"^\d{44}$", doc.chave_nfe), (
            f"Chave inválida: {doc.chave_nfe!r}"
        )


@pytest.mark.asyncio
async def test_fake_valor_total_decimal() -> None:
    """Valor total é Decimal (não float)."""
    provider = _FakeSefazMdeProvider()
    result = await provider.baixar_documentos(_CNPJ, 0)
    for doc in result.documentos:
        assert isinstance(doc.valor_total, Decimal)


@pytest.mark.asyncio
async def test_fake_transmitir_evento_retorna_aceito() -> None:
    """transmitir_evento (PR3) retorna ResultadoTransmissaoEvento com aceito=True (cStat 135)."""
    from app.shared.integrations.sefaz_mde.types import ResultadoTransmissaoEvento

    provider = _FakeSefazMdeProvider()
    resultado = await provider.transmitir_evento(_CNPJ, b"<xml/>", "key-1")
    assert isinstance(resultado, ResultadoTransmissaoEvento)
    assert resultado.aceito is True
    assert resultado.codigo_status == 135


@pytest.mark.asyncio
async def test_fake_transmitir_evento_rejeicao() -> None:
    """transmitir_evento com rejeitar_evento=True retorna aceito=False (cStat 218)."""
    from app.shared.integrations.sefaz_mde.types import ResultadoTransmissaoEvento

    provider = _FakeSefazMdeProvider(rejeitar_evento=True)
    resultado = await provider.transmitir_evento(_CNPJ, b"<xml/>", "key-2")
    assert isinstance(resultado, ResultadoTransmissaoEvento)
    assert resultado.aceito is False
    assert resultado.codigo_status == 218


# ── DistribuicaoService.sincronizar ──────────────────────────────────────────


def _make_mock_cursor(
    *,
    empresa_id: object = None,
    ult_nsu: int = 0,
    max_nsu: int = 0,
) -> MagicMock:
    """Cria um mock de NfeDistribuicaoCursor."""
    c = MagicMock(spec=NfeDistribuicaoCursor)
    c.empresa_id = empresa_id or _EMPRESA_ID
    c.tenant_id = _TENANT_ID
    c.ult_nsu = ult_nsu
    c.max_nsu = max_nsu
    c.ultima_sync_em = None
    return c


def _make_mock_destinada(chave: str, nsu: int = 1) -> MagicMock:
    """Cria um mock de NfeDestinada."""
    obj = MagicMock(spec=NfeDestinada)
    obj.chave_nfe = chave
    obj.nsu = nsu
    return obj


def _make_mock_repo(
    *,
    cursor_existente: object = None,
    is_new: bool = True,
) -> MagicMock:
    """Cria um mock de DistribuicaoRepo com métodos async."""
    cursor_criado = _make_mock_cursor()
    cursor_atualizado = _make_mock_cursor(ult_nsu=3, max_nsu=3)

    repo = MagicMock(spec=DistribuicaoRepo)
    repo.get_cursor = AsyncMock(return_value=cursor_existente)
    repo.create_cursor = AsyncMock(return_value=cursor_criado)
    repo.update_cursor = AsyncMock(return_value=cursor_atualizado)
    repo.upsert_destinada = AsyncMock(
        return_value=(_make_mock_destinada("x" * 44), is_new)
    )
    return repo


@pytest.mark.asyncio
async def test_sincronizar_cria_cursor_na_primeira_vez() -> None:
    """Cursor é criado quando não existe (primeira sincronização)."""
    session = MagicMock()
    session.commit = AsyncMock()

    repo = _make_mock_repo(cursor_existente=None, is_new=True)
    provider = _FakeSefazMdeProvider()  # single-page, terminates

    await DistribuicaoService().sincronizar(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        _CNPJ,
        provider,
        _repo=repo,
    )

    repo.create_cursor.assert_awaited_once_with(_TENANT_ID, _EMPRESA_ID)


@pytest.mark.asyncio
async def test_sincronizar_cursor_existente_nao_cria_novo() -> None:
    """Se cursor já existe, não cria um novo."""
    session = MagicMock()
    session.commit = AsyncMock()

    cursor_existente = _make_mock_cursor(ult_nsu=3, max_nsu=3)
    repo = _make_mock_repo(cursor_existente=cursor_existente)
    provider = _FakeSefazMdeProvider()

    await DistribuicaoService().sincronizar(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        _CNPJ,
        provider,
        _repo=repo,
    )

    repo.create_cursor.assert_not_awaited()


@pytest.mark.asyncio
async def test_sincronizar_upsert_idempotente_segunda_chamada() -> None:
    """Segunda chamada com mesmos docs → atualizados, não novos."""
    session = MagicMock()
    session.commit = AsyncMock()

    cursor = _make_mock_cursor(ult_nsu=0, max_nsu=0)
    repo = _make_mock_repo(cursor_existente=cursor, is_new=False)  # is_new=False
    provider = _FakeSefazMdeProvider()

    resultado = await DistribuicaoService().sincronizar(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        _CNPJ,
        provider,
        _repo=repo,
    )

    # Fake retorna 3 docs; todos marcados como atualizados
    assert resultado.novos == 0
    assert resultado.atualizados == 3


@pytest.mark.asyncio
async def test_sincronizar_cursor_avanca() -> None:
    """Após sync, ult_nsu e max_nsu do resultado refletem o cursor atualizado."""
    session = MagicMock()
    session.commit = AsyncMock()

    cursor = _make_mock_cursor(ult_nsu=0, max_nsu=0)
    repo = _make_mock_repo(cursor_existente=cursor, is_new=True)

    # update_cursor retorna cursor com ult_nsu=3, max_nsu=3
    repo.update_cursor.return_value = _make_mock_cursor(ult_nsu=3, max_nsu=3)

    provider = _FakeSefazMdeProvider()  # extra_batches=0 → ult_nsu == max_nsu

    resultado = await DistribuicaoService().sincronizar(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        _CNPJ,
        provider,
        _repo=repo,
    )

    assert resultado.ult_nsu == 3
    assert resultado.max_nsu == 3
    assert not resultado.truncado


@pytest.mark.asyncio
async def test_sincronizar_truncado_quando_max_paginas_atingido() -> None:
    """Com max_paginas=1 e provider multi-page, truncado=True."""
    session = MagicMock()
    session.commit = AsyncMock()

    cursor = _make_mock_cursor(ult_nsu=0, max_nsu=0)

    # Simula cursor atualizado mas com max_nsu maior (ainda há docs)
    cursor_pos1 = _make_mock_cursor(ult_nsu=3, max_nsu=9)
    repo = _make_mock_repo(cursor_existente=cursor, is_new=True)
    repo.update_cursor.return_value = cursor_pos1

    # Provider com extra_batches=2: max_nsu > ult_nsu → precisaria de 3 páginas
    provider = _FakeSefazMdeProvider(extra_batches=2)

    resultado = await DistribuicaoService().sincronizar(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        _CNPJ,
        provider,
        max_paginas=1,
        _repo=repo,
    )

    assert resultado.truncado is True
    # Apenas 1 página foi processada
    repo.update_cursor.assert_awaited_once()


@pytest.mark.asyncio
async def test_sincronizar_retorna_novos_corretos() -> None:
    """Contagem de novos é igual ao número de docs no batch (is_new=True)."""
    session = MagicMock()
    session.commit = AsyncMock()

    cursor = _make_mock_cursor(ult_nsu=0, max_nsu=0)
    repo = _make_mock_repo(cursor_existente=cursor, is_new=True)
    provider = _FakeSefazMdeProvider()

    resultado = await DistribuicaoService().sincronizar(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        _CNPJ,
        provider,
        _repo=repo,
    )

    # Fake default: 3 docs, todos novos
    assert resultado.novos == 3
    assert resultado.atualizados == 0
    assert not resultado.truncado


@pytest.mark.asyncio
async def test_sincronizar_commit_ao_final() -> None:
    """Session.commit é chamado exatamente 1 vez ao finalizar o sync."""
    session = MagicMock()
    session.commit = AsyncMock()

    cursor = _make_mock_cursor(ult_nsu=0, max_nsu=0)
    repo = _make_mock_repo(cursor_existente=cursor)
    provider = _FakeSefazMdeProvider()

    await DistribuicaoService().sincronizar(
        session,
        _TENANT_ID,
        _EMPRESA_ID,
        _CNPJ,
        provider,
        _repo=repo,
    )

    session.commit.assert_awaited_once()


# ── FocusSefazMdeProvider._parse_response ────────────────────────────────────


def _make_focus_provider() -> FocusSefazMdeProvider:
    """Instância mínima do FocusSefazMdeProvider para testar _parse_response.

    Usa ``object.__new__`` para evitar o ``__init__`` (que abre conexão HTTP).
    ``_parse_response`` e ``_parse_documento`` são métodos puros (sem rede).
    """
    provider: FocusSefazMdeProvider = object.__new__(FocusSefazMdeProvider)
    provider._base = "https://homologacao.focusnfe.com.br"  # type: ignore[attr-defined]
    provider._http = MagicMock()  # type: ignore[attr-defined]
    return provider


def test_focus_parse_response_resnfe_resumo() -> None:
    """Parser interpreta payload resNFe como tipo_documento='resumo'."""
    provider = _make_focus_provider()
    payload = {
        "ult_nsu": "5",
        "max_nsu": "10",
        "documentos": [
            {
                "chave_nfe": _CHAVE_A,
                "nsu": "5",
                "tipo": "resNFe",
                "emitente_cnpj": "12345678000195",
                "emitente_nome": "Fornecedor LTDA",
                "valor_total": "1500.00",
                "dh_emissao": "2026-01-15T10:00:00-03:00",
            }
        ],
    }
    resultado = provider._parse_response(payload, ult_nsu_consulta=2)
    assert resultado.ult_nsu == 5
    assert resultado.max_nsu == 10
    assert len(resultado.documentos) == 1
    doc = resultado.documentos[0]
    assert doc.chave_nfe == _CHAVE_A
    assert doc.nsu == 5
    assert doc.tipo_documento == "resumo"
    assert doc.emitente_cnpj == "12345678000195"
    assert doc.valor_total == Decimal("1500.00")
    assert isinstance(doc.valor_total, Decimal)  # nunca float


def test_focus_parse_response_nfeproc_completo() -> None:
    """Parser interpreta payload nfeProc como tipo_documento='completo'."""
    provider = _make_focus_provider()
    payload = {
        "ultNSU": "8",
        "maxNSU": "8",
        "documentos": [
            {
                "chave_nfe": _CHAVE_B,
                "NSU": "8",
                "tipo": "nfeProc",
                "xml_completo": "<nfeProc>...</nfeProc>",
            }
        ],
    }
    resultado = provider._parse_response(payload, ult_nsu_consulta=5)
    assert resultado.ult_nsu == 8
    assert resultado.max_nsu == 8
    doc = resultado.documentos[0]
    assert doc.tipo_documento == "completo"
    # tem_xml_completo é campo do modelo DB, calculado no upsert, não no DTO
    assert doc.xml_completo == "<nfeProc>...</nfeProc>"


def test_focus_parse_response_aliases_camelcase() -> None:
    """Parser aceita aliasses camelCase (chaveNFe, cnpjEmitente, valorTotal)."""
    provider = _make_focus_provider()
    payload = {
        "ultNSU": "3",
        "maxNSU": "3",
        "docs": [
            {
                "chaveNFe": _CHAVE_C,
                "nsu": 3,
                "cnpjEmitente": "98765432000110",
                "nomeEmitente": "Outro Fornecedor",
                "valorTotal": "200.50",
                "dhEmissao": "2026-01-10T08:30:00Z",
            }
        ],
    }
    resultado = provider._parse_response(payload, ult_nsu_consulta=0)
    assert len(resultado.documentos) == 1
    doc = resultado.documentos[0]
    assert doc.chave_nfe == _CHAVE_C
    assert doc.emitente_cnpj == "98765432000110"
    assert doc.valor_total == Decimal("200.50")


def test_focus_parse_response_doc_sem_chave_ignorado() -> None:
    """Documento sem chave NF-e válida é ignorado silenciosamente."""
    provider = _make_focus_provider()
    payload = {
        "ult_nsu": "1",
        "max_nsu": "1",
        "documentos": [
            {"nsu": 1, "valor_total": "100.00"},  # sem chave_nfe
            {"chave_nfe": "invalida", "nsu": 2},  # chave muito curta
        ],
    }
    resultado = provider._parse_response(payload, ult_nsu_consulta=0)
    assert resultado.documentos == []


def test_focus_parse_response_lista_vazia() -> None:
    """Lista de documentos vazia é tratada corretamente."""
    provider = _make_focus_provider()
    payload = {"ult_nsu": "5", "max_nsu": "5", "documentos": []}
    resultado = provider._parse_response(payload, ult_nsu_consulta=5)
    assert resultado.documentos == []
    assert resultado.ult_nsu == 5
    assert resultado.max_nsu == 5


def test_focus_parse_response_nao_dict_levanta() -> None:
    """Resposta não-dict levanta SefazMdeErro."""
    from app.shared.integrations.sefaz_mde.provider import SefazMdeErro

    provider = _make_focus_provider()
    with pytest.raises(SefazMdeErro, match="não é um objeto JSON"):
        provider._parse_response(["lista", "invalida"], ult_nsu_consulta=0)


# ── Schemas ───────────────────────────────────────────────────────────────────


def test_sincronizar_in_extra_forbid() -> None:
    """SincronizarManifestacaoIn rejeita campos desconhecidos."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="extra_fields_not_permitted|Extra"):
        SincronizarManifestacaoIn.model_validate({"campo_invalido": True})


def test_sincronizar_in_vazio_ok() -> None:
    """SincronizarManifestacaoIn aceita body vazio."""
    obj = SincronizarManifestacaoIn.model_validate({})
    assert obj is not None


def test_sincronizacao_resultado_out_campos() -> None:
    """SincronizacaoResultadoOut serializa todos os campos esperados."""
    out = SincronizacaoResultadoOut(
        novos=5,
        atualizados=2,
        ult_nsu=100,
        max_nsu=100,
        truncado=False,
    )
    data = out.model_dump()
    assert data["novos"] == 5
    assert data["atualizados"] == 2
    assert data["ult_nsu"] == 100
    assert data["max_nsu"] == 100
    assert data["truncado"] is False


def test_nfe_destinada_out_from_attributes() -> None:
    """NfeDestinadaOut.model_validate aceita ORM model mock."""

    obj = MagicMock(spec=NfeDestinada)
    obj.id = uuid4()
    obj.empresa_id = _EMPRESA_ID
    obj.chave_nfe = _CHAVE_A
    obj.nsu = 42
    obj.emitente_cnpj = "12345678000195"
    obj.emitente_nome = "Fornecedor"
    obj.valor_total = Decimal("999.99")
    obj.dh_emissao = datetime(2026, 1, 1, tzinfo=UTC)
    obj.tipo_documento = "resumo"
    obj.tem_xml_completo = False
    obj.xml_storage_key = None
    obj.criado_em = datetime(2026, 1, 2, tzinfo=UTC)
    obj.atualizado_em = datetime(2026, 1, 2, tzinfo=UTC)

    out = NfeDestinadaOut.model_validate(obj)
    assert out.chave_nfe == _CHAVE_A
    assert out.nsu == 42
    assert isinstance(out.valor_total, Decimal)
    assert out.tipo_documento == "resumo"


# ── Protocolo de compatibilidade ─────────────────────────────────────────────


def test_fake_provider_satisfaz_protocolo() -> None:
    """_FakeSefazMdeProvider implementa o Protocol SefazMdeProvider."""
    from app.shared.integrations.sefaz_mde.provider import SefazMdeProvider

    provider = _FakeSefazMdeProvider()
    assert isinstance(provider, SefazMdeProvider)
