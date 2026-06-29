"""Marco 4 — descoberta de tasks p/ o ``include`` do Celery.

Garante que toda task em ``app/workers/tasks/*.py`` é descoberta (e portanto
REGISTRADA no worker), fechando o gap pré-existente em que o worker subia sem
nenhuma task agendada registrada. Runnable sem Celery (só ``pkgutil``).
"""

from __future__ import annotations

from app.workers.celery_app import _descobrir_modulos_tasks


def test_descobre_tasks_criticas() -> None:
    mods = _descobrir_modulos_tasks()
    # E-mail (on-demand) + as agendadas precisam estar no include.
    assert "app.workers.tasks.email_enviar" in mods
    assert "app.workers.tasks.alerta_fiscal" in mods
    assert "app.workers.tasks.advisor_enviar_digests" in mods


def test_nao_inclui_init_nem_dunder() -> None:
    mods = _descobrir_modulos_tasks()
    assert "app.workers.tasks.__init__" not in mods
    assert all(not m.rsplit(".", 1)[-1].startswith("_") for m in mods)


def test_cada_task_agendada_tem_modulo_descoberto() -> None:
    """Toda task referenciada no beat_schedule deve ter um módulo no include.

    Só é assertível com Celery instalado (senão `_beat_schedule()` é {}); sem
    Celery, vira no-op consciente.
    """
    try:
        import celery  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        from app.workers.celery_app import _beat_schedule

        assert _beat_schedule() == {}
        return

    from app.workers.celery_app import _beat_schedule

    # O include não é vazio quando Celery existe.
    assert len(_descobrir_modulos_tasks()) > 0
    # E o beat tem entradas (sanidade — o cruzamento nome→módulo é por convenção).
    assert len(_beat_schedule()) > 0
