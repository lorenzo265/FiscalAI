"""Golden -- helpers de refresh token opaco (Marco 3)."""
from __future__ import annotations

from app.shared.auth.refresh_token import gerar_refresh_token, hash_refresh_token


def test_gerar_token_aleatorio_e_unico() -> None:
    a = gerar_refresh_token()
    b = gerar_refresh_token()
    assert a != b
    assert len(a) >= 40  # 48 bytes url-safe ~ 64 chars de entropia alta


def test_hash_deterministico_sha256_hex() -> None:
    raw = "token-cru-de-exemplo"
    digest = hash_refresh_token(raw)
    assert digest == hash_refresh_token(raw)  # deterministico
    assert len(digest) == 64  # SHA-256 em hex
    assert all(c in "0123456789abcdef" for c in digest)
    assert digest != raw  # nunca igual ao valor cru


def test_hash_de_tokens_diferentes_difere() -> None:
    assert hash_refresh_token(gerar_refresh_token()) != hash_refresh_token(
        gerar_refresh_token()
    )
