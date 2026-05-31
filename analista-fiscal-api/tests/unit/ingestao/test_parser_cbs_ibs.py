"""Testes do parser NF-e 4.x — extensão IBSCBS (Reforma Tributária, Sprint 14 PR2).

Cobre os 3 campos opcionais introduzidos:
  * ``valor_cbs``     ← ``<total><IBSCBSTot><vCBS>``
  * ``valor_ibs``     ← ``<total><IBSCBSTot><vIBS>``
  * ``cclasstrib``    ← ``<det><imposto><IBSCBS><cClassTrib>`` (primeiro item)
"""

from __future__ import annotations

from decimal import Decimal
from textwrap import dedent

from app.modules.ingestao.parser import parse_xml_nfe


def _xml(
    *,
    ibscbstot: str = "",
    cclasstrib_block: str = "",
) -> bytes:
    """Monta NF-e 4.x parametrizando a extensão IBSCBS para testar variações."""
    template = dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.10">
          <NFe>
            <infNFe Id="NFe35260512345678000195550010000001231000001231" versao="4.10">
              <ide>
                <mod>55</mod>
                <serie>1</serie>
                <nNF>123</nNF>
                <dhEmi>2026-05-01T10:00:00-03:00</dhEmi>
                <tpNF>1</tpNF>
                <natOp>Venda</natOp>
              </ide>
              <emit><CNPJ>12345678000195</CNPJ><CRT>1</CRT></emit>
              <dest><CNPJ>98765432000181</CNPJ></dest>
              <det nItem="1">
                <prod>
                  <CFOP>5102</CFOP>
                  <NCM>12345678</NCM>
                  <vProd>1000.00</vProd>
                </prod>
                <imposto>
                  __CCLASSTRIB__
                </imposto>
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
                __IBSCBSTOT__
              </total>
            </infNFe>
          </NFe>
        </nfeProc>
        """)
    return (
        template
        .replace("__IBSCBSTOT__", ibscbstot)
        .replace("__CCLASSTRIB__", cclasstrib_block)
        .encode("utf-8")
    )


class TestIbsCbsTotPresente:
    """``<IBSCBSTot>`` no bloco ``<total>`` (NF-e 4.x extensão)."""

    def test_vcbs_e_vibs_extraidos(self) -> None:
        nfe = parse_xml_nfe(
            _xml(ibscbstot="<IBSCBSTot><vCBS>9.00</vCBS><vIBS>1.00</vIBS></IBSCBSTot>")
        )
        assert nfe.valor_cbs == Decimal("9.00")
        assert nfe.valor_ibs == Decimal("1.00")

    def test_apenas_vcbs_presente(self) -> None:
        nfe = parse_xml_nfe(
            _xml(ibscbstot="<IBSCBSTot><vCBS>5.50</vCBS></IBSCBSTot>")
        )
        assert nfe.valor_cbs == Decimal("5.50")
        # vIBS ausente → None (não confundir com 0,00)
        assert nfe.valor_ibs is None

    def test_apenas_vibs_presente(self) -> None:
        nfe = parse_xml_nfe(
            _xml(ibscbstot="<IBSCBSTot><vIBS>0.10</vIBS></IBSCBSTot>")
        )
        assert nfe.valor_ibs == Decimal("0.10")
        assert nfe.valor_cbs is None

    def test_valores_zero_explicito_preserva_decimal(self) -> None:
        """Princípio §8.2 — vCBS=0,00 explícito é DIFERENTE de tag ausente.

        Quando o emissor inclui ``<vCBS>0.00</vCBS>`` está afirmando "calculei
        e deu zero" (ex.: produto da cesta básica reduzida); quando a tag
        falta, é "nem calculei" — semântica preservada.
        """
        nfe = parse_xml_nfe(
            _xml(ibscbstot="<IBSCBSTot><vCBS>0.00</vCBS><vIBS>0.00</vIBS></IBSCBSTot>")
        )
        assert nfe.valor_cbs == Decimal("0.00")
        assert nfe.valor_ibs == Decimal("0.00")


class TestIbsCbsTotAusente:
    """NF-e 4.0 (sem extensão) ou 4.x sem o bloco — preserva ``None``."""

    def test_sem_ibscbstot_retorna_none(self) -> None:
        nfe = parse_xml_nfe(_xml())  # template sem __IBSCBSTOT__
        assert nfe.valor_cbs is None
        assert nfe.valor_ibs is None


class TestCClassTrib:
    """``<cClassTrib>`` no primeiro ``<det>`` (item da nota)."""

    def test_cclasstrib_extraido(self) -> None:
        nfe = parse_xml_nfe(
            _xml(cclasstrib_block="<IBSCBS><cClassTrib>000001</cClassTrib></IBSCBS>")
        )
        assert nfe.cclasstrib == "000001"

    def test_cclasstrib_ausente_retorna_none(self) -> None:
        # template sem __CCLASSTRIB__ → bloco vazio dentro de <imposto>
        nfe = parse_xml_nfe(_xml())
        assert nfe.cclasstrib is None

    def test_cclasstrib_e_ibscbstot_juntos(self) -> None:
        nfe = parse_xml_nfe(
            _xml(
                cclasstrib_block="<IBSCBS><cClassTrib>000200</cClassTrib></IBSCBS>",
                ibscbstot="<IBSCBSTot><vCBS>9.00</vCBS><vIBS>1.00</vIBS></IBSCBSTot>",
            )
        )
        assert nfe.cclasstrib == "000200"
        assert nfe.valor_cbs == Decimal("9.00")
        assert nfe.valor_ibs == Decimal("1.00")


class TestRobustez:
    """Parser nunca quebra por extensão IBSCBS malformada — fallback None."""

    def test_ibscbstot_vazio_nao_quebra(self) -> None:
        nfe = parse_xml_nfe(_xml(ibscbstot="<IBSCBSTot></IBSCBSTot>"))
        assert nfe.valor_cbs is None
        assert nfe.valor_ibs is None

    def test_demais_campos_preservados_quando_extensao_presente(self) -> None:
        """Garante que a extensão CBS/IBS não interfere em campos legados."""
        nfe = parse_xml_nfe(
            _xml(ibscbstot="<IBSCBSTot><vCBS>9.00</vCBS><vIBS>1.00</vIBS></IBSCBSTot>")
        )
        # Legados continuam corretos
        assert nfe.valor_total == Decimal("1000.00")
        assert nfe.valor_icms == Decimal("120.00")
        assert nfe.valor_pis == Decimal("6.50")
        assert nfe.cfop == "5102"
