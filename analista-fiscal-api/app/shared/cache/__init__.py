"""Cache Redis genérico para SCD lookups + outros read-mostly (Sprint 19 PR2).

Sub-módulos:
  * ``cache``  — classe ``Cache`` low-level (string-based, get/set/invalidate).
  * ``keys``   — helpers determinísticos para nomear chaves consistentemente.

Pattern de uso (cache-aside):

    from app.shared.cache import Cache

    async def vigente(self, competencia: date) -> AliquotaCBSIBS:
        if self._cache is None:
            return await self._vigente_db(competencia)
        key = aliquota_cbs_ibs_key(competencia, regime, cnae, classificacao)
        async def _loader() -> str:
            return _encode(await self._vigente_db(competencia, ...))
        raw = await self._cache.get_or_compute(key, _loader, ttl=86400)
        return _decode(raw)

O cache é **opcional por DI** — repos aceitam ``Cache | None`` para o construtor
funcionar igual em testes unitários sem Redis e em prod com Redis.
"""

from app.shared.cache.cache import Cache, CacheUnavailable
from app.shared.cache.keys import aliquota_cbs_ibs_key, scd_cache_pattern

__all__ = ["Cache", "CacheUnavailable", "aliquota_cbs_ibs_key", "scd_cache_pattern"]
