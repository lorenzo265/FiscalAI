from __future__ import annotations

import bcrypt


def hash_senha(senha: str) -> str:
    """Gera hash bcrypt com custo 12 (conforme §5.1 do Plano)."""
    hashed: bytes = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verificar_senha(senha: str, hash_: str) -> bool:
    """Verifica senha contra hash bcrypt."""
    return bool(bcrypt.checkpw(senha.encode("utf-8"), hash_.encode("utf-8")))
