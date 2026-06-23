"""Testes — IngestaoService propaga CBS/IBS/cClassTrib (Sprint 14 PR2)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.modules.ingestao.service import IngestaoService

_TZ_BR = ZoneInfo("America/Sao_Paulo")


def _xml_com_extensao_cbs_ibs() -> bytes:
    """NF-e 4.1 com extensão completa CBS/IBS + cClassTrib."""
    return dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.10">
          <NFe>
            <infNFe Id="NFe35260512345678000195550010000001231000001231" versao="4.10">
              <ide>
                <mod>55</mod><serie>1</serie><nNF>123</nNF>
                <dhEmi>2026-05-01T10:00:00-03:00</dhEmi>
                <tpNF>1</tpNF><natOp>Venda</natOp>
              </ide>
              <emit><CNPJ>12345678000195</CNPJ><CRT>1</CRT></emit>
              <dest><CNPJ>98765432000181</CNPJ></dest>
              <det nItem="1">
                <prod><CFOP>5102</CFOP><NCM>12345678</NCM><vProd>1000.00</vProd></prod>
                <imposto>
                  <IBSCBS><cClassTrib>000001</cClassTrib></IBSCBS>
                </imposto>
              </det>
              <total>
                <ICMSTot>
                  <vBC>1000.00</vBC><vICMS>120.00</vICMS><vIPI>0.00</vIPI>
                  <vPIS>6.50</vPIS><vCOFINS>30.00</vCOFINS><vNF>1000.00</vNF>
                </ICMSTot>
                <IBSCBSTot><vCBS>9.00</vCBS><vIBS>1.00</vIBS></IBSCBSTot>
              </total>
            </infNFe>
          </NFe>
        </nfeProc>
        """).encode("utf-8")


def _xml_sem_extensao() -> bytes:
    """NF-e 4.0 antiga — sem IBSCBSTot nem cClassTrib."""
    return dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
          <NFe>
            <infNFe Id="NFe35260512345678000195550010000001231000001231" versao="4.00">
              <ide>
                <mod>55</mod><serie>1</serie><nNF>123</nNF>
                <dhEmi>2026-05-01T10:00:00-03:00</dhEmi>
                <tpNF>1</tpNF><natOp>Venda</natOp>
              </ide>
              <emit><CNPJ>12345678000195</CNPJ><CRT>1</CRT></emit>
              <det nItem="1">
                <prod><CFOP>5102</CFOP><NCM>12345678</NCM><vProd>1000.00</vProd></prod>
              </det>
              <total>
                <ICMSTot>
                  <vBC>1000.00</vBC><vICMS>120.00</vICMS><vIPI>0.00</vIPI>
                  <vPIS>6.50</vPIS><vCOFINS>30.00</vCOFINS><vNF>1000.00</vNF>
                </ICMSTot>
              </total>
            </infNFe>
          </NFe>
        </nfeProc>
        """).encode("utf-8")


def _empresa(empresa_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(id=empresa_id, cnpj="12345678000195")


async def _executar_ingestao(
    xml: bytes,
) -> SimpleNamespace:
    """Roda IngestaoService.ingerir_upload com EmpresaRepo/DocRepo mockados;
    devolve o DocumentoFiscal *passado* ao salvar() (capturado).
    """
    empresa_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa(empresa_id))

    doc_repo = AsyncMock()
    doc_repo.buscar_por_chave = AsyncMock(return_value=None)
    # ``salvar`` devolve o próprio doc; capturamos no spy
    capturado: dict[str, object] = {}

    async def _salvar(doc: object) -> object:
        capturado["doc"] = doc
        return doc

    doc_repo.salvar = AsyncMock(side_effect=_salvar)

    with (
        patch("app.modules.ingestao.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.ingestao.service.DocumentoFiscalRepo",
            return_value=doc_repo,
        ),
    ):
        await IngestaoService(session).ingerir_upload(tenant_id, empresa_id, xml)

    return capturado["doc"]  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_ingestao_persiste_cbs_ibs_quando_xml_tem_extensao() -> None:
    """NF-e 4.1 com IBSCBSTot — valor_cbs/valor_ibs/cclasstrib vão para o documento."""
    doc = await _executar_ingestao(_xml_com_extensao_cbs_ibs())
    assert doc.valor_cbs == Decimal("9.00")
    assert doc.valor_ibs == Decimal("1.00")
    assert doc.cclasstrib == "000001"


@pytest.mark.asyncio
async def test_ingestao_preserva_none_quando_xml_sem_extensao() -> None:
    """NF-e 4.0 sem extensão — campos novos ficam None (princípio §8.2)."""
    doc = await _executar_ingestao(_xml_sem_extensao())
    assert doc.valor_cbs is None
    assert doc.valor_ibs is None
    assert doc.cclasstrib is None


@pytest.mark.asyncio
async def test_ingestao_nao_quebra_demais_campos() -> None:
    """Verifica regressão — extensão CBS/IBS coexiste com campos legados."""
    doc = await _executar_ingestao(_xml_com_extensao_cbs_ibs())
    # Legados continuam corretos
    assert doc.valor_total == Decimal("1000.00")
    assert doc.valor_icms == Decimal("120.00")
    assert doc.valor_pis == Decimal("6.50")
    assert doc.cfop == "5102"
    assert doc.ncm == "12345678"
    assert isinstance(doc.emitida_em, datetime)
