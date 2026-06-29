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
  │ whatsapp.expurgar_proc.    │ 04:00 diário     │ expurgar_mensagens_proc. │
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
        from celery.schedules import crontab
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
        "whatsapp.expurgar_processadas": {
            # Fase 2 PR7 — apaga registros de mensagens processadas > 7 dias.
            # Mantém a tabela enxuta; Meta não retry além de algumas horas.
            "task": "whatsapp.expurgar_processadas",
            "schedule": crontab(hour=4, minute=0),
            "options": {"queue": "default"},
        },
        # ── Sprint 13 PR3 — marketplace ──────────────────────────────────
        "marketplace.expirar_sla": {
            "task": "marketplace.expirar_sla",
            "schedule": crontab(minute=0),  # de hora em hora
            "options": {"queue": "default"},
        },
        "marketplace.recalcular_rating": {
            "task": "marketplace.recalcular_rating",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "default"},
        },
        "marketplace.expurgar_pii": {
            "task": "marketplace.expurgar_pii",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "default"},
        },
        "marketplace.check_crc_mensal": {
            "task": "marketplace.check_crc_mensal",
            "schedule": crontab(day_of_month=5, hour=6, minute=0),
            "options": {"queue": "default"},
        },
        # ── Sprint 14 PR3 — Reforma Tributária ────────────────────────────
        "reforma.refresh_cbs_ibs_historico": {
            "task": "reforma.refresh_cbs_ibs_historico",
            "schedule": crontab(hour=4, minute=30),  # diário 04:30
            "options": {"queue": "default"},
        },
        # ── Sprint 15 PR1 — AI Advisor ────────────────────────────────────
        "advisor.detectar_anomalias_diario": {
            "task": "advisor.detectar_anomalias_diario",
            "schedule": crontab(hour=7, minute=30),  # diário 07:30 BR
            "options": {"queue": "default"},
        },
        # ── Sprint 15 PR3 — Weekly digest ─────────────────────────────────
        "advisor.gerar_digest_semanal": {
            "task": "advisor.gerar_digest_semanal",
            "schedule": crontab(day_of_week=1, hour=6, minute=0),  # segunda 06:00 BR
            "options": {"queue": "default"},
        },
        # ── Sprint 15.5 — Envio do digest via Meta WhatsApp template ───────
        "advisor.enviar_digests_preparados": {
            "task": "advisor.enviar_digests_preparados",
            "schedule": crontab(day_of_week=1, hour=6, minute=30),  # segunda 06:30 BR
            "options": {"queue": "default"},
        },
        # ── Sprint 16 PR3 — geração proativa anual SPED ECD/ECF ────────────
        "sped.gerar_ecd_anual": {
            # 03/abril 04:00 BR — ~30 dias antes do prazo legal (último
            # dia útil de maio). Idempotente: empresas que já têm ECD
            # ativa do ano caem em SpedJaGerado (não-erro).
            "task": "sped.gerar_ecd_anual",
            "schedule": crontab(month_of_year=4, day_of_month=3, hour=4, minute=0),
            "options": {"queue": "default"},
        },
        "sped.gerar_ecf_anual": {
            # 03/junho 04:00 BR — ~30 dias antes do prazo legal (último
            # dia útil de julho).
            "task": "sped.gerar_ecf_anual",
            "schedule": crontab(month_of_year=6, day_of_month=3, hour=4, minute=0),
            "options": {"queue": "default"},
        },
        # ── Sprint 19.5 PR2 — Painel admin de tabelas tributárias ──────────
        "tabelas.verificar_vigencias": {
            # Diário 06:15 BR — 15min após o sync e-CAC para não competir por
            # conexões Postgres. Cria alertas idempotentes em alerta_admin.
            "task": "tabelas.verificar_vigencias",
            "schedule": crontab(hour=6, minute=15),
            "options": {"queue": "default"},
        },
        # ── Sprint 19.6 PR4 (#34) — EFD mensal proativa ────────────────────
        "sped.gerar_efd_contribuicoes_mensal": {
            # Dia 5 às 04:00 BR — gera EFD-Contribuições do mês anterior
            # (prazo legal: 10º dia útil do 2º mês subsequente, ~6 semanas).
            "task": "sped.gerar_efd_contribuicoes_mensal",
            "schedule": crontab(day_of_month=5, hour=4, minute=0),
            "options": {"queue": "default"},
        },
        "sped.gerar_efd_icms_ipi_mensal": {
            # Dia 5 às 04:00 BR — gera EFD ICMS-IPI do mês anterior. Prazo
            # varia por UF (SP dia 20, MG dia 9 etc. — ver migration 0046).
            "task": "sped.gerar_efd_icms_ipi_mensal",
            "schedule": crontab(day_of_month=5, hour=4, minute=0),
            "options": {"queue": "default"},
        },
        # ── Sprint 19.5 PR3 — Scraper DOU + LLM extrai estrutura ───────────
        # ── Sprint 19.6 PR4 (#4) — drain de webhook events Pluggy ─────────
        "open_finance.processar_webhook_events": {
            # A cada 5 minutos — drena eventos não processados como
            # backup ao trigger imediato do webhook (que pode falhar
            # se Celery estiver indisponível no momento).
            "task": "open_finance.processar_webhook_events",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "default"},
        },
        "tabelas.varrer_dou_mensal": {
            # Mensal dia 5 às 04:00 BR — busca matérias INSS/IRRF dos
            # últimos 60 dias, expira sugestões > 60 dias.
            "task": "tabelas.varrer_dou_mensal",
            "schedule": crontab(day_of_month=5, hour=4, minute=0),
            "options": {"queue": "default"},
        },
        # ── Marco 4 PR3 (#14) — alerta por e-mail de obrigações a vencer ───
        "agenda.alertar_vencimentos": {
            # Diário 06:45 BR — varre AgendaItem pendentes a vencer na janela
            # (ALERTA_AGENDA_DIAS) ainda não alertados → e-mail + alertado_em.
            "task": "agenda.alertar_vencimentos",
            "schedule": crontab(hour=6, minute=45),
            "options": {"queue": "default"},
        },
    }


def _build() -> _CeleryStub:
    """Constrói a Celery app real se o pacote estiver disponível, senão o stub."""
    try:
        from celery import Celery
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


def enqueue(task: Any, *args: Any, **kwargs: Any) -> None:
    """Sprint 19.6 PR4 helper — chama ``task.delay(*args, **kwargs)`` quando
    Celery real está ativo; faz log no-op com stub.

    Permite que callers (webhooks, services) disparem tasks sem checar a
    cada vez se o broker está disponível. Em dev (stub) o evento fica
    apenas registrado no banco e será processado pelo próximo beat
    schedule quando Celery for ativado.
    """
    import structlog

    _log = structlog.get_logger(__name__)
    delay = getattr(task, "delay", None)
    task_name = getattr(task, "__name__", str(task))
    if delay is None:
        # Stub — task é função pura. Não roda síncrono (bloquearia
        # request HTTP); apenas loga. Beat schedule eventual drena depois.
        _log.info("celery.enqueue.stub", task=task_name)
        return
    try:
        delay(*args, **kwargs)
        _log.info("celery.enqueue.ok", task=task_name)
    except Exception:
        _log.exception("celery.enqueue.falhou", task=task_name)
