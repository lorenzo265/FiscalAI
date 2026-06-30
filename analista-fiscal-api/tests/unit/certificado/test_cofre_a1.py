"""Unit tests do cofre A1 — inspeção pura do .p12 + round-trip do envelope.

Gera certificados PKCS#12 reais em memória (cryptography, dependência core), sem
DB nem rede. O serviço/loader contra DB + RLS vai na suíte de integração.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    pkcs12,
)
from cryptography.x509.oid import NameOID

from app.modules.certificado.inspeciona_p12 import inspecionar_p12
from app.shared.crypto.envelope import carregar_chave, cifrar, decifrar
from app.shared.exceptions import CertificadoA1Invalido

_OID_CNPJ_ICP = "2.16.76.1.3.3"
# Chave de envelope fixa (32 bytes AES-256) — independe de settings nos testes.
_CHAVE_B64 = base64.b64encode(b"x" * 32).decode("ascii")


def _gerar_p12(
    *,
    senha: str = "1234",
    cnpj: str | None = "12345678000190",
    cnpj_no_cn: bool = True,
    cnpj_no_san: bool = False,
    razao: str = "PADARIA DO BAIRRO LTDA",
    dias_validade: int = 365,
) -> bytes:
    """Monta um .p12 e-CNPJ-like (autoassinado) para os testes."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cn_value = f"{razao}:{cnpj}" if (cnpj_no_cn and cnpj) else razao
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn_value)])
    builder = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=dias_validade))
    )
    if cnpj_no_san and cnpj:
        # otherName 2.16.76.1.3.3 com o CNPJ como OCTET STRING (DER: 0x04 len ...)
        valor_der = b"\x04" + bytes([len(cnpj)]) + cnpj.encode("ascii")
        san = x509.SubjectAlternativeName(
            [x509.OtherName(x509.ObjectIdentifier(_OID_CNPJ_ICP), valor_der)]
        )
        builder = builder.add_extension(san, critical=False)
    cert = builder.sign(key, hashes.SHA256())
    return pkcs12.serialize_key_and_certificates(
        b"teste", key, cert, None, BestAvailableEncryption(senha.encode())
    )


def test_inspecionar_extrai_cn_validade_fingerprint() -> None:
    pfx = _gerar_p12(senha="segredo", dias_validade=400)
    info = inspecionar_p12(pfx, "segredo")
    assert "PADARIA DO BAIRRO LTDA" in info.cn_titular
    assert info.validade_fim > info.validade_inicio
    assert info.validade_fim > datetime.now(UTC)
    assert len(info.fingerprint) == 64  # sha256 hex
    int(info.fingerprint, 16)  # é hex válido


def test_cnpj_extraido_do_cn() -> None:
    pfx = _gerar_p12(cnpj="12345678000190", cnpj_no_cn=True, cnpj_no_san=False)
    info = inspecionar_p12(pfx, "1234")
    assert info.cnpj_titular == "12345678000190"


def test_cnpj_extraido_do_san_otherrname() -> None:
    pfx = _gerar_p12(cnpj="99888777000166", cnpj_no_cn=False, cnpj_no_san=True)
    info = inspecionar_p12(pfx, "1234")
    assert info.cnpj_titular == "99888777000166"


def test_cnpj_ausente_retorna_none() -> None:
    pfx = _gerar_p12(cnpj=None, cnpj_no_cn=False, cnpj_no_san=False)
    info = inspecionar_p12(pfx, "1234")
    assert info.cnpj_titular is None


def test_senha_errada_levanta_invalido() -> None:
    pfx = _gerar_p12(senha="certa")
    with pytest.raises(CertificadoA1Invalido):
        inspecionar_p12(pfx, "errada")


def test_arquivo_corrompido_levanta_invalido() -> None:
    with pytest.raises(CertificadoA1Invalido):
        inspecionar_p12(b"isto nao e um pkcs12", "1234")


def test_envelope_roundtrip_preserva_pfx_binario() -> None:
    """O .p12 (binário) sobrevive a cifrar(base64(.p12)) → decifrar → b64decode."""
    pfx = _gerar_p12()
    chave = carregar_chave(_CHAVE_B64)
    token = cifrar(base64.b64encode(pfx).decode("ascii"), chave)
    recuperado = base64.b64decode(decifrar(token, chave))
    assert recuperado == pfx
    # E o .p12 recuperado ainda abre.
    info = inspecionar_p12(recuperado, "1234")
    assert info.fingerprint == inspecionar_p12(pfx, "1234").fingerprint
