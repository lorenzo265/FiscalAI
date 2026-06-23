"""Testa auto-resolução de alertas ao postar nova vigência Camada 1 → 2 (PR2).

Quando ``TabelaAdminService`` é instanciado com ``alerta_repo`` (router PR2),
toda criação bem-sucedida de vigência marca como resolvidos os alertas
abertos do mesmo ``(tipo_tabela, ano)`` antes do commit.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.modules.tabelas_admin.repo import (
    SCDTabelasRepo,
    VigenciaTabelaLogRepo,
)
from app.modules.tabelas_admin.service import TabelaAdminService
from tests.unit.tabelas_admin._helpers import vigencia_inss_valida


def _service_com_alerta_repo(
    *,
    max_inss: date | None = None,
    alertas_resolvidos: int = 2,
) -> tuple[TabelaAdminService, AsyncMock, AsyncMock, AsyncMock]:
    log_repo = AsyncMock(spec=VigenciaTabelaLogRepo)
    log_repo.por_idempotency_key = AsyncMock(return_value=None)
    log_repo.criar = AsyncMock(side_effect=lambda obj: obj)

    scd_repo = AsyncMock(spec=SCDTabelasRepo)
    scd_repo.max_valid_from_inss = AsyncMock(return_value=max_inss)
    scd_repo.inserir_inss = AsyncMock(return_value=5)

    alerta_repo = AsyncMock()
    alerta_repo.resolver_relacionados = AsyncMock(return_value=alertas_resolvidos)

    session = AsyncMock()
    svc = TabelaAdminService(
        log_repo=log_repo, scd_repo=scd_repo, alerta_repo=alerta_repo
    )
    return svc, alerta_repo, scd_repo, session


@pytest.mark.asyncio
async def test_post_nova_vigencia_inss_marca_alertas_relacionados_resolvidos() -> None:
    """POST com valid_from=2026-01-15 → resolver_relacionados('inss', 2026) é chamado."""
    svc, alerta_repo, scd_repo, session = _service_com_alerta_repo(
        max_inss=date(2025, 1, 1)
    )
    payload = vigencia_inss_valida()  # valid_from=2026-01-15
    await svc.criar_vigencia_inss(session, payload)

    alerta_repo.resolver_relacionados.assert_awaited_once_with(
        tipo_tabela="inss", ano=2026
    )
    scd_repo.inserir_inss.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_resolucao_acontece_no_mesmo_commit_que_a_vigencia() -> None:
    """resolver_relacionados é chamado ANTES do commit final (atomicidade)."""
    svc, alerta_repo, _, session = _service_com_alerta_repo(
        max_inss=date(2025, 1, 1)
    )

    chamadas: list[str] = []

    async def _resolver_marca(*, tipo_tabela: str, ano: int) -> int:
        chamadas.append(f"resolver:{tipo_tabela}:{ano}")
        return 1

    async def _commit() -> None:
        chamadas.append("commit")

    alerta_repo.resolver_relacionados = AsyncMock(side_effect=_resolver_marca)
    session.commit = AsyncMock(side_effect=_commit)

    payload = vigencia_inss_valida()
    await svc.criar_vigencia_inss(session, payload)

    # resolver_relacionados precedeu commit
    assert chamadas == ["resolver:inss:2026", "commit"]


@pytest.mark.asyncio
async def test_sem_alerta_repo_pr1_segue_funcionando() -> None:
    """Backward-compat: TabelaAdminService sem alerta_repo não chama resolver."""
    log_repo = AsyncMock(spec=VigenciaTabelaLogRepo)
    log_repo.por_idempotency_key = AsyncMock(return_value=None)
    log_repo.criar = AsyncMock(side_effect=lambda obj: obj)
    scd_repo = AsyncMock(spec=SCDTabelasRepo)
    scd_repo.max_valid_from_inss = AsyncMock(return_value=date(2025, 1, 1))
    scd_repo.inserir_inss = AsyncMock(return_value=5)
    session = AsyncMock()

    svc = TabelaAdminService(log_repo=log_repo, scd_repo=scd_repo)
    payload = vigencia_inss_valida()
    log = await svc.criar_vigencia_inss(session, payload)
    # Sem AttributeError — fluxo backward-compat preservado.
    assert log.tipo_tabela == "inss"
    session.commit.assert_awaited_once()
