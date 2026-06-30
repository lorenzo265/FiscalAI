"""Inspeção pura de um certificado A1 (.p12 ICP-Brasil).

Abre o PKCS#12 com a senha, valida e extrai metadados — CN do titular, CNPJ
(quando presente), validade (aware) e fingerprint SHA-256. Função pura, sem
I/O nem DB: golden-testável. Só usa ``cryptography`` (dependência core), então
roda **sem** o grupo opt-in ``esocial`` (que é necessário só para assinar).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs12

from app.shared.exceptions import CertificadoA1Invalido

ALGORITMO_VERSAO = "cert_a1.inspecao.v1"

# OID do e-CNPJ no SubjectAltName/otherName (ICP-Brasil DOC-ICP-04).
_OID_CNPJ_ICP = "2.16.76.1.3.3"
_RE_CNPJ = re.compile(rb"\d{14}")


@dataclass(frozen=True)
class CertInfoA1:
    """Metadados extraídos de um certificado A1 (sem material sensível)."""

    cn_titular: str
    cnpj_titular: str | None
    validade_inicio: datetime
    validade_fim: datetime
    fingerprint: str


def _extrair_cn(cert: x509.Certificate) -> str:
    attrs = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    if not attrs:
        return ""
    valor = attrs[0].value
    return valor if isinstance(valor, str) else valor.decode("utf-8", "replace")


def _extrair_cnpj(cert: x509.Certificate) -> str | None:
    """CNPJ do titular: 1º do SAN otherName OID 2.16.76.1.3.3, senão do CN."""
    try:
        san = cert.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
    except x509.ExtensionNotFound:
        san = None
    if san is not None:
        for other in san.get_values_for_type(x509.OtherName):
            if other.type_id.dotted_string == _OID_CNPJ_ICP:
                achado = _RE_CNPJ.search(other.value)
                if achado is not None:
                    return achado.group().decode("ascii")
    # Fallback: CN no formato "RAZAO SOCIAL:CNPJ".
    cn = _extrair_cn(cert)
    achado_cn = re.search(r"\d{14}", cn)
    return achado_cn.group() if achado_cn is not None else None


def inspecionar_p12(pfx_bytes: bytes, senha: str) -> CertInfoA1:
    """Abre o .p12 com a senha e devolve seus metadados.

    Raises:
        CertificadoA1Invalido: senha errada, arquivo corrompido ou sem cert.
    """
    try:
        _key, cert, _extras = pkcs12.load_key_and_certificates(
            pfx_bytes, senha.encode("utf-8")
        )
    except (ValueError, TypeError) as exc:
        raise CertificadoA1Invalido(
            "Não foi possível abrir o certificado com a senha informada."
        ) from exc
    if cert is None:
        raise CertificadoA1Invalido(
            "O arquivo enviado não contém um certificado válido."
        )
    return CertInfoA1(
        cn_titular=_extrair_cn(cert),
        cnpj_titular=_extrair_cnpj(cert),
        validade_inicio=cert.not_valid_before_utc,
        validade_fim=cert.not_valid_after_utc,
        fingerprint=cert.fingerprint(hashes.SHA256()).hex(),
    )
