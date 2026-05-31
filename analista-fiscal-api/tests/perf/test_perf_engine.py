"""Testes do ``app.shared.db.perf`` — engine builder + slow query listener.

Sprint 19 PR1 — Polish + escala. Valida que o builder aplica pool config
do ``Settings`` e que o listener loga apenas quando duração ≥ threshold.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import patch

import pytest
import structlog
from sqlalchemy import event
from structlog.testing import capture_logs

from app.config import Settings
from app.shared.db.perf import build_async_engine, install_slow_query_listener


# ─────────────────────────────────────────────────────────────────────────────
# build_async_engine
# ─────────────────────────────────────────────────────────────────────────────


def _settings_padrao() -> Settings:
    """Settings sintéticos para teste. DSN é stub (não conecta — só constroi engine)."""
    return Settings(
        DATABASE_URL="postgresql+asyncpg://t:t@localhost:5432/t",
        DB_POOL_SIZE=20,
        DB_MAX_OVERFLOW=30,
        DB_POOL_TIMEOUT=30,
        DB_POOL_RECYCLE=1800,
        SLOW_QUERY_THRESHOLD_MS=500,
    )


def test_build_async_engine_aplica_pool_size() -> None:
    settings = _settings_padrao()
    engine = build_async_engine(settings)
    try:
        # ``sync_engine.pool.size()`` devolve o pool_size configurado.
        assert engine.sync_engine.pool.size() == 20
    finally:
        # Não chamar dispose async — engine nunca conectou.
        engine.sync_engine.dispose()


def test_build_async_engine_aplica_max_overflow() -> None:
    settings = _settings_padrao()
    engine = build_async_engine(settings)
    try:
        # ``_max_overflow`` é atributo interno, mas é o caminho documentado
        # para introspecção em testes (SQLAlchemy QueuePool).
        assert engine.sync_engine.pool._max_overflow == 30  # type: ignore[attr-defined]
    finally:
        engine.sync_engine.dispose()


def test_build_async_engine_usa_valores_customizados_do_settings() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://t:t@localhost:5432/t",
        DB_POOL_SIZE=5,
        DB_MAX_OVERFLOW=2,
        DB_POOL_TIMEOUT=10,
        DB_POOL_RECYCLE=60,
    )
    engine = build_async_engine(settings)
    try:
        assert engine.sync_engine.pool.size() == 5
        assert engine.sync_engine.pool._max_overflow == 2  # type: ignore[attr-defined]
    finally:
        engine.sync_engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# install_slow_query_listener
# ─────────────────────────────────────────────────────────────────────────────


class _FakeContext:
    """Stand-in para ``ExecutionContext`` — aceita ``setattr`` arbitrário."""


def _disparar_query(
    engine: Any,
    statement: str,
    duracao_ms: float,
    executemany: bool = False,
) -> _FakeContext:
    """Dispara before/after manualmente simulando uma query com duração dada.

    Em vez de rodar uma query real (que exige DB), invocamos os handlers
    diretamente via ``engine.sync_engine.dispatch.<evento>``.
    """
    sync_engine = engine.sync_engine
    ctx = _FakeContext()
    sync_engine.dispatch.before_cursor_execute(
        None, None, statement, None, ctx, executemany
    )
    # Avança o relógio "para trás" no perf_counter para simular duração.
    # _START_ATTR foi setado em ``before``; subtraímos o equivalente.
    from app.shared.db.perf import _START_ATTR  # type: ignore[attr-defined]

    inicio = getattr(ctx, _START_ATTR)
    setattr(ctx, _START_ATTR, inicio - duracao_ms / 1000.0)
    sync_engine.dispatch.after_cursor_execute(
        None, None, statement, None, ctx, executemany
    )
    return ctx


def _make_engine() -> Any:
    return build_async_engine(_settings_padrao())


def test_listener_loga_quando_query_excede_threshold() -> None:
    engine = _make_engine()
    try:
        install_slow_query_listener(engine, threshold_ms=100)
        with capture_logs() as logs:
            _disparar_query(engine, "SELECT 1", duracao_ms=250.0)
        slow_logs = [le for le in logs if le.get("event") == "db.slow_query"]
        assert len(slow_logs) == 1
        log_entry = slow_logs[0]
        assert log_entry["statement"] == "SELECT 1"
        assert log_entry["limite_ms"] == 100
        assert log_entry["duracao_ms"] >= 250.0
        assert log_entry["log_level"] == "warning"
    finally:
        engine.sync_engine.dispose()


def test_listener_silencia_quando_query_abaixo_do_threshold() -> None:
    engine = _make_engine()
    try:
        install_slow_query_listener(engine, threshold_ms=500)
        with capture_logs() as logs:
            _disparar_query(engine, "SELECT 1", duracao_ms=10.0)
        slow_logs = [le for le in logs if le.get("event") == "db.slow_query"]
        assert slow_logs == []
    finally:
        engine.sync_engine.dispose()


def test_listener_threshold_zero_ou_negativo_e_no_op() -> None:
    engine = _make_engine()
    try:
        install_slow_query_listener(engine, threshold_ms=0)
        install_slow_query_listener(engine, threshold_ms=-10)
        # Como o listener nem foi registrado, nada acontece no dispatch.
        # Para confirmar, disparamos uma "query lenta" e checamos logs.
        with capture_logs() as logs:
            try:
                _disparar_query(engine, "SELECT 1", duracao_ms=10_000.0)
            except Exception:
                # Sem listener registrado, before/after ainda funcionam,
                # mas nenhum handler escuta — sem erro.
                pass
        slow_logs = [le for le in logs if le.get("event") == "db.slow_query"]
        assert slow_logs == []
    finally:
        engine.sync_engine.dispose()


def test_listener_trunca_statement_grande() -> None:
    engine = _make_engine()
    try:
        install_slow_query_listener(engine, threshold_ms=10)
        statement_gigante = "SELECT " + ("a, " * 1000) + "1"
        with capture_logs() as logs:
            _disparar_query(engine, statement_gigante, duracao_ms=50.0)
        slow_logs = [le for le in logs if le.get("event") == "db.slow_query"]
        assert len(slow_logs) == 1
        # Truncado a ~500 chars + reticências.
        assert len(slow_logs[0]["statement"]) <= 501
        assert slow_logs[0]["statement"].endswith("…")
    finally:
        engine.sync_engine.dispose()


def test_listener_normaliza_quebras_de_linha_no_statement() -> None:
    engine = _make_engine()
    try:
        install_slow_query_listener(engine, threshold_ms=10)
        statement_multilinha = "SELECT *\nFROM empresa\nWHERE id = 1"
        with capture_logs() as logs:
            _disparar_query(engine, statement_multilinha, duracao_ms=50.0)
        slow_logs = [le for le in logs if le.get("event") == "db.slow_query"]
        assert len(slow_logs) == 1
        # Quebras de linha viraram espaços.
        assert "\n" not in slow_logs[0]["statement"]
        assert "SELECT * FROM empresa WHERE id = 1" in slow_logs[0]["statement"]
    finally:
        engine.sync_engine.dispose()


def test_listener_marca_executemany_no_log() -> None:
    engine = _make_engine()
    try:
        install_slow_query_listener(engine, threshold_ms=10)
        with capture_logs() as logs:
            _disparar_query(
                engine, "INSERT INTO x VALUES (?)", duracao_ms=50.0, executemany=True
            )
        slow_logs = [le for le in logs if le.get("event") == "db.slow_query"]
        assert len(slow_logs) == 1
        assert slow_logs[0]["executemany"] is True
    finally:
        engine.sync_engine.dispose()
