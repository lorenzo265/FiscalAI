"""Performance helpers — engine builder DRY + slow query listener (Sprint 19 PR1).

Sprint 19 = polish + escala (§11 do Plano). Antes deste módulo, ``app/main.py``
e cada um dos ~17 workers Celery chamava ``create_async_engine(DATABASE_URL,
pool_pre_ping=True)`` sem ``pool_size``/``max_overflow``, herdando o default
SQLAlchemy (5+10) que estoura em 1k empresas concorrentes.

Este módulo centraliza:

1. ``build_async_engine(settings)`` — cria o engine com pool config consistente
   vindo do ``Settings`` (DB_POOL_SIZE etc.). Todos os call sites (``main.py``,
   workers) passam pelo mesmo builder.

2. ``install_slow_query_listener(engine, threshold_ms)`` — pendura event
   listeners ``before_cursor_execute``/``after_cursor_execute`` no
   ``sync_engine`` interno do AsyncEngine para medir cada query e logar
   ``db.slow_query`` structlog quando ultrapassar o limiar. Statement é
   truncado e parâmetros são *redacted* (`tenant_id`/CPF/CNPJ vazam pelo
   structlog processor existente).

Princípios cravados:
  * §8.10 Observabilidade — slow query log em toda sessão (app + workers).
  * §8.7 LGPD — statement truncado, parâmetros não logados.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings

log = structlog.get_logger(__name__)

# Atributo onde guardamos o ``perf_counter()`` do início da query — evita
# colidir com qualquer atributo nativo do ``ExecutionContext`` (que é interno
# do SQLAlchemy mas estável o suficiente para essa monkey-patch leve).
_START_ATTR = "_fiscal_query_start"

# Limite de caracteres do statement no log — evita Loki indigestão em
# CTE/UNION grandes ou INSERT bulk com VALUES enormes.
_STATEMENT_MAX_CHARS = 500


def build_async_engine(settings: Settings) -> AsyncEngine:
    """Factory canônica do ``AsyncEngine`` — aplica pool config + pre-ping.

    Antes do PR1 (Sprint 19), call sites herdavam o default SQLAlchemy de
    ``pool_size=5, max_overflow=10`` que estoura em workload concorrente
    (1k empresas, beat schedule diário). Esta função consolida o padrão.

    O ``pool_pre_ping=True`` continua: detecta conexões mortas (DB reiniciado,
    PgBouncer reciclando) antes de devolver ao caller. Custo é 1 round-trip
    extra por checkout — vale a pena em produção.

    ``pool_recycle`` é em segundos (não milissegundos). 1800s (30min) é
    conservador para Postgres 16 + PgBouncer transaction pooling — mantém a
    conexão jovem o suficiente para não bater em timeouts intermediários.
    """
    return create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
    )


def install_slow_query_listener(
    engine: AsyncEngine,
    threshold_ms: int,
) -> None:
    """Registra event listeners no engine para logar queries lentas.

    Pendura ``before_cursor_execute`` (marca início) e ``after_cursor_execute``
    (mede duração e loga se > ``threshold_ms``). O event system do SQLAlchemy
    é síncrono por design — o ``AsyncEngine`` expõe ``.sync_engine`` que é o
    alvo correto desses listeners.

    O listener é idempotente: registrar duas vezes faz cada query gerar dois
    logs. Chame uma única vez no ``lifespan`` do FastAPI.

    Threshold ≤ 0 desabilita o log (defensivo — facilita desligar em testes
    onde não queremos ruído).
    """
    if threshold_ms <= 0:
        return

    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        # ``context`` é o ``ExecutionContext`` da query atual; aceita
        # atributos arbitrários (é um objeto Python normal).
        setattr(context, _START_ATTR, time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        start = getattr(context, _START_ATTR, None)
        if start is None:
            return
        duracao_ms = (time.perf_counter() - start) * 1000.0
        if duracao_ms < threshold_ms:
            return
        # Statement truncado e single-lined para Loki/Grafana.
        snippet = statement.replace("\n", " ").strip()
        if len(snippet) > _STATEMENT_MAX_CHARS:
            snippet = snippet[:_STATEMENT_MAX_CHARS] + "…"
        log.warning(
            "db.slow_query",
            duracao_ms=round(duracao_ms, 2),
            limite_ms=threshold_ms,
            executemany=executemany,
            statement=snippet,
        )
