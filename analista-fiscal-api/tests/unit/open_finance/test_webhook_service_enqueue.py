"""Testes do WebhookService — caminho de enqueue Celery (S1 Plataforma).

Cobre:
  * persistir: evento novo → chama _enfileirar_sync com event_id + pluggy_item_id
  * persistir: evento duplicado (ON CONFLICT) → NÃO chama _enfileirar_sync
  * _enfileirar_sync stub (sem apply_async): retorna False, chama enqueue helper
  * _enfileirar_sync Celery real (apply_async disponível): retorna True,
      task_id = f"webhook-sync-{event_id}" (idempotência §8.9)
  * _enfileirar_sync apply_async levanta → retorna False (fallback seguro)
  * pluggy_item_id propagado como kwarg da task (routing cross-tenant §8.7)
  * task stub: aceita pluggy_item_id opcional, retorna {"status": "noop"}
  * enqueue helper: sem .delay → no-op; com .delay → chama delay; .delay levanta → silencioso

Princípios testados:
  §8.9 — idempotência: task_id derivado de event_id; ON CONFLICT DO NOTHING no DB.
  §8.7 — tenant_id NÃO propagado no webhook (routing feito pela task como admin).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.open_finance.webhook_service import (
    WebhookService,
    _enfileirar_sync,
)

# Caminhos de patch — módulo usa imports no topo, então patch via módulo funciona.
_MOD = "app.modules.open_finance.webhook_service"


# ── helpers ───────────────────────────────────────────────────────────────────


def _eid() -> str:
    return "evt-" + str(uuid.uuid4())[:8]


def _iid() -> str:
    return "pluggy-" + str(uuid.uuid4())[:8]


def _mock_session(inserido: uuid.UUID | None) -> AsyncMock:
    """AsyncMock de sessão: execute().scalar_one_or_none() == inserido."""
    session = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = inserido
    session.execute = AsyncMock(return_value=exec_result)
    session.commit = AsyncMock()
    return session


# ── WebhookService.persistir ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persistir_novo_marca_persistido_e_enfileira() -> None:
    """Evento novo: persistido=True, enfileirado=True, _enfileirar_sync chamado."""
    eid, iid = _eid(), _iid()
    session = _mock_session(inserido=uuid.uuid4())

    with patch(f"{_MOD}._enfileirar_sync", return_value=True) as mock_enq:
        r = await WebhookService().persistir(
            session,
            event_id=eid,
            item_pluggy_id=iid,
            event_type="item/updated",
            payload={"id": eid},
        )

    assert r.persistido is True
    assert r.duplicado is False
    assert r.enfileirado is True
    mock_enq.assert_called_once_with(event_id=eid, item_pluggy_id=iid)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persistir_duplicado_nao_enfileira() -> None:
    """ON CONFLICT retorna None → duplicado=True, _enfileirar_sync NÃO chamado."""
    session = _mock_session(inserido=None)

    with patch(f"{_MOD}._enfileirar_sync", return_value=True) as mock_enq:
        r = await WebhookService().persistir(
            session,
            event_id=_eid(),
            item_pluggy_id=_iid(),
            event_type="item/updated",
            payload={},
        )

    assert r.duplicado is True
    assert r.persistido is False
    assert r.enfileirado is False
    mock_enq.assert_not_called()


@pytest.mark.asyncio
async def test_persistir_commit_chamado_em_ambos_os_casos() -> None:
    """commit() é chamado tanto para evento novo quanto duplicado."""
    session_novo = _mock_session(inserido=uuid.uuid4())
    session_dup = _mock_session(inserido=None)

    with patch(f"{_MOD}._enfileirar_sync", return_value=False):
        await WebhookService().persistir(
            session_novo, event_id=_eid(), item_pluggy_id=_iid(),
            event_type="x", payload={},
        )
        await WebhookService().persistir(
            session_dup, event_id=_eid(), item_pluggy_id=_iid(),
            event_type="x", payload={},
        )

    session_novo.commit.assert_awaited_once()
    session_dup.commit.assert_awaited_once()


# ── _enfileirar_sync — stub (sem Celery instalado) ────────────────────────────


def test_enfileirar_sync_stub_sem_apply_async_retorna_false() -> None:
    """Celery não instalado: apply_async ausente → retorna False, usa enqueue."""
    eid, iid = _eid(), _iid()
    # spec=[] → sem nenhum atributo → sem apply_async
    mock_task = MagicMock(spec=[])
    mock_task.__name__ = "processar_webhook_events_pendentes"
    mock_enqueue = MagicMock()

    with (
        patch(f"{_MOD}.enqueue", mock_enqueue),
        patch(f"{_MOD}.processar_webhook_events_pendentes", mock_task),
    ):
        resultado = _enfileirar_sync(event_id=eid, item_pluggy_id=iid)

    assert resultado is False
    mock_enqueue.assert_called_once_with(mock_task)


# ── _enfileirar_sync — Celery real (apply_async disponível) ───────────────────


def test_enfileirar_sync_real_task_id_derivado_do_event_id() -> None:
    """Celery real: apply_async chamado com task_id=webhook-sync-{event_id}."""
    eid = "evt-abc-123"
    iid = "item-xyz-456"
    mock_task = MagicMock()
    mock_task.apply_async = MagicMock(return_value=None)

    with (
        patch(f"{_MOD}.enqueue", MagicMock()),
        patch(f"{_MOD}.processar_webhook_events_pendentes", mock_task),
    ):
        resultado = _enfileirar_sync(event_id=eid, item_pluggy_id=iid)

    assert resultado is True
    mock_task.apply_async.assert_called_once_with(
        kwargs={"pluggy_item_id": iid},
        task_id=f"webhook-sync-{eid}",
    )


def test_enfileirar_sync_idempotencia_mesmo_event_id_mesmo_task_id() -> None:
    """Re-enqueue com mesmo event_id → mesmo task_id → broker descarta (§8.9)."""
    eid = "evt-idempotente-001"
    iid = "item-idem"
    task_ids: list[str] = []
    mock_task = MagicMock()
    mock_task.apply_async = MagicMock(
        side_effect=lambda **kw: task_ids.append(str(kw.get("task_id", "")))
    )

    with (
        patch(f"{_MOD}.enqueue", MagicMock()),
        patch(f"{_MOD}.processar_webhook_events_pendentes", mock_task),
    ):
        _enfileirar_sync(event_id=eid, item_pluggy_id=iid)
        _enfileirar_sync(event_id=eid, item_pluggy_id=iid)

    assert len(task_ids) == 2
    assert task_ids[0] == task_ids[1] == f"webhook-sync-{eid}"


def test_enfileirar_sync_pluggy_item_id_propagado_nos_kwargs() -> None:
    """pluggy_item_id passado como kwargs → task faz routing cross-tenant (§8.7)."""
    iid = "item-banco-especifico-999"
    mock_task = MagicMock()
    mock_task.apply_async = MagicMock(return_value=None)

    with (
        patch(f"{_MOD}.enqueue", MagicMock()),
        patch(f"{_MOD}.processar_webhook_events_pendentes", mock_task),
    ):
        _enfileirar_sync(event_id=_eid(), item_pluggy_id=iid)

    chamada = mock_task.apply_async.call_args
    assert chamada.kwargs["kwargs"]["pluggy_item_id"] == iid


def test_enfileirar_sync_apply_async_exception_retorna_false() -> None:
    """apply_async levanta (Redis down) → retorna False, beat schedule drena."""
    mock_task = MagicMock()
    mock_task.apply_async = MagicMock(
        side_effect=ConnectionRefusedError("Redis indisponível")
    )

    with (
        patch(f"{_MOD}.enqueue", MagicMock()),
        patch(f"{_MOD}.processar_webhook_events_pendentes", mock_task),
    ):
        resultado = _enfileirar_sync(event_id=_eid(), item_pluggy_id=_iid())

    assert resultado is False


def test_enfileirar_sync_event_ids_distintos_geram_task_ids_distintos() -> None:
    """Eventos distintos geram task_ids distintos → sem colisão no broker."""
    task_ids: list[str] = []
    mock_task = MagicMock()
    mock_task.apply_async = MagicMock(
        side_effect=lambda **kw: task_ids.append(str(kw.get("task_id", "")))
    )

    with (
        patch(f"{_MOD}.enqueue", MagicMock()),
        patch(f"{_MOD}.processar_webhook_events_pendentes", mock_task),
    ):
        _enfileirar_sync(event_id="evt-001", item_pluggy_id="item-x")
        _enfileirar_sync(event_id="evt-002", item_pluggy_id="item-x")

    assert len(task_ids) == 2
    assert task_ids[0] != task_ids[1]
    assert task_ids[0] == "webhook-sync-evt-001"
    assert task_ids[1] == "webhook-sync-evt-002"


# ── task processar_webhook_events_pendentes (stub) ────────────────────────────


def test_processar_webhook_stub_sem_args_retorna_noop() -> None:
    """Task stub sem args: status=noop, pluggy_item_id=None."""
    from app.workers.tasks.sync_pluggy import processar_webhook_events_pendentes

    r = processar_webhook_events_pendentes()
    assert r["status"] == "noop"
    assert r["pluggy_item_id"] is None


def test_processar_webhook_stub_com_pluggy_item_id() -> None:
    """Task stub com pluggy_item_id: propaga no resultado (para tracing)."""
    from app.workers.tasks.sync_pluggy import processar_webhook_events_pendentes

    r = processar_webhook_events_pendentes(pluggy_item_id="item-abc-123")
    assert r["status"] == "noop"
    assert r["pluggy_item_id"] == "item-abc-123"


def test_processar_webhook_stub_item_ids_distintos_isolados() -> None:
    """Task stub é stateless: chamadas distintas não compartilham estado."""
    from app.workers.tasks.sync_pluggy import processar_webhook_events_pendentes

    r1 = processar_webhook_events_pendentes(pluggy_item_id="item-A")
    r2 = processar_webhook_events_pendentes(pluggy_item_id="item-B")
    assert r1["pluggy_item_id"] == "item-A"
    assert r2["pluggy_item_id"] == "item-B"


# ── celery_app.enqueue helper ─────────────────────────────────────────────────


def test_enqueue_helper_stub_sem_delay_nao_executa() -> None:
    """enqueue com task sem .delay: não executa (não bloquearia request HTTP)."""
    from app.workers.celery_app import enqueue

    chamadas: list[str] = []

    def fake_task() -> None:
        chamadas.append("executou")

    enqueue(fake_task)
    assert chamadas == []


def test_enqueue_helper_real_chama_delay_com_args_e_kwargs() -> None:
    """enqueue com task com .delay: chama delay(*args, **kwargs)."""
    from app.workers.celery_app import enqueue

    chamadas: list[tuple[tuple[object, ...], dict[str, object]]] = []

    task = MagicMock()
    task.delay = MagicMock(side_effect=lambda *a, **kw: chamadas.append((a, kw)))
    task.__name__ = "fake_task"

    enqueue(task, "arg1", chave="valor")
    assert chamadas == [(("arg1",), {"chave": "valor"})]


def test_enqueue_helper_delay_exception_nao_propaga() -> None:
    """enqueue: se .delay levanta, exceção não re-propagada (fail silencioso)."""
    from app.workers.celery_app import enqueue

    task = MagicMock()
    task.delay = MagicMock(side_effect=RuntimeError("broker down"))
    task.__name__ = "fake_task"

    enqueue(task)  # não deve levantar
