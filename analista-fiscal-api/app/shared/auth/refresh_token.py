"""Refresh token opaco -- geracao e hash (Marco 3, rotacao + revogacao).

O refresh token e um valor ALEATORIO opaco (NAO um JWT): alta entropia, sem
claims. No banco guardamos apenas o SHA-256 hex dele -- nunca o valor cru. Como
o token ja tem 384 bits de entropia, um hash rapido (SHA-256) basta: forca bruta
e inviavel, e nao ha o problema de senha de baixa entropia que exigiria bcrypt.
"""
from __future__ import annotations

import hashlib
import secrets

_TOKEN_BYTES = 48  # 384 bits de entropia


def gerar_refresh_token() -> str:
    """Gera um refresh token opaco, URL-safe e criptograficamente aleatorio."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_refresh_token(raw: str) -> str:
    """SHA-256 hex do token cru -- o que vai pro banco (nunca o valor cru)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
