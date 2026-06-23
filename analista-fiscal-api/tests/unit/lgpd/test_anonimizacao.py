"""Golden -- anonimizacao de PII (Marco 3, direito ao esquecimento).

Funcoes puras: determinismo, unicidade por id e formato dos tokens.
"""
from __future__ import annotations

from uuid import UUID

from app.modules.lgpd.anonimizacao import (
    NOME_ANONIMO,
    cpf_anonimo,
    email_anonimo,
    token_anonimo,
)

_ID_A = UUID(int=1)
_ID_B = UUID(int=2)


def test_token_deterministico_e_do_tamanho() -> None:
    assert token_anonimo(_ID_A, tamanho=16) == token_anonimo(_ID_A, tamanho=16)
    assert len(token_anonimo(_ID_A, tamanho=16)) == 16


def test_token_unico_por_id() -> None:
    assert token_anonimo(_ID_A, tamanho=16) != token_anonimo(_ID_B, tamanho=16)


def test_email_anonimo_nao_roteavel_e_unico() -> None:
    email = email_anonimo(_ID_A)
    assert email.startswith("anon-")
    assert email.endswith("@anonimizado.invalid")
    assert email_anonimo(_ID_A) != email_anonimo(_ID_B)


def test_cpf_anonimo_11_digitos_unico() -> None:
    cpf = cpf_anonimo(_ID_A)
    assert len(cpf) == 11
    assert cpf.isdigit()
    assert cpf_anonimo(_ID_A) != cpf_anonimo(_ID_B)


def test_nome_anonimo_e_placeholder_fixo() -> None:
    assert NOME_ANONIMO == "[ANONIMIZADO]"
