"""Testes unitários — extração granular de itens da NF-e (Sprint 18 PR1).

Cobre ``parse_xml_nfe`` populando ``NFeData.itens`` (pendência #26).
"""

from __future__ import annotations

from decimal import Decimal

from app.modules.ingestao.parser import parse_xml_nfe

_NFE_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
    "<NFe>"
    '<infNFe Id="NFe35260512345678000195550010000001231000001231" versao="4.00">'
    "<ide>"
    "<mod>55</mod><serie>1</serie><nNF>123</nNF>"
    "<dhEmi>2026-05-01T10:00:00-03:00</dhEmi>"
    "<natOp>Venda</natOp>"
    "</ide>"
    "<emit><CNPJ>12345678000195</CNPJ><CRT>1</CRT></emit>"
    "<dest><CNPJ>98765432000181</CNPJ></dest>"
    "{itens}"
    "<total><ICMSTot>"
    "<vNF>1000.00</vNF><vICMS>120.00</vICMS><vIPI>0.00</vIPI>"
    "<vPIS>6.50</vPIS><vCOFINS>30.00</vCOFINS>"
    "</ICMSTot></total>"
    "</infNFe>"
    "<Signature/>"
    "</NFe>"
    "<protNFe versao=\"4.00\"><infProt>"
    "<chNFe>35260512345678000195550010000001231000001231</chNFe>"
    "<nProt>1</nProt><dhRecbto>2026-05-01T10:01:00-03:00</dhRecbto><cStat>100</cStat>"
    "</infProt></protNFe>"
    "</nfeProc>"
)


def _nfe_com_itens(itens_xml: str) -> bytes:
    """Monta um XML NF-e mínimo com bloco ``<det>`` arbitrário."""
    return _NFE_TEMPLATE.format(itens=itens_xml).encode("utf-8")


_DET_UM_ITEM = """
<det nItem="1">
  <prod>
    <cProd>P001</cProd>
    <xProd>Notebook Dell</xProd>
    <NCM>84713012</NCM>
    <CFOP>5102</CFOP>
    <uCom>UN</uCom>
    <qCom>2.0000</qCom>
    <vUnCom>500.0000</vUnCom>
    <vProd>1000.00</vProd>
  </prod>
  <imposto>
    <ICMS>
      <ICMS00>
        <CST>00</CST>
        <vICMS>120.00</vICMS>
      </ICMS00>
    </ICMS>
    <PIS>
      <PISAliq>
        <CST>01</CST>
        <vPIS>6.50</vPIS>
      </PISAliq>
    </PIS>
    <COFINS>
      <COFINSAliq>
        <CST>01</CST>
        <vCOFINS>30.00</vCOFINS>
      </COFINSAliq>
    </COFINS>
  </imposto>
</det>
"""


def test_parse_um_item_completo() -> None:
    """NF-e com 1 item carrega todos os campos granulares."""
    nfe = parse_xml_nfe(_nfe_com_itens(_DET_UM_ITEM))
    assert len(nfe.itens) == 1
    item = nfe.itens[0]
    assert item.n_item == 1
    assert item.codigo_produto == "P001"
    assert item.descricao == "Notebook Dell"
    assert item.ncm == "84713012"
    assert item.cfop == "5102"
    assert item.cst_icms == "00"
    assert item.cst_pis == "01"
    assert item.cst_cofins == "01"
    assert item.unidade == "UN"
    assert item.quantidade == Decimal("2.0000")
    assert item.valor_unitario == Decimal("500.0000")
    assert item.valor_total == Decimal("1000.00")
    assert item.valor_icms == Decimal("120.00")
    assert item.valor_pis == Decimal("6.50")
    assert item.valor_cofins == Decimal("30.00")
    assert item.valor_cbs is None  # NF-e sem extensão IBSCBS
    assert item.valor_ibs is None


def test_parse_multiplos_itens_em_ordem() -> None:
    """NF-e com N itens preserva ordem por nItem."""
    det_dois = """
    <det nItem="1">
      <prod>
        <cProd>A</cProd><xProd>Item A</xProd>
        <NCM>11111111</NCM><CFOP>5102</CFOP>
        <uCom>UN</uCom><qCom>1</qCom>
        <vUnCom>100</vUnCom><vProd>100.00</vProd>
      </prod>
      <imposto/>
    </det>
    <det nItem="2">
      <prod>
        <cProd>B</cProd><xProd>Item B</xProd>
        <NCM>22222222</NCM><CFOP>5102</CFOP>
        <uCom>KG</uCom><qCom>3.5</qCom>
        <vUnCom>200</vUnCom><vProd>700.00</vProd>
      </prod>
      <imposto/>
    </det>
    <det nItem="3">
      <prod>
        <cProd>C</cProd><xProd>Item C</xProd>
        <NCM>33333333</NCM><CFOP>5405</CFOP>
        <uCom>UN</uCom><qCom>1</qCom>
        <vUnCom>200</vUnCom><vProd>200.00</vProd>
      </prod>
      <imposto/>
    </det>
    """
    nfe = parse_xml_nfe(_nfe_com_itens(det_dois))
    assert [it.n_item for it in nfe.itens] == [1, 2, 3]
    assert nfe.itens[1].ncm == "22222222"
    assert nfe.itens[1].quantidade == Decimal("3.5")
    assert nfe.itens[2].cfop == "5405"


