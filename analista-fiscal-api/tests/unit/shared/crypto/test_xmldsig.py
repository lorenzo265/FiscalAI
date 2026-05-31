"""Testes do assinador XMLDSig (Sprint 19.7 PR2 #13).

Cobre:
  * ``hash_xml_canonico`` — determinismo + sensibilidade a 1 byte.
  * ``NotImplementedXmldsigSigner`` — fail-fast com motivo.
  * ``construir_assinador`` — escolhe factory com base em flags.
"""

from __future__ import annotations

import pytest

from app.shared.crypto.xmldsig import (
    ALGORITMO_VERSAO,
    NotImplementedXmldsigSigner,
    XmldsigSigningError,
    construir_assinador,
    hash_xml_canonico,
)


class TestHashXmlCanonico:
    def test_deterministico_mesmo_xml(self) -> None:
        xml = "<eSocial><evtRemun Id='ID1'/></eSocial>"
        assert hash_xml_canonico(xml) == hash_xml_canonico(xml)

    def test_sensivel_a_1_byte(self) -> None:
        a = "<eSocial><evtRemun Id='ID1'/></eSocial>"
        b = "<eSocial><evtRemun Id='ID2'/></eSocial>"
        assert hash_xml_canonico(a) != hash_xml_canonico(b)

    def test_retorna_hex_64_chars(self) -> None:
        h = hash_xml_canonico("<x/>")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestNotImplementedXmldsigSigner:
    def test_assinar_levanta_com_motivo(self) -> None:
        signer = NotImplementedXmldsigSigner(motivo="grupo esocial off")
        with pytest.raises(XmldsigSigningError) as ei:
            signer.assinar("<x/>", id_referencia="ID1")
        assert "grupo esocial off" in str(ei.value)
        assert "poetry install --with esocial" in str(ei.value)


class TestConstruirAssinador:
    def test_flag_desligada_retorna_not_implemented(self) -> None:
        signer = construir_assinador(
            cert_p12_bytes=b"dummy",
            senha="x",
            transmissao_ativa=False,
        )
        assert isinstance(signer, NotImplementedXmldsigSigner)
        assert "ESOCIAL_TRANSMISSAO_ATIVA=false" in signer.motivo

    def test_sem_cert_retorna_not_implemented(self) -> None:
        signer = construir_assinador(
            cert_p12_bytes=None,
            senha=None,
            transmissao_ativa=True,
        )
        assert isinstance(signer, NotImplementedXmldsigSigner)
        assert "certificado A1" in signer.motivo

    def test_com_cert_invalido_e_flag_ligada_levanta(self) -> None:
        """Sem grupo 'esocial' instalado, qualquer cert dummy falha em
        load_key_and_certificates → XmldsigSigningError com hint."""
        with pytest.raises(XmldsigSigningError):
            construir_assinador(
                cert_p12_bytes=b"not a real p12 blob",
                senha="x",
                transmissao_ativa=True,
            )


def test_algoritmo_versao_v1() -> None:
    assert ALGORITMO_VERSAO == "xmldsig.v1"
