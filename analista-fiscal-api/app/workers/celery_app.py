"""App Celery + beat schedule do Analista Fiscal (Sprint 11 PR3).

Padrão dual:
  * Se ``celery`` estiver instalado em runtime, criamos uma ``Celery`` real
    com broker/backend Redis, queue ``default`` e beat schedule para os 4
    workers periódicos da Sprint 11.
  * Caso contrário, usamos o stub local que aceita ``.task(...)`` e devolve
    a função intocada — permite testar o corpo das tasks como funções
    normais e mantém imports seguros sem `celery` no PATH.

Beat schedule:
  ┌────────────────────────────┬──────────────────┬──────────────────────────┐
  │ Task                       │ Cron             │ Implementação            │
  ├────────────────────────────┼──────────────────┼──────────────────────────┤
  │ e_cac.sync_diario          │ 06:00 diário     │ sync_e_cac_empresa       │
  │ open_finance.sync_diario   │ 07:00 diário     │ sync_pluggy_empresa      │
  │ imobilizado.depreciacao    │ 03:00 dia 1°/mês │ gerar_depreciacao_empresa│
  │ provisoes.mensal           │ 23:00 último dia │ gerar_provisao_empresa   │
  │ rbt12.refresh_mensal       │ 06:00 dia 2/mês  │ refresh_rbt12_mensal     │
  └────────────────────────────┴──────────────────┴──────────────────────────┘

Para ativar Celery real:

    poetry add celery[redis]
    poetry run celery -A app.workers.celery_app worker -Q default -l info
    poetry run celery -A app.workers.celery_app beat -l info

Princípios: §8.7 (tenant_id propagado), §8.9 (idempotência via UPSERT em
tabelas de destino), §8.10 (log estruturado).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from app.config import get_settings

_F = TypeVar("_F", bound=Callable[..., Any])


class _CeleryStub:
    """Stub mínimo de :class:`celery.Celery` — só o suficiente para mypy + import.

    Aceita o mesmo decorator ``.task(**kwargs)`` que a Celery real e devolve a
    função recebida sem alteração. Tasks decoradas com este stub são chamáveis
    diretamente como funções regulares.
    """

    def __init__(self, name: str, *, broker: str | None = None) -> None:
        self.main = name
        self.broker = broker
        self.conf = _StubConf()

    def task(self, *_args: Any, **_kwargs: Any) -> Callable[[_F], _F]:
        def decorator(fn: _F) -> _F:
            return fn

        return decorator


class _StubConf:
    """Stub mínimo de ``Celery.conf`` — aceita ``.beat_schedule = {...}``."""

    def __init__(self) -> None:
        self.beat_schedule: dict[str, Any] = {}
        self.timezone: str = "America/Sao_Paulo"


# ── Beat schedule (definição declarativa, aplicada se Celery real existir) ──


def _beat_schedule() -> dict[str, Any]:
    """Retorna o beat schedule como dict; pode ser introspectado em testes.

    Imports do ``celery.schedules.crontab`` ficam lazy — se Celery não está
    instalado, usamos ``None`` como sentinel (o stub ignora qualquer schedule).
    """
    try:
        from celery.schedules import crontab  # type: ignore[import-not-found]
    except ImportError:
        return {}

    return {
        "e_cac.sync_diario": {
            "task": "e_cac.sync_empresa",
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": "default"},
        },
        "open_finance.sync_diario": {
            "task": "open_finance.sync_pluggy_empresa",
            "schedule": crontab(hour=7, minute=0),
            "options": {"queue": "default"},
        },
        "imobilizado.depreciacao_mensal": {
            "task": "imobilizado.gerar_depreciacao_empresa",
            "schedule": crontab(day_of_month=1, hour=3, minute=0),
            "options": {"queue": "default"},
        },
        "provisoes.mensal": {
            # Roda no dia 28 às 23h — qualquer mês tem dia 28, evitando
            # last-day-of-month complications. Service garante idempotência.
            "task": "provisoes.gerar_provisao_empresa",
            "schedule": crontab(day_of_month=28, hour=23, minute=0),
            "options": {"queue": "default"},
        },
        "rbt12.refresh_mensal": {
            # Fase 2 PR3 — refresh global da view materializada rbt12_mensal,
            # dia 2 às 6h (depois do encerramento contábil do mês anterior).
            "task": "rbt12.refresh_mensal",
            "schedule": crontab(day_of_month=2, hour=6, minute=0),
            "options": {"queue": "default"},
        },
    }


def _build() -> _CeleryStub:
    """Constrói a Celery app real se o pacote estiver disponível, senão o stub."""
    try:
        from celery import Celery  # type: ignore[import-not-found]
    except ImportError:
        settings = get_settings()
        return _CeleryStub("analista-fiscal", broker=settings.REDIS_URL)

    settings = get_settings()
    real = Celery(
        "analista-fiscal",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
    )
    real.conf.update(
        task_acks_late=True,
        task_default_queue="default",
        worker_prefetch_multiplier=1,
        timezone="America/Sao_Paulo",
        enable_utc=True,
        beat_schedule=_beat_schedule(),
    )
    return real  # type: ignore[no-any-return]


celery_app: _CeleryStub = _build()
