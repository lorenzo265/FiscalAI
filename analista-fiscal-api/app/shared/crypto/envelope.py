"""Envelope AES-256-GCM para cifrar PII em repouso (Marco 3, LGPD principio 8.7).

A chave de 32 bytes vem de ``settings.PII_ENCRYPTION_KEY`` (base64). Em dev usa
um placeholder; em prod a chave vem do KMS (o ``config`` faz fail-fast se ela
ainda for o placeholder em ENVIRONMENT=prod).

Token de saida: ``"<versao>:" + base64( nonce[12] || ciphertext || tag[16] )``.
O prefixo de versao permite rotacao futura de algoritmo/chave sem ambiguidade.
GCM e autenticado: adulterar o ciphertext faz ``decifrar`` levantar.
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_VERSAO = "v1"
_NONCE_BYTES = 12
_CHAVE_BYTES = 32  # AES-256


def carregar_chave(chave_b64: str) -> bytes:
    """Decodifica e valida a chave de 32 bytes (AES-256) a partir do base64."""
    chave = base64.b64decode(chave_b64)
    if len(chave) != _CHAVE_BYTES:
        raise ValueError(
            f"PII_ENCRYPTION_KEY deve ter {_CHAVE_BYTES} bytes (AES-256) em base64; "
            f"tem {len(chave)}"
        )
    return chave


def cifrar(plaintext: str, chave: bytes) -> str:
    """Cifra ``plaintext`` com AES-256-GCM e nonce aleatorio. Retorna o token."""
    nonce = os.urandom(_NONCE_BYTES)
    ct: bytes = AESGCM(chave).encrypt(nonce, plaintext.encode("utf-8"), None)
    return f"{_VERSAO}:{base64.b64encode(nonce + ct).decode('ascii')}"


def decifrar(token: str, chave: bytes) -> str:
    """Decifra um token gerado por :func:`cifrar`. Levanta se adulterado."""
    versao, _, corpo = token.partition(":")
    if versao != _VERSAO:
        raise ValueError(f"Versao de envelope desconhecida: {versao!r}")
    blob = base64.b64decode(corpo)
    nonce, ct = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    plaintext: bytes = AESGCM(chave).decrypt(nonce, ct, None)
    return plaintext.decode("utf-8")
