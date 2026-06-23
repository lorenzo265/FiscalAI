"""Primitivas criptográficas compartilhadas.

  * XMLDSig (Sprint 19.7) — assinador de eventos eSocial.
  * Envelope AES-256-GCM (Marco 3) — cifra de PII em repouso (`envelope` +
    `PiiCifrada` TypeDecorator). Chave via `settings.PII_ENCRYPTION_KEY` (KMS
    em prod). Aplicado a `empresa.whatsapp_phone` como coluna de prova.
"""

from app.shared.crypto.envelope import carregar_chave, cifrar, decifrar
from app.shared.crypto.pii_type import PiiCifrada
from app.shared.crypto.xmldsig import (
    ALGORITMO_VERSAO,
    NotImplementedXmldsigSigner,
    XmldsigSigner,
    XmldsigSigningError,
    construir_assinador,
    hash_xml_canonico,
)

__all__ = [
    "ALGORITMO_VERSAO",
    "NotImplementedXmldsigSigner",
    "PiiCifrada",
    "XmldsigSigner",
    "XmldsigSigningError",
    "carregar_chave",
    "cifrar",
    "construir_assinador",
    "decifrar",
    "hash_xml_canonico",
]