def test_parse_item_sem_impostos() -> None:
    """Item com bloco <imposto/> vazio — campos opcionais ficam None."""
    det = """
    <det nItem="1">
      <prod>
        <cProd>X</cProd><xProd>Servico</xProd>
        <CFOP>5933</CFOP>
        <uCom>SV</uCom><qCom>1</qCom>
        <vUnCom>500</vUnCom><vProd>500.00</vProd>
      </prod>
      <imposto/>
    </det>
    """
    nfe = parse_xml_nfe(_nfe_com_itens(det))
    item = nfe.itens[0]
    assert item.ncm is None  # NF-e sem NCM
    assert item.cst_icms is None
    assert item.cst_pis is None
    assert item.cst_cofins is None
    assert item.valor_icms is None
    assert item.valor_pis is None
    assert item.valor_cofins is None


def test_parse_item_simples_nacional_csosn() -> None:
    """Item de empresa SN usa <CSOSN> em vez de <CST> no bloco ICMS."""
    det = """
    <det nItem="1">
      <prod>
        <cProd>SN1</cProd><xProd>Produto SN</xProd>
        <NCM>12345678</NCM><CFOP>5102</CFOP>
        <uCom>UN</uCom><qCom>1</qCom>
        <vUnCom>1000</vUnCom><vProd>1000.00</vProd>
      </prod>
      <imposto>
        <ICMS>
          <ICMSSN102>
            <CSOSN>102</CSOSN>
          </ICMSSN102>
        </ICMS>
      </imposto>
    </det>
    """
    nfe = parse_xml_nfe(_nfe_com_itens(det))
    assert nfe.itens[0].cst_icms == "102"  # CSOSN lido como cst_icms


def test_parse_item_com_cbs_ibs() -> None:
    """Item com extensão IBSCBS — valor_cbs/valor_ibs preenchidos."""
    det = """
    <det nItem="1">
      <prod>
        <cProd>R1</cProd><xProd>Produto Reforma</xProd>
        <NCM>12345678</NCM><CFOP>5102</CFOP>
        <uCom>UN</uCom><qCom>1</qCom>
        <vUnCom>1000</vUnCom><vProd>1000.00</vProd>
      </prod>
      <imposto>
        <IBSCBS>
          <cClassTrib>000001</cClassTrib>
          <vCBS>27.00</vCBS>
          <vIBS>5.50</vIBS>
        </IBSCBS>
      </imposto>
    </det>
    """
    nfe = parse_xml_nfe(_nfe_com_itens(det))
    assert nfe.itens[0].valor_cbs == Decimal("27.00")
    assert nfe.itens[0].valor_ibs == Decimal("5.50")


def test_parse_item_invalido_pulado_silenciosamente() -> None:
    """Item sem <xProd> ou com nItem ausente é pulado sem quebrar a NF."""
    det = """
    <det nItem="1">
      <prod>
        <cProd>OK</cProd><xProd>OK Item</xProd>
        <CFOP>5102</CFOP>
        <uCom>UN</uCom><qCom>1</qCom>
        <vUnCom>100</vUnCom><vProd>100.00</vProd>
      </prod>
      <imposto/>
    </det>
    <det nItem="2">
      <prod>
        <cProd>SEM_DESC</cProd>
        <CFOP>5102</CFOP>
        <uCom>UN</uCom><qCom>1</qCom>
        <vUnCom>50</vUnCom><vProd>50.00</vProd>
      </prod>
      <imposto/>
    </det>
    """
    nfe = parse_xml_nfe(_nfe_com_itens(det))
    # Só o item 1 entrou; item 2 (sem xProd) foi pulado.
    assert len(nfe.itens) == 1
    assert nfe.itens[0].n_item == 1


def test_cabecalho_continua_funcionando_apos_itens() -> None:
    """Retrocompat: campos agregados do cabeçalho continuam preenchidos."""
    nfe = parse_xml_nfe(_nfe_com_itens(_DET_UM_ITEM))
    # Itens novos + cabeçalho intacto (smoke retrocompat).
    assert nfe.cfop == "5102"
    assert nfe.ncm == "84713012"
    assert nfe.valor_total == Decimal("1000.00")
    assert nfe.valor_icms == Decimal("120.00")
    assert len(nfe.itens) == 1


def test_nfe_sem_itens_lista_vazia() -> None:
    """NF-e sem nenhum <det> (cenário defensivo) — itens=[] sem quebrar."""
    xml = _nfe_com_itens("").decode("utf-8")
    # Garante que o template realmente ficou sem <det>.
    assert "<det" not in xml
    nfe = parse_xml_nfe(xml.encode("utf-8"))
    assert nfe.itens == []
