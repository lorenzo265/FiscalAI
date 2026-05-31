"""Invariantes de hash de senha bcrypt (Sprint 21 PR1).

Golden tests para hash_senha / verificar_senha.
Cobre: salt aleatório, verificação correta/errada, custo rounds=12, Unicode.
"""
from __future__ import annotations

import pytest

from app.shared.auth.password import hash_senha, verificar_senha


def test_hash_difere_a_cada_chamada():
    """bcrypt gera salt diferente a cada call — hashes distintos para mesma senha."""
    h1 = hash_senha("minha_senha_123")
    h2 = hash_senha("minha_senha_123")
    assert h1 != h2


def test_senha_correta_verifica():
    senha = "SenhaSuperSecreta!42"
    hash_ = hash_senha(senha)
    assert verificar_senha(senha, hash_) is True


def test_senha_errada_nao_verifica():
    hash_ = hash_senha("senha_correta")
    assert verificar_senha("senha_errada", hash_) is False


def test_hash_tem_prefixo_bcrypt_rounds_12():
    """Garante que o custo do bcrypt é rounds=12 conforme §5.1 do Plano."""
    hash_ = hash_senha("teste")
    assert hash_.startswith("$2b$12$"), f"Hash inesperado: {hash_[:10]}..."


def test_senha_unicode_verifica():
    """Senhas com caracteres UTF-8 funcionam corretamente."""
    senha = "Confirmação_2026_ção"
    hash_ = hash_senha(senha)
    assert verificar_senha(senha, hash_) is True
    assert verificar_senha("Confirmacao_2026_cao", hash_) is False


def test_senha_vazia_hash_e_verifica():
    """String vazia é aceita como senha — decisão de negócio, não bug."""
    hash_ = hash_senha("")
    assert verificar_senha("", hash_) is True
    assert verificar_senha(" ", hash_) is False
