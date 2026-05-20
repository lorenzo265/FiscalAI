"""Testes unitários — parser XML NF-e 4.0.

Valida extração de campos críticos: chave, CNPJ, valores, datas.
"""

from __future__ import annotations

from decimal import Decimal
from textwrap import dedent

import pytest

from app.modules.ingestao.parser import XmlNFeInvalido, parse_xml_nfe

# ── XML de referência ─────────────────────────────────────────────────────────

_XML_NFE_VALIDO = dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
      <NFe>
        <infNFe Id="NFe35260512345678000195550010000001231000001231" versao="4.00">
          <ide>
            <mod>55</mod>
            <serie>1</serie>
            <nNF>123</nNF>
            <dhEmi>2026-05-01T10:00:00-03:00</dhEmi>
            <tpNF>1</tpNF>
            <natOp>Venda de mercadoria</natOp>
          </ide>
          <emit>
            <CNPJ>12345678000195</CNPJ>
            <CRT>1</CRT>
          </emit>
          <dest>
            <CNPJ>98765432000181</CNPJ>
          </dest>
          <det nItem="1">
            <prod>
              <CFOP>5102</CFOP>
              <NCM>12345678</NCM>
              <vProd>1000.00</vProd>
            </prod>
          </det>
          <total>
            <ICMSTot>
              <vBC>1000.00</vBC>
              <vICMS>120.00</vICMS>
              <vIPI>0.00</vIPI>
              <vPIS>6.50</vPIS>
              <vCOFINS>30.00</vCOFINS>
              <vNF>1000.00</vNF>
            </ICMSTot>
          </total>
        </infNFe>
        <Signature/>
      </NFe>
      <protNFe versao="4.00">
        <infProt>
          <chNFe>35260512345678000195550010000001231000001231</chNFe>
          <nProt>135260501234567</nProt>
          <dhRecbto>2026-05-01T10:01:00-03:00</dhRecbto>
          <cStat>100</cStat>
        </infProt>
      </protNFe>
    </nfeProc>
""").encode("utf-8")

_XML_NFCE = _XML_NFE_VALIDO.replace(b"<mod>55</mod>", b"<mod>65</mod>")

_XML_MALFORMADO = b"<nao-e-xml>"

_XML_SEM_INFNFE = b"""<?xml version="1.0"?><root xmlns="http://www.portalfiscal.inf.br/nfe"/>"""


# ── Testes principais ─────────────────────────────────────────────────────────


def test_parse_nfe_valido() -> None:
    nfe = parse_xml_nfe(_XML_NFE_VALIDO)

    assert nfe.tipo == "nfe"
    assert nfe.chave == "35260512345678000195550010000001231000001231"
    assert nfe.numero == "123"
    assert nfe.serie == "1"
    assert nfe.cnpj_emitente == "12345678000195"
    assert nfe.cnpj_destinatario == "98765432000181"
    assert nfe.valor_total == Decimal("1000.00")
    assert nfe.valor_icms == Decimal("120.00")
    assert nfe.valor_ipi == Decimal("0.00")
    assert nfe.valor_pis == Decimal("6.50")
    assert nfe.valor_cofins == Decimal("30.00")
    assert nfe.cfop == "5102"
    assert nfe.ncm == "12345678"
    assert nfe.natureza_operacao == "Venda de mercadoria"
    assert nfe.crt == "1"
    assert nfe.emitida_em.year == 2026
    assert nfe.emitida_em.month == 5
    assert nfe.emitida_em.day == 1


def test_parse_nfce_detecta_tipo() -> None:
    nfe = parse_xml_nfe(_XML_NFCE)
    assert nfe.tipo == "nfce"


def test_xml_malformado_levanta_erro() -> None:
    with pytest.raises(XmlNFeInvalido, match="malformado"):
        parse_xml_nfe(_XML_MALFORMADO)


def test_xml_sem_infnfe_levanta_erro() -> None:
    with pytest.raises(XmlNFeInvalido, match="infNFe"):
        parse_xml_nfe(_XML_SEM_INFNFE)


def test_emitida_em_e_timezone_aware() -> None:
    nfe = parse_xml_nfe(_XML_NFE_VALIDO)
    assert nfe.emitida_em.tzinfo is not None


def test_chave_de_infnfe_id_quando_sem_protnfe() -> None:
    xml_sem_prot = _XML_NFE_VALIDO.replace(
        b"<protNFe", b"<protNFeX"
    ).replace(b"</protNFe>", b"</protNFeX>")
    nfe = parse_xml_nfe(xml_sem_prot)
    assert len(nfe.chave) == 44
    assert nfe.chave.isdigit()
