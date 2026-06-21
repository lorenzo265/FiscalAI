"""Testes golden — reconciliação de NF-e na ingestão (Auditoria Onda C).

Cobre:
  Tarefa 1 — Σ(itens.vProd) vs ICMSTot.vProd (reconciliação bloqueante).
  Tarefa 2 — normalização de formato de CFOP/NCM no cabeçalho (lenient).
  Tarefa 3 — log de aviso CST×CSOSN vs CRT (não-bloqueante).

Fixtures construídas com templates próprios (concatenação de strings, sem
``<?xml?>`` em offset errado). O ``<?xml?>`` está na posição 0 da string
concatenada — sem espaço ou quebra de linha antes.

Para os testes de log (Tarefa 3), usamos ``structlog.testing.capture_logs()``
em vez de ``pytest.caplog`` — structlog não roteia para o logging stdlib por
padrão, e ``capture_logs()`` é o mecanismo canônico de teste do structlog.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import structlog.testing

from app.modules.ingestao.parser import XmlNFeInvalido, parse_xml_nfe

# ── Template base (sem vProd no ICMSTot) — igual ao de test_parser_itens ──────
# Usado nos testes de Tarefa 2 e 3, onde ICMSTot.vProd está ausente e a
# reconciliação é portanto pulada.

_TEMPLATE_SEM_VPROD = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
    "<NFe>"
    '<infNFe Id="NFe35260512345678000195550010000001231000001231" versao="4.00">'
    "<ide>"
    "<mod>55</mod><serie>1</serie><nNF>123</nNF>"
    "<dhEmi>2026-05-01T10:00:00-03:00</dhEmi>"
    "<natOp>Venda</natOp>"
    "</ide>"
    "<emit><CNPJ>12345678000195</CNPJ><CRT>{crt}</CRT></emit>"
    "<dest><CNPJ>98765432000181</CNPJ></dest>"
    "{itens}"
    "<total><ICMSTot>"
    "<vNF>{v_nf}</vNF><vICMS>0.00</vICMS><vIPI>0.00</vIPI>"
    "<vPIS>0.00</vPIS><vCOFINS>0.00</vCOFINS>"
    "</ICMSTot></total>"
    "</infNFe>"
    "<Signature/>"
    "</NFe>"
    '<protNFe versao="4.00"><infProt>'
    "<chNFe>35260512345678000195550010000001231000001231</chNFe>"
    "<nProt>1</nProt><dhRecbto>2026-05-01T10:01:00-03:00</dhRecbto><cStat>100</cStat>"
    "</infProt></protNFe>"
    "</nfeProc>"
)

# ── Template COM vProd no ICMSTot — para testes de reconciliação (Tarefa 1) ───
# vProd_icmstot: o vProd declarado no ICMSTot (soma dos produtos).
# v_nf: o vNF (pode diferir de vProd_icmstot quando há desconto/frete).
# Separar os dois permite provar que a validação usa vProd, não vNF.

_TEMPLATE_COM_VPROD = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
    "<NFe>"
    '<infNFe Id="NFe35260512345678000195550010000001231000001231" versao="4.00">'
    "<ide>"
    "<mod>55</mod><serie>1</serie><nNF>123</nNF>"
    "<dhEmi>2026-05-01T10:00:00-03:00</dhEmi>"
    "<natOp>Venda</natOp>"
    "</ide>"
    "<emit><CNPJ>12345678000195</CNPJ><CRT>3</CRT></emit>"
    "<dest><CNPJ>98765432000181</CNPJ></dest>"
    "{itens}"
    "<total><ICMSTot>"
    "<vProd>{vProd_icmstot}</vProd>"
    "<vNF>{v_nf}</vNF><vICMS>0.00</vICMS><vIPI>0.00</vIPI>"
    "<vPIS>0.00</vPIS><vCOFINS>0.00</vCOFINS>"
    "</ICMSTot></total>"
    "</infNFe>"
    "<Signature/>"
    "</NFe>"
    '<protNFe versao="4.00"><infProt>'
    "<chNFe>35260512345678000195550010000001231000001231</chNFe>"
    "<nProt>1</nProt><dhRecbto>2026-05-01T10:01:00-03:00</dhRecbto><cStat>100</cStat>"
    "</infProt></protNFe>"
    "</nfeProc>"
)


def _nfe_com_vprod(
    itens_xml: str,
    vProd_icmstot: str,
    v_nf: str,
) -> bytes:
    """Monta NF-e com ICMSTot.vProd explícito (para teste de reconciliação)."""
    return _TEMPLATE_COM_VPROD.format(
        itens=itens_xml,
        vProd_icmstot=vProd_icmstot,
        v_nf=v_nf,
    ).encode("utf-8")


def _nfe_sem_vprod(
    itens_xml: str,
    v_nf: str = "1000.00",
    crt: str = "3",
) -> bytes:
    """Monta NF-e SEM ICMSTot.vProd (reconciliação deve ser pulada)."""
    return _TEMPLATE_SEM_VPROD.format(
        itens=itens_xml,
        v_nf=v_nf,
        crt=crt,
    ).encode("utf-8")


# ── Blocos <det> reutilizáveis ──────────────────────────────────────────────

_DET_100 = (
    '<det nItem="1">'
    "<prod>"
    "<cProd>P001</cProd><xProd>Produto A</xProd>"
    "<NCM>12345678</NCM><CFOP>5102</CFOP>"
    "<uCom>UN</uCom><qCom>1</qCom>"
    "<vUnCom>100.00</vUnCom><vProd>100.00</vProd>"
    "</prod>"
    "<imposto/>"
    "</det>"
)

_DET_900 = (
    '<det nItem="1">'
    "<prod>"
    "<cProd>P001</cProd><xProd>Produto A</xProd>"
    "<NCM>12345678</NCM><CFOP>5102</CFOP>"
    "<uCom>UN</uCom><qCom>1</qCom>"
    "<vUnCom>900.00</vUnCom><vProd>900.00</vProd>"
    "</prod>"
    "<imposto/>"
    "</det>"
)

_DET_1000 = (
    '<det nItem="1">'
    "<prod>"
    "<cProd>P001</cProd><xProd>Produto A</xProd>"
    "<NCM>12345678</NCM><CFOP>5102</CFOP>"
    "<uCom>UN</uCom><qCom>1</qCom>"
    "<vUnCom>1000.00</vUnCom><vProd>1000.00</vProd>"
    "</prod>"
    "<imposto/>"
    "</det>"
)

_DET_1000_COM_CST = (
    '<det nItem="1">'
    "<prod>"
    "<cProd>P001</cProd><xProd>Produto A</xProd>"
    "<NCM>12345678</NCM><CFOP>5102</CFOP>"
    "<uCom>UN</uCom><qCom>1</qCom>"
    "<vUnCom>1000.00</vUnCom><vProd>1000.00</vProd>"
    "</prod>"
    "<imposto>"
    "<ICMS><ICMS00><CST>00</CST></ICMS00></ICMS>"
    "</imposto>"
    "</det>"
)

# ── Tarefa 1 — Reconciliação Σ(itens) vs ICMSTot.vProd ────────────────────────


def test_soma_itens_igual_vprod_aceita() -> None:
    """Σ itens == ICMSTot.vProd → parse bem-sucedido."""
    nfe = parse_xml_nfe(_nfe_com_vprod(_DET_1000, vProd_icmstot="1000.00", v_nf="1000.00"))
    assert len(nfe.itens) == 1
    assert nfe.itens[0].valor_total == Decimal("1000.00")


def test_soma_itens_diverge_vprod_em_cinco_centavos_rejeita() -> None:
    """Σ itens diverge de ICMSTot.vProd em R$0,05 → XmlNFeInvalido.

    Item declara vProd=900.00 mas ICMSTot.vProd=900.05 (diferença 0,05 > tolerância 0,02).
    """
    det_900_05 = (
        '<det nItem="1">'
        "<prod>"
        "<cProd>P001</cProd><xProd>Produto A</xProd>"
        "<NCM>12345678</NCM><CFOP>5102</CFOP>"
        "<uCom>UN</uCom><qCom>1</qCom>"
        "<vUnCom>900.00</vUnCom><vProd>900.00</vProd>"
        "</prod>"
        "<imposto/>"
        "</det>"
    )
    with pytest.raises(XmlNFeInvalido, match="total dos itens"):
        parse_xml_nfe(_nfe_com_vprod(det_900_05, vProd_icmstot="900.05", v_nf="900.05"))


def test_divergencia_exatamente_dois_centavos_aceita() -> None:
    """Divergência de exatamente R$0,02 está dentro da tolerância → aceita."""
    det_100_00 = (
        '<det nItem="1">'
        "<prod>"
        "<cProd>P001</cProd><xProd>Produto A</xProd>"
        "<NCM>12345678</NCM><CFOP>5102</CFOP>"
        "<uCom>UN</uCom><qCom>1</qCom>"
        "<vUnCom>100.00</vUnCom><vProd>100.00</vProd>"
        "</prod>"
        "<imposto/>"
        "</det>"
    )
    # Σ itens = 100.00, ICMSTot.vProd = 100.02 → diferença 0.02 (não excede)
    nfe = parse_xml_nfe(_nfe_com_vprod(det_100_00, vProd_icmstot="100.02", v_nf="100.02"))
    assert len(nfe.itens) == 1


def test_nota_com_desconto_soma_itens_igual_vprod_aceita() -> None:
    """Nota com desconto: vNF < vProd mas Σitens == ICMSTot.vProd → aceita.

    Prova que a validação usa ICMSTot.vProd (soma bruta de produtos) e
    NÃO usa vNF (que seria vProd − desconto). Esse era o erro da 1ª tentativa.
    vNF = 950.00 (com desconto de 50), ICMSTot.vProd = 1000.00, Σitens = 1000.00.
    """
    nfe = parse_xml_nfe(_nfe_com_vprod(_DET_1000, vProd_icmstot="1000.00", v_nf="950.00"))
    assert nfe.itens[0].valor_total == Decimal("1000.00")
    # valor_total do cabeçalho vem de vNF (comportamento retrocompat)
    assert nfe.valor_total == Decimal("950.00")


def test_reconciliacao_pulada_quando_vprod_ausente_no_icmstot() -> None:
    """Se ICMSTot não tem <vProd>, reconciliação é pulada → sem exceção.

    Cobre o caso dos testes legados em test_parser_itens.py que usam o
    _NFE_TEMPLATE sem vProd no ICMSTot.
    """
    # _DET_1000 soma 1000.00, mas ICMSTot não tem vProd → skip da validação
    nfe = parse_xml_nfe(_nfe_sem_vprod(_DET_1000, v_nf="1000.00"))
    assert len(nfe.itens) == 1


def test_reconciliacao_pulada_quando_sem_itens() -> None:
    """NF-e sem itens parseados → reconciliação pulada mesmo com vProd presente.

    Cobre fixtures legadas sem <xProd> (det pulado silenciosamente).
    """
    # Item sem <xProd> é pulado → itens == [] → reconciliação não ocorre
    det_sem_descricao = (
        '<det nItem="1">'
        "<prod>"
        "<cProd>SEM_DESC</cProd>"
        "<NCM>12345678</NCM><CFOP>5102</CFOP>"
        "<uCom>UN</uCom><qCom>1</qCom>"
        "<vUnCom>1000.00</vUnCom><vProd>1000.00</vProd>"
        "</prod>"
        "<imposto/>"
        "</det>"
    )
    nfe = parse_xml_nfe(_nfe_com_vprod(det_sem_descricao, vProd_icmstot="1000.00", v_nf="1000.00"))
    assert nfe.itens == []


# ── Tarefa 2 — CFOP/NCM do cabeçalho com normalização de formato ──────────────


def test_cfop_tres_digitos_no_cabecalho_vira_none() -> None:
    """CFOP de 3 dígitos no primeiro <det> → cabeçalho.cfop = None (sem exceção)."""
    det_cfop_curto = (
        '<det nItem="1">'
        "<prod>"
        "<cProd>P001</cProd><xProd>Produto A</xProd>"
        "<NCM>12345678</NCM><CFOP>510</CFOP>"
        "<uCom>UN</uCom><qCom>1</qCom>"
        "<vUnCom>100.00</vUnCom><vProd>100.00</vProd>"
        "</prod>"
        "<imposto/>"
        "</det>"
    )
    nfe = parse_xml_nfe(_nfe_sem_vprod(det_cfop_curto, v_nf="100.00"))
    assert nfe.cfop is None  # normalizado para None por formato inválido
    # mas o item em si — _parse_item faz a mesma validação → também None
    assert nfe.itens[0].cfop is None


def test_ncm_quatro_digitos_no_cabecalho_vira_none() -> None:
    """NCM de 4 dígitos no primeiro <det> → cabeçalho.ncm = None (sem exceção)."""
    det_ncm_curto = (
        '<det nItem="1">'
        "<prod>"
        "<cProd>P001</cProd><xProd>Produto A</xProd>"
        "<NCM>1234</NCM><CFOP>5102</CFOP>"
        "<uCom>UN</uCom><qCom>1</qCom>"
        "<vUnCom>100.00</vUnCom><vProd>100.00</vProd>"
        "</prod>"
        "<imposto/>"
        "</det>"
    )
    nfe = parse_xml_nfe(_nfe_sem_vprod(det_ncm_curto, v_nf="100.00"))
    assert nfe.ncm is None  # normalizado para None por formato inválido
    assert nfe.itens[0].ncm is None


def test_cfop_nao_numerico_no_cabecalho_vira_none() -> None:
    """CFOP não-numérico (ex.: 'ABCD') → None (sem exceção)."""
    det_cfop_alpha = (
        '<det nItem="1">'
        "<prod>"
        "<cProd>P001</cProd><xProd>Produto A</xProd>"
        "<NCM>12345678</NCM><CFOP>ABCD</CFOP>"
        "<uCom>UN</uCom><qCom>1</qCom>"
        "<vUnCom>100.00</vUnCom><vProd>100.00</vProd>"
        "</prod>"
        "<imposto/>"
        "</det>"
    )
    nfe = parse_xml_nfe(_nfe_sem_vprod(det_cfop_alpha, v_nf="100.00"))
    assert nfe.cfop is None


def test_cfop_ncm_validos_no_cabecalho_preservados() -> None:
    """CFOP 4 dígitos e NCM 8 dígitos → preservados no cabeçalho."""
    nfe = parse_xml_nfe(_nfe_sem_vprod(_DET_1000, v_nf="1000.00"))
    assert nfe.cfop == "5102"
    assert nfe.ncm == "12345678"


# ── Tarefa 3 — CST×CSOSN vs CRT: log de aviso não-bloqueante ─────────────────


def test_crt1_com_cst_dois_digitos_loga_aviso_e_nao_rejeita() -> None:
    """CRT=1 (Simples Nacional) com CST de 2 dígitos → parse OK + log de aviso.

    CST '00' é código de regime Normal. SN deveria usar CSOSN (3 dígitos).
    O parser NÃO rejeita — apenas emite log estruturado via structlog.
    Usamos ``structlog.testing.capture_logs()`` (mecanismo canônico do structlog).
    """
    with structlog.testing.capture_logs() as cap_logs:
        # CRT=1 com CST '00' (2 dígitos) — incoerente mas não bloqueante
        nfe = parse_xml_nfe(_nfe_sem_vprod(_DET_1000_COM_CST, v_nf="1000.00", crt="1"))

    # Parse deve ter sucesso
    assert len(nfe.itens) == 1
    assert nfe.itens[0].cst_icms == "00"
    assert nfe.crt == "1"
    # Aviso deve ter sido registrado com o evento correto
    avisos = [e for e in cap_logs if e.get("event") == "ingestao.cst_csosn_incoerente"]
    assert len(avisos) >= 1
    assert avisos[0]["log_level"] == "warning"
    assert avisos[0]["crt"] == "1"
    assert avisos[0]["codigo"] == "00"


def test_crt3_com_csosn_tres_digitos_loga_aviso_e_nao_rejeita() -> None:
    """CRT=3 (Regime Normal) com CSOSN de 3 dígitos → parse OK + log de aviso."""
    det_csosn = (
        '<det nItem="1">'
        "<prod>"
        "<cProd>P001</cProd><xProd>Produto A</xProd>"
        "<NCM>12345678</NCM><CFOP>5102</CFOP>"
        "<uCom>UN</uCom><qCom>1</qCom>"
        "<vUnCom>1000.00</vUnCom><vProd>1000.00</vProd>"
        "</prod>"
        "<imposto>"
        "<ICMS><ICMSSN102><CSOSN>102</CSOSN></ICMSSN102></ICMS>"
        "</imposto>"
        "</det>"
    )
    with structlog.testing.capture_logs() as cap_logs:
        nfe = parse_xml_nfe(_nfe_sem_vprod(det_csosn, v_nf="1000.00", crt="3"))

    assert len(nfe.itens) == 1
    assert nfe.itens[0].cst_icms == "102"
    avisos = [e for e in cap_logs if e.get("event") == "ingestao.cst_csosn_incoerente"]
    assert len(avisos) >= 1
    assert avisos[0]["log_level"] == "warning"
    assert avisos[0]["crt"] == "3"
    assert avisos[0]["codigo"] == "102"


def test_crt1_com_csosn_correto_nao_loga_aviso() -> None:
    """CRT=1 com CSOSN correto (3 dígitos) → sem aviso de incoerência."""
    det_csosn_ok = (
        '<det nItem="1">'
        "<prod>"
        "<cProd>P001</cProd><xProd>Produto A</xProd>"
        "<NCM>12345678</NCM><CFOP>5102</CFOP>"
        "<uCom>UN</uCom><qCom>1</qCom>"
        "<vUnCom>1000.00</vUnCom><vProd>1000.00</vProd>"
        "</prod>"
        "<imposto>"
        "<ICMS><ICMSSN101><CSOSN>101</CSOSN></ICMSSN101></ICMS>"
        "</imposto>"
        "</det>"
    )
    with structlog.testing.capture_logs() as cap_logs:
        parse_xml_nfe(_nfe_sem_vprod(det_csosn_ok, v_nf="1000.00", crt="1"))

    avisos = [e for e in cap_logs if e.get("event") == "ingestao.cst_csosn_incoerente"]
    assert avisos == []
