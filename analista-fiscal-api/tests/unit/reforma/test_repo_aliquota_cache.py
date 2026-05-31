"""Testes do ``AliquotaCbsIbsRepo`` com cache injetado (Sprint 19 PR2).

Verifica que:
  * Sem cache → comportamento original (1 query por chamada).
  * Com cache → 1ª chamada vai ao DB; 2ª chamada com mesmos filtros é hit
    (zero queries adicionais).
  * Chaves SCD diferentes não compartilham cache.
  * Exceções (``AliquotaCbsIbsAusente`` / ``PeriodoReformaNaoMapeado``) NÃO
    entram no cache — re-execução re-bate no DB (caso o seed seja corrigido).
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as redis_async

from app.modules.reforma.repo import AliquotaCbsIbsRepo
from app.shared.cache import Cache
from app.shared.exceptions import (
    AliquotaCbsIbsAusente,
    PeriodoReformaNaoMapeado,
)
from tests.unit.reforma.test_repo_aliquota import _row


# ─────────────────────────────────────────────────────────────────────────────
# FakeRedis — reusa o pattern do test_cache, mas isolado por teste.
# ─────────────────────────────────────────────────────────────────────────────


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
        **_: Any,
    ) -> bool | None:
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        n = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                n += 1
        return n

    async def scan(
        self, cursor: int = 0, match: str | None = None, count: int = 200
    ) -> tuple[int, list[str]]:
        import fnmatch
        chaves = (
            list(self._store)
            if match is None
            else [k for k in self._store if fnmatch.fnmatch(k, match)]
        )
        return (0, chaves)


def _mock_session_com_contador(rows: list[Any]) -> tuple[AsyncMock, dict[str, int]]:
    """Mock session que conta chamadas a ``execute`` — prova hit do cache.

    Retorna ``(session, contadores)``. Cada call de ``session.execute(...)``
    incrementa ``contadores['execute']``.
    """
    contadores = {"execute": 0}
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=rows)
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)

    async def _execute(*_args: Any, **_kwargs: Any) -> Any:
        contadores["execute"] += 1
        return result

    session = AsyncMock()
    session.execute = _execute
    return session, contadores


def _cache() -> Cache:
    return Cache(cast(redis_async.Redis, _FakeRedis()), jitter_pct=0.0, namespace="test")


# ─────────────────────────────────────────────────────────────────────────────
# Hit / miss
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sem_cache_cada_chamada_vai_ao_db() -> None:
    rows = [_row()]
    session, contadores = _mock_session_com_contador(rows)
    repo = AliquotaCbsIbsRepo(session=session)  # sem cache

    await repo.vigente(date(2026, 6, 1))
    await repo.vigente(date(2026, 6, 1))
    await repo.vigente(date(2026, 6, 1))

    assert contadores["execute"] == 3


@pytest.mark.asyncio
async def test_com_cache_segunda_chamada_e_hit() -> None:
    rows = [_row()]
    session, contadores = _mock_session_com_contador(rows)
    repo = AliquotaCbsIbsRepo(session=session, cache=_cache())

    primeira = await repo.vigente(date(2026, 6, 1))
    segunda = await repo.vigente(date(2026, 6, 1))
    terceira = await repo.vigente(date(2026, 6, 1))

    # Loader rodou 1×; hits subsequentes não tocam o DB.
    assert contadores["execute"] == 1
    # Resultado é idêntico em todas as chamadas.
    assert primeira == segunda == terceira


@pytest.mark.asyncio
async def test_filtros_diferentes_nao_compartilham_cache() -> None:
    rows = [_row(), _row(regime="lucro_presumido")]
    session, contadores = _mock_session_com_contador(rows)
    cache = _cache()
    repo = AliquotaCbsIbsRepo(session=session, cache=cache)

    await repo.vigente(date(2026, 6, 1))
    await repo.vigente(date(2026, 6, 1), regime="lucro_presumido")
    await repo.vigente(date(2026, 6, 1), regime="lucro_presumido")

    # 1ª e 2ª chamadas → 2 misses (chaves diferentes).
    # 3ª → hit da 2ª.
    assert contadores["execute"] == 2


@pytest.mark.asyncio
async def test_competencias_diferentes_nao_compartilham_cache() -> None:
    rows = [_row()]
    session, contadores = _mock_session_com_contador(rows)
    repo = AliquotaCbsIbsRepo(session=session, cache=_cache())

    await repo.vigente(date(2026, 6, 1))
    await repo.vigente(date(2026, 7, 1))
    await repo.vigente(date(2026, 6, 1))  # hit do 1º
    await repo.vigente(date(2026, 7, 1))  # hit do 2º

    assert contadores["execute"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# Exceções não viram cache (LGPD + correção de seed)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_aliquota_ausente_nao_e_cacheada() -> None:
    """Cache de erro é armadilha — se o seed for corrigido com nova
    vigência, o erro grudaria por 24h. ``_loader`` deve propagar a exceção.
    """
    session, contadores = _mock_session_com_contador([])  # nenhuma linha
    repo = AliquotaCbsIbsRepo(session=session, cache=_cache())

    with pytest.raises(AliquotaCbsIbsAusente):
        await repo.vigente(date(2026, 6, 1))
    with pytest.raises(AliquotaCbsIbsAusente):
        await repo.vigente(date(2026, 6, 1))

    # Re-execução bate no DB de novo — não armazenou o "erro" no cache.
    assert contadores["execute"] == 2


@pytest.mark.asyncio
async def test_periodo_antes_de_2026_nao_e_cacheado() -> None:
    """Pré-reforma levanta ``PeriodoReformaNaoMapeado`` dentro de ``_resolver_db``
    pela função ``fase()`` — antes de ``session.execute()``.

    O importante para o cache: re-execução não devolve valor cacheado
    (exceção propagada nunca é serializada). Cada chamada repete o erro.
    """
    rows = [_row()]
    session, contadores = _mock_session_com_contador(rows)
    repo = AliquotaCbsIbsRepo(session=session, cache=_cache())

    with pytest.raises(PeriodoReformaNaoMapeado):
        await repo.vigente(date(2025, 12, 31))
    with pytest.raises(PeriodoReformaNaoMapeado):
        await repo.vigente(date(2025, 12, 31))

    # ``fase()`` levanta antes de qualquer ``session.execute`` — contador
    # zerado é correto. O ponto provado: exceção continua subindo (sem
    # ser silenciada pelo cache "lembrando o erro").
    assert contadores["execute"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Round-trip da serialização (Decimal + date + Enum)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_serializacao_preserva_decimal_e_date() -> None:
    from decimal import Decimal

    rows = [
        _row(
            aliquota_cbs="0.0090",
            aliquota_ibs="0.0010",
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
            observacao="estimativa LC 214",
        )
    ]
    session, _ = _mock_session_com_contador(rows)
    repo = AliquotaCbsIbsRepo(session=session, cache=_cache())

    primeira = await repo.vigente(date(2026, 6, 1))
    segunda = await repo.vigente(date(2026, 6, 1))

    # Hit re-decodifica do JSON — tipos têm que voltar idênticos.
    assert primeira == segunda
    assert isinstance(segunda.aliquota_cbs, Decimal)
    assert isinstance(segunda.valid_from, date)
    assert segunda.aliquota_cbs == Decimal("0.0090")
    assert segunda.valid_from == date(2026, 1, 1)
    assert segunda.valid_to == date(2026, 12, 31)
    assert segunda.observacao == "estimativa LC 214"


@pytest.mark.asyncio
async def test_serializacao_aceita_valid_to_e_observacao_none() -> None:
    rows = [_row(valid_to=None, observacao=None)]
    session, _ = _mock_session_com_contador(rows)
    repo = AliquotaCbsIbsRepo(session=session, cache=_cache())

    primeira = await repo.vigente(date(2026, 6, 1))
    segunda = await repo.vigente(date(2026, 6, 1))

    assert primeira.valid_to is None
    assert segunda.valid_to is None
    assert primeira.observacao is None
