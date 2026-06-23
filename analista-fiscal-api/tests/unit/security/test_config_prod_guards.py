"""Testes dos guards de configuração em ENVIRONMENT=prod (PR2 Segurança/LGPD).

§8.4: golden tests garantindo que JWT_SECRET placeholder e
META_WHATSAPP_VERIFY_TOKEN padrão nunca cheguem a produção.
"""
from __future__ import annotations

import base64

import pytest

from app.config import Settings

# Chave PII valida (base64 de 32 bytes) e DIFERENTE do placeholder DEV.
_PII_PROD_KEY = base64.b64encode(b"P" * 32).decode()


# ── JWT_SECRET guards ─────────────────────────────────────────────────────────


def test_jwt_secret_placeholder_bloqueado_em_prod() -> None:
    """JWT_SECRET com prefixo 'TROCAR_EM_PRODUCAO' deve levantar em prod."""
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://user:pass@db.prod:5432/fiscal",
            REDIS_URL="redis://redis.prod:6379/0",
            JWT_SECRET="TROCAR_EM_PRODUCAO_gere_com_openssl_rand_hex_32",
            META_WHATSAPP_VERIFY_TOKEN="token-customizado-valido",
        )


def test_jwt_secret_curto_bloqueado_em_prod() -> None:
    """JWT_SECRET com menos de 32 chars deve levantar em prod."""
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://user:pass@db.prod:5432/fiscal",
            REDIS_URL="redis://redis.prod:6379/0",
            JWT_SECRET="segredo_curto_demais",  # 20 chars < 32
            META_WHATSAPP_VERIFY_TOKEN="token-customizado-valido",
        )


def test_jwt_secret_valido_aceito_em_prod() -> None:
    """JWT_SECRET longo e sem placeholder deve ser aceito em prod."""
    settings = Settings(
        ENVIRONMENT="prod",
        DATABASE_URL="postgresql+asyncpg://user:pass@db.prod:5432/fiscal",
        REDIS_URL="redis://redis.prod:6379/0",
        JWT_SECRET="a" * 32,  # 32 chars, sem placeholder
        META_WHATSAPP_VERIFY_TOKEN="token-customizado-valido",
        PII_ENCRYPTION_KEY=_PII_PROD_KEY,
    )
    assert len(settings.JWT_SECRET) >= 32


def test_jwt_secret_placeholder_permitido_em_local() -> None:
    """Em ENVIRONMENT=local o placeholder NÃO deve ser bloqueado."""
    settings = Settings(
        ENVIRONMENT="local",
        JWT_SECRET="TROCAR_EM_PRODUCAO_gere_com_openssl_rand_hex_32",
    )
    assert settings.JWT_SECRET.startswith("TROCAR_EM_PRODUCAO")


def test_jwt_secret_curto_permitido_em_staging() -> None:
    """Em ENVIRONMENT=staging o JWT_SECRET curto NÃO é bloqueado."""
    settings = Settings(
        ENVIRONMENT="staging",
        JWT_SECRET="short",
    )
    assert settings.JWT_SECRET == "short"


# ── META_WHATSAPP_VERIFY_TOKEN guard ─────────────────────────────────────────


def test_meta_verify_token_padrao_bloqueado_em_prod() -> None:
    """META_WHATSAPP_VERIFY_TOKEN com valor padrão deve levantar em prod."""
    with pytest.raises(ValueError, match="META_WHATSAPP_VERIFY_TOKEN"):
        Settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://user:pass@db.prod:5432/fiscal",
            REDIS_URL="redis://redis.prod:6379/0",
            JWT_SECRET="a" * 32,
            META_WHATSAPP_VERIFY_TOKEN="fiscalai-webhook-verify",  # default do repo
        )


def test_meta_verify_token_customizado_aceito_em_prod() -> None:
    """META_WHATSAPP_VERIFY_TOKEN customizado deve ser aceito em prod."""
    settings = Settings(
        ENVIRONMENT="prod",
        DATABASE_URL="postgresql+asyncpg://user:pass@db.prod:5432/fiscal",
        REDIS_URL="redis://redis.prod:6379/0",
        JWT_SECRET="a" * 32,
        META_WHATSAPP_VERIFY_TOKEN="meu-token-webhook-secreto-unico",
        PII_ENCRYPTION_KEY=_PII_PROD_KEY,
    )
    assert settings.META_WHATSAPP_VERIFY_TOKEN == "meu-token-webhook-secreto-unico"


# ── PII_ENCRYPTION_KEY guard (Marco 3 — AES-256 em repouso) ───────────────────


def test_pii_key_placeholder_bloqueado_em_prod() -> None:
    """O placeholder DEV de PII_ENCRYPTION_KEY (público no repo) deve levantar em prod."""
    with pytest.raises(ValueError, match="PII_ENCRYPTION_KEY"):
        Settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://user:pass@db.prod:5432/fiscal",
            REDIS_URL="redis://redis.prod:6379/0",
            JWT_SECRET="a" * 32,
            META_WHATSAPP_VERIFY_TOKEN="token-customizado-valido",
            PII_ENCRYPTION_KEY="REVWX1BJSV9LRVlfVFJPQ0FSX0VNX1BST0RVQ0FPISE=",
        )


def test_pii_key_placeholder_permitido_em_local() -> None:
    """Em ENVIRONMENT=local o placeholder DEV de PII NÃO deve ser bloqueado."""
    settings = Settings(ENVIRONMENT="local")
    assert settings.PII_ENCRYPTION_KEY.startswith("REVW")


# ── DATABASE_URL / REDIS_URL guards (pré-existentes — não regrediu) ───────────


def test_database_localhost_bloqueado_em_prod() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/fiscal",
            REDIS_URL="redis://redis.prod:6379/0",
            JWT_SECRET="a" * 32,
            META_WHATSAPP_VERIFY_TOKEN="token-customizado-valido",
        )


def test_redis_localhost_bloqueado_em_prod() -> None:
    with pytest.raises(ValueError, match="REDIS_URL"):
        Settings(
            ENVIRONMENT="prod",
            DATABASE_URL="postgresql+asyncpg://user:pass@db.prod:5432/fiscal",
            REDIS_URL="redis://localhost:6379/0",
            JWT_SECRET="a" * 32,
            META_WHATSAPP_VERIFY_TOKEN="token-customizado-valido",
        )
