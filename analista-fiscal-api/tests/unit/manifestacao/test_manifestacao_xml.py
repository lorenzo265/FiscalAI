"""Golden tests — gerador XML MD-e (Manifestação do Destinatário NF-e).

Cobre os 4 tipos de evento + validações de edge cases.

Fonte normativa: NT 2014.002 v1.10 / NT 2020.001 v1.10.

Invariantes verificadas:
  * Id = "ID" + tpEvento(6) + chNFe(44) + nSeqEvento(2d) → 54 chars.
  * cOrgao = 91 (Ambiente Nacional — NT 2014.002 §4.1.1).
  * descEvento correto por tipo (sem acentuação, conforme XSD SEFAZ).
  * 210240 gera <xJust>; 210200/10/20 NÃO geram <xJust>.
  * dhEvento em ISO-8601 com offset de fuso.
  * Namespace = http://www.portalfiscal.inf.br/nfe.
  * ALGORITMO_VERSAO presente.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.modules.manifestacao.manifestacao_xml import (
    _DESC_EVENTO,
    ALGORITMO_VERSAO,
    desc_evento,
    gerar_id_infevento,
    gerar_xml_evento,
)

_TZ_BR = ZoneInfo("America/Sao_Paulo")
_DH = datetime(2026, 6, 29, 14, 0, 0, tzinfo=_TZ_BR)

# Chave NF-e fictícia (44 dígitos)
_CHAVE = "35260612345678000195550010000123451234567890"
_CNPJ = "12345678000195"

_NS = "http://www.portalfiscal.inf.br/nfe"


def _parse(xml_str: str) -> ET.Element:
    """Parsa a string XML e devolve o elemento raiz."""
    return ET.fromstring(xml_str)


def _find(root: ET.Element, *path: str) -> ET.Element | None:
    """Navega pela árvore XML ignorando namespace."""
    el: ET.Element | None = root
    for tag in path:
        if el is None:
            return None
        nxt: ET.Element | None = None
        for child in el:
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if local == tag:
                nxt = child
                break
        el = nxt
    return el


def _text(root: ET.Element, *path: str) -> str | None:
    el = _find(root, *path)
    return el.text if el is not None else None


class TestAlgoritmoVersao:
    def test_constante_presente(self) -> None:
        assert ALGORITMO_VERSAO == "mde.xml.v1"


class TestDescEvento:
    def test_confirmacao(self) -> None:
        assert desc_evento("210200") == "Confirmacao da Operacao"

    def test_ciencia(self) -> None:
        assert desc_evento("210210") == "Ciencia da Operacao"

    def test_desconhecimento(self) -> None:
        assert desc_evento("210220") == "Desconhecimento da Operacao"

    def test_nao_realizada(self) -> None:
        assert desc_evento("210240") == "Operacao nao Realizada"

    def test_tipo_invalido_levanta(self) -> None:
        with pytest.raises(ValueError, match="tipo_evento desconhecido"):
            desc_evento("999999")


class TestGeradorId:
    def test_formato_confirmacao(self) -> None:
        id_ = gerar_id_infevento("210200", _CHAVE, 1)
        assert id_ == f"ID210200{_CHAVE}01"
        assert len(id_) == 54  # 2 + 6 + 44 + 2

    def test_formato_nao_realizada(self) -> None:
        id_ = gerar_id_infevento("210240", _CHAVE, 3)
        assert id_ == f"ID210240{_CHAVE}03"
        assert len(id_) == 54

    def test_sequencial_zero_padded(self) -> None:
        id_ = gerar_id_infevento("210210", _CHAVE, 7)
        assert id_.endswith("07")

    def test_sequencial_dois_digitos(self) -> None:
        id_ = gerar_id_infevento("210220", _CHAVE, 20)
        assert id_.endswith("20")


class TestGeradorXmlConfirmacao:
    """Tipo 210200 — Confirmação da Operação."""

    def test_xml_e_id(self) -> None:
        xml_str, id_infevento = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",  # homologação
            dh_evento=_DH,
        )
        assert id_infevento == f"ID210200{_CHAVE}01"
        assert len(id_infevento) == 54
        assert isinstance(xml_str, str)

    def test_namespace(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        assert "portalfiscal.inf.br/nfe" in xml_str

    def test_c_orgao_91(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        assert _text(root, "evento", "infEvento", "cOrgao") == "91"

    def test_tp_amb_homolog(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        assert _text(root, "evento", "infEvento", "tpAmb") == "2"

    def test_cnpj_no_xml(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        assert _text(root, "evento", "infEvento", "CNPJ") == _CNPJ

    def test_chave_nfe_no_xml(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        assert _text(root, "evento", "infEvento", "chNFe") == _CHAVE

    def test_tp_evento_no_xml(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        assert _text(root, "evento", "infEvento", "tpEvento") == "210200"

    def test_desc_evento_confirmacao(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        assert (
            _text(root, "evento", "infEvento", "detEvento", "descEvento")
            == "Confirmacao da Operacao"
        )

    def test_sem_xjust(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        assert "<xJust>" not in xml_str

    def test_n_seq_evento(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=3,
            tp_amb="2",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        assert _text(root, "evento", "infEvento", "nSeqEvento") == "3"

    def test_dh_evento_aware(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        dh = _text(root, "evento", "infEvento", "dhEvento")
        assert dh is not None
        # Deve conter offset de fuso (ex: -03:00 ou -0300)
        assert "-03" in dh or "+00" in dh, f"dhEvento sem offset de fuso: {dh!r}"

    def test_determinismo(self) -> None:
        """Mesmos inputs → mesmo XML."""
        xml1, id1 = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        xml2, id2 = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        assert xml1 == xml2
        assert id1 == id2


class TestGeradorXmlCiencia:
    """Tipo 210210 — Ciência da Operação."""

    def test_desc_evento(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210210",
            sequencial=1,
            tp_amb="1",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        assert (
            _text(root, "evento", "infEvento", "detEvento", "descEvento")
            == "Ciencia da Operacao"
        )

    def test_id_tipo_210210(self) -> None:
        _, id_infevento = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210210",
            sequencial=1,
            tp_amb="1",
            dh_evento=_DH,
        )
        assert id_infevento.startswith("ID210210")
        assert len(id_infevento) == 54


class TestGeradorXmlDesconhecimento:
    """Tipo 210220 — Desconhecimento da Operação."""

    def test_desc_evento(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210220",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        assert (
            _text(root, "evento", "infEvento", "detEvento", "descEvento")
            == "Desconhecimento da Operacao"
        )

    def test_sem_xjust(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210220",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        assert "<xJust>" not in xml_str


class TestGeradorXmlNaoRealizada:
    """Tipo 210240 — Operação não Realizada (com justificativa)."""

    _JUST = "Mercadoria nao recebida conforme pedido numero 12345"

    def test_desc_evento(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210240",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
            justificativa=self._JUST,
        )
        root = _parse(xml_str)
        assert (
            _text(root, "evento", "infEvento", "detEvento", "descEvento")
            == "Operacao nao Realizada"
        )

    def test_xjust_presente(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210240",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
            justificativa=self._JUST,
        )
        root = _parse(xml_str)
        assert (
            _text(root, "evento", "infEvento", "detEvento", "xJust") == self._JUST
        )

    def test_id_tipo_210240(self) -> None:
        _, id_infevento = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210240",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
            justificativa=self._JUST,
        )
        assert id_infevento.startswith("ID210240")
        assert len(id_infevento) == 54

    def test_c_orgao_91(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210240",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
            justificativa=self._JUST,
        )
        root = _parse(xml_str)
        assert _text(root, "evento", "infEvento", "cOrgao") == "91"


class TestValidacaoEntrada:
    """Erros de entrada levantam ValueError (antes de qualquer I/O)."""

    def test_chave_curta_levanta(self) -> None:
        with pytest.raises(ValueError, match="44 dígitos"):
            gerar_xml_evento(
                cnpj_destinatario=_CNPJ,
                chave_nfe="12345",  # muito curta
                tipo_evento="210200",
                sequencial=1,
                tp_amb="2",
                dh_evento=_DH,
            )

    def test_chave_com_letras_levanta(self) -> None:
        with pytest.raises(ValueError, match="44 dígitos"):
            gerar_xml_evento(
                cnpj_destinatario=_CNPJ,
                chave_nfe="A" * 44,
                tipo_evento="210200",
                sequencial=1,
                tp_amb="2",
                dh_evento=_DH,
            )

    def test_tipo_invalido_levanta(self) -> None:
        with pytest.raises(ValueError, match="tipo_evento inválido"):
            gerar_xml_evento(
                cnpj_destinatario=_CNPJ,
                chave_nfe=_CHAVE,
                tipo_evento="000000",
                sequencial=1,
                tp_amb="2",
                dh_evento=_DH,
            )

    def test_nao_realizada_sem_justificativa_levanta(self) -> None:
        """210240 sem justificativa deve levantar ValueError."""
        with pytest.raises(ValueError, match="210240 exige justificativa"):
            gerar_xml_evento(
                cnpj_destinatario=_CNPJ,
                chave_nfe=_CHAVE,
                tipo_evento="210240",
                sequencial=1,
                tp_amb="2",
                dh_evento=_DH,
                justificativa=None,
            )

    def test_210200_com_justificativa_levanta(self) -> None:
        """Tipos sem justificativa não aceitam xJust."""
        with pytest.raises(ValueError, match="não aceita justificativa"):
            gerar_xml_evento(
                cnpj_destinatario=_CNPJ,
                chave_nfe=_CHAVE,
                tipo_evento="210200",
                sequencial=1,
                tp_amb="2",
                dh_evento=_DH,
                justificativa="Justificativa nao permitida aqui",
            )

    def test_justificativa_muito_curta_levanta(self) -> None:
        with pytest.raises(ValueError, match="entre 15 e 255"):
            gerar_xml_evento(
                cnpj_destinatario=_CNPJ,
                chave_nfe=_CHAVE,
                tipo_evento="210240",
                sequencial=1,
                tp_amb="2",
                dh_evento=_DH,
                justificativa="curta",  # < 15 chars
            )

    def test_justificativa_muito_longa_levanta(self) -> None:
        with pytest.raises(ValueError, match="entre 15 e 255"):
            gerar_xml_evento(
                cnpj_destinatario=_CNPJ,
                chave_nfe=_CHAVE,
                tipo_evento="210240",
                sequencial=1,
                tp_amb="2",
                dh_evento=_DH,
                justificativa="x" * 256,  # > 255 chars
            )

    def test_sequencial_zero_levanta(self) -> None:
        with pytest.raises(ValueError, match="sequencial deve ser entre 1 e 20"):
            gerar_xml_evento(
                cnpj_destinatario=_CNPJ,
                chave_nfe=_CHAVE,
                tipo_evento="210200",
                sequencial=0,
                tp_amb="2",
                dh_evento=_DH,
            )

    def test_sequencial_21_levanta(self) -> None:
        with pytest.raises(ValueError, match="sequencial deve ser entre 1 e 20"):
            gerar_xml_evento(
                cnpj_destinatario=_CNPJ,
                chave_nfe=_CHAVE,
                tipo_evento="210200",
                sequencial=21,
                tp_amb="2",
                dh_evento=_DH,
            )

    def test_tp_amb_invalido_levanta(self) -> None:
        with pytest.raises(ValueError, match="tp_amb"):
            gerar_xml_evento(
                cnpj_destinatario=_CNPJ,
                chave_nfe=_CHAVE,
                tipo_evento="210200",
                sequencial=1,
                tp_amb="3",  # inválido
                dh_evento=_DH,
            )

    def test_datetime_naive_levanta(self) -> None:
        from datetime import datetime as dt
        naive = dt(2026, 6, 29, 14, 0, 0)  # sem tzinfo
        with pytest.raises(ValueError, match="aware"):
            gerar_xml_evento(
                cnpj_destinatario=_CNPJ,
                chave_nfe=_CHAVE,
                tipo_evento="210200",
                sequencial=1,
                tp_amb="2",
                dh_evento=naive,
            )

    def test_cnpj_invalido_levanta(self) -> None:
        with pytest.raises(ValueError, match="14 dígitos"):
            gerar_xml_evento(
                cnpj_destinatario="1234",  # muito curto
                chave_nfe=_CHAVE,
                tipo_evento="210200",
                sequencial=1,
                tp_amb="2",
                dh_evento=_DH,
            )


class TestGoldenStructure:
    """Verifica a estrutura completa do XML gerado (golden snapshot parcial)."""

    def test_versao_evento_e_det(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        # verEvento = 1.00
        assert _text(root, "evento", "infEvento", "verEvento") == "1.00"
        # detEvento[versao] = 1.00
        inf = _find(root, "evento", "infEvento")
        assert inf is not None
        det = _find(inf, "detEvento")
        assert det is not None
        assert det.attrib.get("versao") == "1.00"

    def test_id_lote_presente(self) -> None:
        xml_str, _ = gerar_xml_evento(
            cnpj_destinatario=_CNPJ,
            chave_nfe=_CHAVE,
            tipo_evento="210200",
            sequencial=1,
            tp_amb="2",
            dh_evento=_DH,
        )
        root = _parse(xml_str)
        id_lote = _text(root, "idLote")
        assert id_lote is not None
        assert id_lote.isdigit()
        assert len(id_lote) <= 15

    def test_todos_4_tipos_desc_mapa(self) -> None:
        """Todos os tipos têm mapeamento de descEvento."""
        tipos = ["210200", "210210", "210220", "210240"]
        descs_esperados = [
            "Confirmacao da Operacao",
            "Ciencia da Operacao",
            "Desconhecimento da Operacao",
            "Operacao nao Realizada",
        ]
        for tipo, desc_exp in zip(tipos, descs_esperados, strict=False):
            assert _DESC_EVENTO[tipo] == desc_exp
