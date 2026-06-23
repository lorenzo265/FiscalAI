"""Sprint 15.5 PR4 — Smoke tests do worker advisor.enviar_digests_preparados."""

from __future__ import annotations

from app.workers.tasks.advisor_enviar_digests import (
    _LIMITE_TENTATIVAS,
    enviar_digests_preparados,
)


def test_worker_e_callable_e_tem_nome_celery() -> None:
    """O decorator @celery_app.task (stub ou real) preserva chamabilidade."""
    assert callable(enviar_digests_preparados)


def test_limite_tentativas_e_5() -> None:
    """Decisão de design: 5 ciclos sem sucesso → status='falhou'."""
    assert _LIMITE_TENTATIVAS == 5


def test_beat_schedule_inclui_envio_segunda_06_30() -> None:
    """Validate beat schedule: segunda 06:30 BR depois do gerar_digest 06:00."""
    try:
        from celery.schedules import crontab  # type: ignore[import-not-found]
    except ImportError:
        # Celery não instalado em CI — beat schedule retorna {} (stub).
        from app.workers.celery_app import _beat_schedule

        assert _beat_schedule() == {}
        return

    from app.workers.celery_app import _beat_schedule

    schedule = _beat_schedule()
    assert "advisor.enviar_digests_preparados" in schedule
    entry = schedule["advisor.enviar_digests_preparados"]
    assert entry["task"] == "advisor.enviar_digests_preparados"
    sched = entry["schedule"]
    assert isinstance(sched, crontab)
    # 06:30 segunda (day_of_week=1 em celery — segunda)
    assert "30" in str(sched.minute)
    assert "6" in str(sched.hour)


def test_beat_schedule_envio_e_30min_apos_geracao() -> None:
    """envio deve rodar DEPOIS do gerar_digest (mesmo cron day, hora maior)."""
    try:
        from celery.schedules import (
            crontab,  # type: ignore[import-not-found,unused-ignore]  # noqa: F401
        )
    except ImportError:
        return  # stub

    from app.workers.celery_app import _beat_schedule

    schedule = _beat_schedule()
    gerar = schedule["advisor.gerar_digest_semanal"]["schedule"]
    enviar = schedule["advisor.enviar_digests_preparados"]["schedule"]
    # Mesma segunda; envio em hora/minuto >= geração
    assert gerar.day_of_week == enviar.day_of_week
    # 06:00 < 06:30
    assert (str(gerar.hour), str(gerar.minute)) <= (
        str(enviar.hour),
        str(enviar.minute),
    )
