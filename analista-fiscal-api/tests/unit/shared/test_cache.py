"""Testes do ``app.shared.cache.Cache`` (Sprint 19 PR2).

Usa ``FakeRedis`` (mock in-memory minimalista) — apenas os métodos que o
``Cache`` consome. Não traz dependência externa (fakeredis).
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
import redis.asyncio as redis_async

from app.shared.cache import Cache
from app.shared.cache.keys import aliquota_cbs_ibs_key, scd_cache_pattern

# ─────────────────────────────────────────────────────────────────────────────
# FakeRedis — mock manual dos métodos consumidos pelo Cache
# ─────────────────────────────────────────────────────────────────────────────


class FakeRedis:
    """Mock manual de ``redis.asyncio.Redis``. NÃO honra TTL (testes não
    aguardam tempo real); apenas registra TTL para inspeção."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttl: dict[str, int] = {}
        self.raise_on: set[str] = set()  # nomes de métodos que devem levantar
        self.scan_chunks: int | None = None  # se set, simula SCAN paginado
        # Snapshot determinística de uma iteração SCAN. Reset quando o
        # cursor volta a 0 (próxima iteração lógica).
        self._scan_snapshot: list[str] | None = None

    def _maybe_raise(self, method: str) -> None:
        if method in self.raise_on:
            raise redis_async.RedisError(f"FakeRedis simulando erro em {method}")

    async def get(self, key: str) -> str | None:
        self._maybe_raise("get")
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
        self._maybe_raise("set")
        if nx and key in self._store:
            return None
        self._store[key] = value
        if ex is not None:
            self._ttl[key] = ex
        return True

    async def delete(self, *keys: str) -> int:
        self._maybe_raise("delete")
        removidas = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                self._ttl.pop(k, None)
                removidas += 1
        return removidas

    async def scan(
        self, cursor: int = 0, match: str | None = None, count: int = 200
    ) -> tuple[int, list[str]]:
        self._maybe_raise("scan")
        if self.scan_chunks is None:
            # Sem paginação simulada — retorna tudo de uma vez.
            if match is None:
                return (0, list(self._store))
            import fnmatch
            return (0, [k for k in self._store if fnmatch.fnmatch(k, match)])

        # Paginação: tira uma snapshot na 1ª iteração (cursor=0) e itera
        # nela. Isto emula a garantia real do Redis SCAN — chaves que
        # existiam quando o cursor começou serão retornadas, mesmo se
        # forem deletadas entre iterações.
        if cursor == 0 or self._scan_snapshot is None:
            if match is None:
                self._scan_snapshot = list(self._store)
            else:
                import fnmatch
                self._scan_snapshot = [
                    k for k in self._store if fnmatch.fnmatch(k, match)
                ]
        snapshot = self._scan_snapshot
        if cursor >= len(snapshot):
            self._scan_snapshot = None
            return (0, [])
        proximo = cursor + self.scan_chunks
        chunk = snapshot[cursor:proximo]
        if proximo >= len(snapshot):
            self._scan_snapshot = None
            return (0, chunk)
        return (proximo, chunk)


def _make_cache(jitter_pct: float = 0.0) -> tuple[Cache, FakeRedis]:
    fake = FakeRedis()
    cache = Cache(cast(redis_async.Redis, fake), jitter_pct=jitter_pct, namespace="t")
    return cache, fake


# ─────────────────────────────────────────────────────────────────────────────
# Operações básicas: get / set / delete
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_e_get_round_trip() -> None:
    cache, fake = _make_cache()
    await cache.set("foo", "bar", ttl=60)
    assert await cache.get("foo") == "bar"
    # Chave foi prefixada com namespace.
    assert "t:foo" in fake._store


@pytest.mark.asyncio
async def test_get_miss_devolve_none() -> None:
    cache, _ = _make_cache()
    assert await cache.get("naoexiste") is None


@pytest.mark.asyncio
async def test_get_em_erro_redis_e_fail_open() -> None:
    cache, fake = _make_cache()
    fake.raise_on.add("get")
    # Não levanta — devolve None (fail-open).
    assert await cache.get("foo") is None


@pytest.mark.asyncio
async def test_set_em_erro_redis_e_fail_open() -> None:
    cache, fake = _make_cache()
    fake.raise_on.add("set")
    # Não levanta — log + segue.
    await cache.set("foo", "bar", ttl=60)


@pytest.mark.asyncio
async def test_delete_remove_e_devolve_true() -> None:
    cache, _ = _make_cache()
    await cache.set("foo", "bar", ttl=60)
    assert await cache.delete("foo") is True
    assert await cache.get("foo") is None


@pytest.mark.asyncio
async def test_delete_em_chave_inexistente_devolve_false() -> None:
    cache, _ = _make_cache()
    assert await cache.delete("nope") is False


# ─────────────────────────────────────────────────────────────────────────────
# TTL + Jitter
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_sem_jitter_preserva_ttl_exato() -> None:
    cache, fake = _make_cache(jitter_pct=0.0)
    await cache.set("foo", "bar", ttl=120)
    assert fake._ttl["t:foo"] == 120


@pytest.mark.asyncio
async def test_set_com_jitter_aplica_variacao_dentro_da_faixa() -> None:
    cache, fake = _make_cache(jitter_pct=0.1)
    # 10 chamadas para amostrar a distribuição.
    ttls: set[int] = set()
    for i in range(10):
        await cache.set(f"k{i}", "v", ttl=1000)
        ttls.add(fake._ttl[f"t:k{i}"])
    assert min(ttls) >= 900
    assert max(ttls) <= 1100
    # Probabilisticamente quase certo: ao menos 2 valores diferentes em 10 tentativas.
    assert len(ttls) >= 2


