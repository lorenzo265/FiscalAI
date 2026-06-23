"""Golden -- envelope AES-256-GCM + PiiCifrada TypeDecorator (Marco 3).

Round-trip, ciphertext != plaintext, nonce aleatorio, deteccao de adulteracao
(GCM autenticado) e validacao de chave/versao. Funcoes puras, sem DB.
"""
from __future__ import annotations

import base64

import pytest
from cryptography.exceptions import InvalidTag

from app.shared.crypto.envelope import carregar_chave, cifrar, decifrar
from app.shared.crypto.pii_type import PiiCifrada

_CHAVE = carregar_chave(base64.b64encode(b"x" * 32).decode())


def test_roundtrip_preserva_o_plaintext() -> None:
    token = cifrar("11987654321", _CHAVE)
    assert decifrar(token, _CHAVE) == "11987654321"


def test_ciphertext_nao_contem_o_plaintext_e_e_versionado() -> None:
    token = cifrar("segredo-fiscal", _CHAVE)
    assert "segredo-fiscal" not in token
    assert token.startswith("v1:")


def test_nonce_aleatorio_muda_o_ciphertext() -> None:
    # Mesmo plaintext -> ciphertexts diferentes (nonce por escrita)...
    assert cifrar("igual", _CHAVE) != cifrar("igual", _CHAVE)
    # ...mas ambos decifram pro mesmo valor.
    assert decifrar(cifrar("igual", _CHAVE), _CHAVE) == "igual"


def test_adulteracao_falha_autenticacao_gcm() -> None:
    token = cifrar("integro", _CHAVE)
    blob = bytearray(base64.b64decode(token.split(":", 1)[1]))
    blob[-1] ^= 0x01  # flip de 1 bit no tag GCM
    adulterado = "v1:" + base64.b64encode(bytes(blob)).decode()
    with pytest.raises(InvalidTag):
        decifrar(adulterado, _CHAVE)


def test_chave_de_tamanho_errado_e_rejeitada() -> None:
    with pytest.raises(ValueError):
        carregar_chave(base64.b64encode(b"curta").decode())


def test_versao_desconhecida_e_rejeitada() -> None:
    corpo = cifrar("x", _CHAVE).split(":", 1)[1]
    with pytest.raises(ValueError):
        decifrar(f"v2:{corpo}", _CHAVE)


def test_typedecorator_cifra_e_decifra_e_trata_none() -> None:
    td = PiiCifrada()
    token = td.process_bind_param("11999999999", None)
    assert token is not None
    assert token != "11999999999"
    assert td.process_result_value(token, None) == "11999999999"
    assert td.process_bind_param(None, None) is None
    assert td.process_result_value(None, None) is None
