"""Primitivas criptográficas compartilhadas (Sprint 19.7 PR2 #13).

Hoje expõe apenas o assinador XMLDSig pra eventos eSocial. Em sprints
futuras virão helpers de envelope AES-256-GCM (ampliar uso pgcrypto pra
campos sensíveis adicionais — pendência da Sprint 21 hardening) e
wrappers de KMS pra rotacionar `SERPRO_CERT_ENCRYPTION_KEY`.
"""

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
    "XmldsigSigner",
    "XmldsigSigningError",
    "construir_assinador",
    "hash_xml_canonico",
]