@pytest.mark.asyncio
async def test_jitter_garante_ttl_minimo_de_1() -> None:
    cache, fake = _make_cache(jitter_pct=0.5)
    await cache.set("foo", "bar", ttl=1)
    # Mesmo no pior caso, TTL é ≥ 1 (Redis 0 = sem expiração — armadilha).
    assert fake._ttl["t:foo"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# get_or_compute — cache-aside
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_or_compute_hit_nao_chama_loader() -> None:
    cache, _ = _make_cache()
    await cache.set("foo", "cached", ttl=60)
    chamadas = {"n": 0}

    async def loader() -> str:
        chamadas["n"] += 1
        return "computed"

    valor = await cache.get_or_compute("foo", loader, ttl=60)
    assert valor == "cached"
    assert chamadas["n"] == 0


@pytest.mark.asyncio
async def test_get_or_compute_miss_chama_loader_e_persiste() -> None:
    cache, fake = _make_cache()

    async def loader() -> str:
        return "computed"

    valor = await cache.get_or_compute("foo", loader, ttl=60)
    assert valor == "computed"
    assert fake._store["t:foo"] == "computed"


@pytest.mark.asyncio
async def test_get_or_compute_concorrente_so_um_loader_roda() -> None:
    """SETNX lock — 5 chamadas paralelas com mesma key → loader roda 1 vez."""
    cache, _ = _make_cache()
    chamadas = {"n": 0}

    async def loader() -> str:
        chamadas["n"] += 1
        await asyncio.sleep(0.05)  # simula query lenta
        return "computed"

    resultados = await asyncio.gather(
        *(cache.get_or_compute("foo", loader, ttl=60) for _ in range(5))
    )

    assert all(r == "computed" for r in resultados)
    # Vencedor do SETNX é o único a rodar; perdedores leem do cache.
    assert chamadas["n"] == 1


@pytest.mark.asyncio
async def test_get_or_compute_em_erro_redis_cai_para_loader_direto() -> None:
    cache, fake = _make_cache()
    fake.raise_on.add("get")

    async def loader() -> str:
        return "computed"

    valor = await cache.get_or_compute("foo", loader, ttl=60)
    assert valor == "computed"


# ─────────────────────────────────────────────────────────────────────────────
# invalidate_pattern — SCAN + DEL
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalidate_pattern_remove_chaves_que_casam() -> None:
    cache, fake = _make_cache()
    await cache.set("scd:cbs_ibs:2026-01-01:-:-:-", "v1", ttl=60)
    await cache.set("scd:cbs_ibs:2027-01-01:lucro_presumido:-:-", "v2", ttl=60)
    await cache.set("scd:faixa_simples:2026-01-01", "v3", ttl=60)
    await cache.set("outro:dominio", "v4", ttl=60)

    removidas = await cache.invalidate_pattern("scd:cbs_ibs:*")
    assert removidas == 2
    assert "t:scd:cbs_ibs:2026-01-01:-:-:-" not in fake._store
    assert "t:scd:cbs_ibs:2027-01-01:lucro_presumido:-:-" not in fake._store
    # Não toca em outros prefixos.
    assert "t:scd:faixa_simples:2026-01-01" in fake._store
    assert "t:outro:dominio" in fake._store


@pytest.mark.asyncio
async def test_invalidate_pattern_lida_com_scan_paginado() -> None:
    cache, fake = _make_cache()
    for i in range(25):
        await cache.set(f"x:{i}", "v", ttl=60)
    fake.scan_chunks = 5  # simula paginação SCAN

    removidas = await cache.invalidate_pattern("x:*")
    assert removidas == 25


@pytest.mark.asyncio
async def test_invalidate_pattern_em_erro_redis_e_fail_open() -> None:
    cache, fake = _make_cache()
    await cache.set("foo", "bar", ttl=60)
    fake.raise_on.add("scan")
    removidas = await cache.invalidate_pattern("foo*")
    assert removidas == 0


@pytest.mark.asyncio
async def test_invalidate_pattern_sem_match_devolve_zero() -> None:
    cache, _ = _make_cache()
    removidas = await cache.invalidate_pattern("nada:*")
    assert removidas == 0


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de chave (keys.py)
# ─────────────────────────────────────────────────────────────────────────────


def test_aliquota_cbs_ibs_key_inclui_todos_os_filtros() -> None:
    from datetime import date as date_

    k = aliquota_cbs_ibs_key(
        date_(2026, 6, 15),
        regime="lucro_presumido",
        cnae="4781400",
        classificacao="geral",
    )
    assert k == "scd:cbs_ibs:2026-06-15:lucro_presumido:4781400:geral"


def test_aliquota_cbs_ibs_key_substitui_none_por_dash() -> None:
    from datetime import date as date_

    k = aliquota_cbs_ibs_key(
        date_(2026, 1, 1), regime=None, cnae=None, classificacao=None,
    )
    assert k == "scd:cbs_ibs:2026-01-01:-:-:-"


def test_aliquota_cbs_ibs_key_chaves_diferentes_para_filtros_diferentes() -> None:
    from datetime import date as date_

    base = aliquota_cbs_ibs_key(
        date_(2026, 1, 1), regime=None, cnae=None, classificacao=None,
    )
    com_regime = aliquota_cbs_ibs_key(
        date_(2026, 1, 1), regime="lucro_presumido", cnae=None, classificacao=None,
    )
    assert base != com_regime


def test_scd_cache_pattern_sem_tabela_pega_tudo() -> None:
    assert scd_cache_pattern() == "scd:*"


def test_scd_cache_pattern_com_tabela_filtra() -> None:
    assert scd_cache_pattern("cbs_ibs") == "scd:cbs_ibs:*"
