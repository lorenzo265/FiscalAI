"""Conftest — fixtures compartilhadas entre unit e integration tests.

Sprint 0: fixtures para smoke test (sem DB).
Sprint 1: adiciona live_client com lifespan, isola settings e JWT.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Generator

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.main import app

# ── Settings globais ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolar_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Isola settings entre testes — limpa LRU cache do get_settings()."""
    from app.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("JWT_SECRET", "test_secret_key_must_have_32chars_ok")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── Cliente HTTP leve (sem lifespan) — smoke tests ────────────────────────────


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Cliente HTTP sem lifespan — usar para /healthz e /openapi.json."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Cliente HTTP com lifespan — integration tests ─────────────────────────────


@pytest_asyncio.fixture
async def live_client() -> AsyncIterator[AsyncClient]:
    """Cliente HTTP com lifespan ativo (DB + Redis reais).

    Requer Postgres/Redis rodando (service containers no CI ou docker-compose localmente).
    As tabelas devem existir: `alembic upgrade head` antes dos testes.
    """
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
