"""Wrapper Redis com TTL+jitter + mitigação de thundering herd (Sprint 19 PR2).

Antes deste módulo:
  * SCD lookups (faixa Simples, presunção LP, alíquota CBS/IBS) batiam no
    DB em toda chamada — ~5ms por lookup, mas com 1k empresas concorrentes
    apurando às 9h do dia 1 do trimestre vira hotspot.
  * Cada call site reinventava cache: alguns tinham, outros não, TTL e
    invalidação inconsistentes.

Este módulo padroniza:

1. ``Cache.get_or_compute(key, loader, ttl)`` — cache-aside genérico.
   Caller controla serialização (string in/out). Aplica jitter ±10% no
   TTL para distribuir expiração no tempo (evita stampede sincronizado).

2. ``Cache.invalidate_pattern(pattern)`` — SCAN + DEL em batch.
   ``SCAN`` em vez de ``KEYS`` para não bloquear Redis em prod com
   milhões de chaves.

3. Mitigação de thundering herd via **SETNX lock**: na primeira miss em
   uma chave, o vencedor da disputa adquire um lock curto e computa; os
   perdedores esperam por backoff curto e tentam ler de novo.

Princípios cravados:
  * §8.10 Observabilidade — log estruturado de hit/miss/lock.
  * §8.9 Idempotência — `get_or_compute` é idempotente; concorrência via
    SETNX evita compute duplicado.
  * §8.7 LGPD — chave do cache não deve conter PII (caller responsável;
    helpers em ``keys.py`` mantêm o padrão).
"""

from __future__ import annotations

import asyncio
import contextlib
import random
from collections.abc import Awaitable, Callable

import redis.asyncio as redis_async
import structlog

log = structlog.get_logger(__name__)


class CacheUnavailable(Exception):
    """Redis indisponível — caller deve cair para o caminho sem cache."""


# Lock SETNX é curto: só dura o tempo de computar o loader. Se o loader
# travar (DB lento), outros chamadores esperam até o lock expirar.
_LOCK_TTL_SEC = 15

# Backoff entre tentativas de ler valor recém-computado pelo lock holder.
# Total = _RETRY_MAX_TRIES * _RETRY_BASE_SLEEP_SEC * 1.5 (média geométrica).
_RETRY_MAX_TRIES = 8
_RETRY_BASE_SLEEP_SEC = 0.05  # 50ms inicial — dobra a cada tentativa.


