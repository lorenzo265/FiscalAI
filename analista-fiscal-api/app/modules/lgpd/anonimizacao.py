"""Anonimizacao de PII -- direito ao esquecimento (LGPD art. 18, VI).

Substitui a PII por tokens nao-identificantes e IRREVERSIVEIS. O token deriva
do ``id`` da linha (UUID), NAO da PII original -- entao o valor original e
sobrescrito e nao ha como recupera-lo a partir do token. A derivacao por id
tambem garante a UNICIDADE exigida pelas constraints (CPF unico por empresa,
email unico por tenant): linhas distintas -> ids distintos -> tokens distintos.

Funcoes puras e deterministicas (golden-testaveis); nenhuma toca o banco.
"""
from __future__ import annotations

import hashlib
from uuid import UUID

# Placeholder para campos de nome (sem constraint de unicidade -> valor fixo).
NOME_ANONIMO = "[ANONIMIZADO]"


def _digest(semente: str) -> str:
    return hashlib.sha256(semente.encode("utf-8")).hexdigest()


def token_anonimo(row_id: UUID, *, tamanho: int) -> str:
    """Token hex deterministico e unico por linha (deriva do id, nao da PII)."""
    return _digest(str(row_id))[:tamanho]


def email_anonimo(usuario_id: UUID) -> str:
    """Email nao-roteavel e unico por usuario.

    Usa o dominio reservado ``.invalid`` (RFC 6761): nunca resolve, nunca
    entrega -- garante que nenhuma mensagem chegue a uma pessoa real.
    """
    return f"anon-{token_anonimo(usuario_id, tamanho=16)}@anonimizado.invalid"


def cpf_anonimo(row_id: UUID) -> str:
    """11 digitos (cabe em ``String(11)``), unico por linha, NAO e um CPF real."""
    numero = int(_digest(str(row_id)), 16) % (10**11)
    return str(numero).zfill(11)
