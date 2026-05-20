"""Unit tests para hash/verificação de senha bcrypt."""

from __future__ import annotations

import pytest

from app.shared.auth.password import hash_senha, verificar_senha


def test_hash_diferente_da_senha_original() -> None:
    h = hash_senha("minha_senha_123")
    assert h != "minha_senha_123"


def test_hash_comeca_com_bcrypt_prefix() -> None:
    h = hash_senha("qualquer")
    assert h.startswith("$2b$")


def test_verificar_senha_correta() -> None:
    senha = "S3nh@Forte!"
    assert verificar_senha(senha, hash_senha(senha)) is True


def test_verificar_senha_errada() -> None:
    h = hash_senha("senha_correta")
    assert verificar_senha("senha_errada", h) is False


def test_hashes_distintos_para_mesma_senha() -> None:
    """bcrypt.gensalt() gera salt diferente a cada chamada."""
    h1 = hash_senha("igual")
    h2 = hash_senha("igual")
    assert h1 != h2
    assert verificar_senha("igual", h1) is True
    assert verificar_senha("igual", h2) is True


def test_hash_custo_12() -> None:
    """Verifica que o custo bcrypt é 12 conforme §5.1 do Plano."""
    h = hash_senha("qualquer")
    # Formato $2b$<custo>$<resto>
    custo = int(h.split("$")[2])
    assert custo == 12


@pytest.mark.parametrize("senha", ["a", "b" * 128, "senha com espaços", "!@#$%^&*()"])
def test_verificar_senhas_variadas(senha: str) -> None:
    assert verificar_senha(senha, hash_senha(senha)) is True