class Cache:
    """Wrapper Redis low-level.

    Caller controla serialização (string in/out). Para tipos complexos
    (Decimal, date, dataclasses), use Pydantic JSON ou helpers ad-hoc.
    """

    def __init__(
        self,
        redis: redis_async.Redis[str],
        *,
        jitter_pct: float = 0.1,
        namespace: str = "fiscalai",
    ) -> None:
        self._r = redis
        self._jitter_pct = jitter_pct
        self._ns = namespace

    def _full_key(self, key: str) -> str:
        """Prefixa namespace global. Permite múltiplas apps no mesmo Redis."""
        return f"{self._ns}:{key}"

    def _ttl_with_jitter(self, ttl: int) -> int:
        """Aplica ±jitter_pct ao TTL para distribuir expiração no tempo.

        Garante mínimo 1 segundo — TTL=0 em Redis é "sem expiração", que
        seria bug em cache temporal.
        """
        if self._jitter_pct <= 0:
            return max(1, ttl)
        delta = int(ttl * self._jitter_pct)
        # random.SystemRandom seria criptograficamente seguro mas overkill aqui.
        return max(1, ttl + random.randint(-delta, delta))  # nosec B311

    async def get(self, key: str) -> str | None:
        """GET raw. Retorna None em miss OU em erro Redis (fail-open)."""
        try:
            value = await self._r.get(self._full_key(key))
        except redis_async.RedisError:
            log.warning("cache.get.redis_error", key=key)
            return None
        if value is None:
            return None
        # decode_responses=True no client → value já vem str.
        return str(value)

    async def set(self, key: str, value: str, ttl: int) -> None:
        """SET com TTL+jitter. Fail-open: erro em Redis vira warning."""
        try:
            await self._r.set(self._full_key(key), value, ex=self._ttl_with_jitter(ttl))
        except redis_async.RedisError:
            log.warning("cache.set.redis_error", key=key)

    async def delete(self, key: str) -> bool:
        """DEL — retorna True se a chave existia. Fail-open."""
        try:
            removed = await self._r.delete(self._full_key(key))
        except redis_async.RedisError:
            log.warning("cache.delete.redis_error", key=key)
            return False
        return bool(removed)

    async def invalidate_pattern(self, pattern: str) -> int:
        """SCAN + DEL — não bloqueia Redis em prod.

        Pattern aceita curinga Redis (``*``, ``?``, ``[abc]``). Caller passa
        sem o namespace; este método adiciona.

        Retorna nº de chaves removidas. Fail-open: erros viram 0.
        """
        full_pattern = self._full_key(pattern)
        total_removidas = 0
        try:
            cursor = 0
            while True:
                cursor, chaves = await self._r.scan(
                    cursor=cursor, match=full_pattern, count=200
                )
                if chaves:
                    total_removidas += int(await self._r.delete(*chaves))
                if cursor == 0:
                    break
        except redis_async.RedisError:
            log.warning("cache.invalidate.redis_error", pattern=pattern)
            return total_removidas
        log.info("cache.invalidate", pattern=pattern, removidas=total_removidas)
        return total_removidas

    async def get_or_compute(
        self,
        key: str,
        loader: Callable[[], Awaitable[str]],
        *,
        ttl: int,
    ) -> str:
        """Cache-aside com mitigação de thundering herd.

        Algoritmo:
          1. Tenta GET → hit retorna direto.
          2. Miss: tenta adquirir lock ``SETNX <key>:lock`` com TTL curto.
             - Vencedor: roda ``loader()``, faz SET, libera lock, retorna.
             - Perdedor: dorme em backoff exponencial e tenta GET de novo;
               se até o final ainda não houver valor, computa por conta
               própria (defensive — lock pode ter morrido com o vencedor).
          3. Erro Redis em qualquer ponto cai para ``loader()`` direto
             (fail-open — disponibilidade > performance).

        Caller controla serialização do retorno do ``loader()``.
        """
        full_key = self._full_key(key)
        lock_key = f"{full_key}:lock"

        try:
            cached = await self._r.get(full_key)
        except redis_async.RedisError:
            log.warning("cache.get.redis_error", key=key)
            return await loader()

        if cached is not None:
            log.debug("cache.hit", key=key)
            return str(cached)

        # Tenta adquirir o lock — SETNX (`nx=True`).
        try:
            obtive_lock = await self._r.set(lock_key, "1", ex=_LOCK_TTL_SEC, nx=True)
        except redis_async.RedisError:
            log.warning("cache.lock.redis_error", key=key)
            obtive_lock = True  # fail-open: assume que sou o vencedor

        if obtive_lock:
            log.debug("cache.miss.computando", key=key)
            try:
                valor = await loader()
                await self.set(key, valor, ttl=ttl)
                return valor
            finally:
                # Libera lock — não usa Lua check-and-delete (overkill aqui;
                # TTL curto protege contra lock órfão).
                with contextlib.suppress(redis_async.RedisError):
                    await self._r.delete(lock_key)

        # Perdedor — espera o vencedor terminar.
        log.debug("cache.miss.aguardando_lock", key=key)
        for tentativa in range(_RETRY_MAX_TRIES):
            await asyncio.sleep(_RETRY_BASE_SLEEP_SEC * (2**tentativa) * 0.5)
            try:
                cached = await self._r.get(full_key)
            except redis_async.RedisError:
                break
            if cached is not None:
                log.debug("cache.hit_apos_lock", key=key, tentativa=tentativa)
                return str(cached)

        # Lock holder pode ter falhado silenciosamente. Compute defensivo.
        log.warning("cache.lock_timeout_computando_local", key=key)
        valor = await loader()
        await self.set(key, valor, ttl=ttl)
        return valor
