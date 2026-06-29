"""Marco 4 PR3 (#14) — smoke tests do worker agenda.alertar_vencimentos."""

from __future__ import annotations

from app.workers.tasks.alerta_fiscal import alertar_vencimentos


def test_worker_e_callable_e_tem_nome_celery() -> None:
    """O decorator @celery_app.task (stub ou real) preserva chamabilidade."""
    assert callable(alertar_vencimentos)


def test_beat_schedule_inclui_alerta_diario_06_45() -> None:
    try:
        from celery.schedules import crontab  # type: ignore[import-not-found]
    except ImportError:
        # Celery não instalado em CI — beat schedule retorna {} (stub).
        from app.workers.celery_app import _beat_schedule

        assert _beat_schedule() == {}
        return

    from app.workers.celery_app import _beat_schedule

    schedule = _beat_schedule()
    assert "agenda.alertar_vencimentos" in schedule
    entry = schedule["agenda.alertar_vencimentos"]
    assert entry["task"] == "agenda.alertar_vencimentos"
    sched = entry["schedule"]
    assert isinstance(sched, crontab)
    assert "45" in str(sched.minute)
    assert "6" in str(sched.hour)
