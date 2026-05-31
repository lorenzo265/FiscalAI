"""Testes do AdvisorService.gerar_digest_semanal — orquestração I/O (Sprint 15 PR3)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.modules.advisor.service import AdvisorService
from app.shared.exceptions import DigestJaGeradoNaSemana, EmpresaNaoEncontrada


_TZ_BR = ZoneInfo("America/Sao_Paulo")
_COMP = date(2026, 5, 20)  # quarta-feira → semana 2026-W21


def _empresa() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        regime_tributario="simples_nacional",
        anexo_simples="III",
        cnae_principal="62.01-5",
        razao_social="ACME LTDA",
        nome_fantasia=None,
        uf="SP",
    )


def _persisted_digest(empresa_id: uuid.UUID, semana_iso: str = "2026-W21") -> MagicMock:
    """Mock do ORM DigestSemanal — só atributos consultados pelo service."""
    m = MagicMock()
    m.id = uuid.uuid4()
    m.empresa_id = empresa_id
    m.semana_iso = semana_iso
    m.superseded_by = None
    m.dispensada_em = None
    return m


# ── Caminho feliz com template ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gera_digest_caminho_feliz_template() -> None:
    empresa = _empresa()
    session = AsyncMock()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    digest_repo = AsyncMock()
    digest_repo.ativo_por_semana = AsyncMock(return_value=None)
    digest_repo.apuracoes_da_semana = AsyncMock(return_value=[])
    digest_repo.anomalias_abertas_para_digest = AsyncMock(return_value=[])
    digest_repo.agenda_proximos_vencimentos = AsyncMock(return_value=[])
    digest_repo.adicionar = AsyncMock(side_effect=lambda x: x)

    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo),
        patch.object(
            AdvisorService, "listar_sugestoes", AsyncMock(return_value=[])
        ),
    ):
        digest = await AdvisorService(session).gerar_digest_semanal(
            empresa.id, competencia=_COMP
        )

    assert digest.semana_iso == "2026-W21"
    assert digest.fonte_redacao == "template"
    assert digest.status == "preparado"
    digest_repo.adicionar.assert_awaited_once()
    digest_repo.marcar_superseded.assert_not_awaited()


@pytest.mark.asyncio
async def test_gera_digest_existente_sem_forcar_levanta_409() -> None:
    empresa = _empresa()
    existente = _persisted_digest(empresa.id)
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    digest_repo = AsyncMock()
    digest_repo.ativo_por_semana = AsyncMock(return_value=existente)

    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo),
    ):
        with pytest.raises(DigestJaGeradoNaSemana):
            await AdvisorService(session).gerar_digest_semanal(
                empresa.id, competencia=_COMP, forcar=False
            )


@pytest.mark.asyncio
async def test_gera_digest_com_forcar_supersede_anterior() -> None:
    empresa = _empresa()
    existente = _persisted_digest(empresa.id)
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    digest_repo = AsyncMock()
    digest_repo.ativo_por_semana = AsyncMock(return_value=existente)
    digest_repo.apuracoes_da_semana = AsyncMock(return_value=[])
    digest_repo.anomalias_abertas_para_digest = AsyncMock(return_value=[])
    digest_repo.agenda_proximos_vencimentos = AsyncMock(return_value=[])
    digest_repo.adicionar = AsyncMock(side_effect=lambda x: x)

    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo),
        patch.object(
            AdvisorService, "listar_sugestoes", AsyncMock(return_value=[])
        ),
    ):
        await AdvisorService(session).gerar_digest_semanal(
            empresa.id, competencia=_COMP, forcar=True
        )

    digest_repo.marcar_superseded.assert_awaited_once()
    digest_repo.adicionar.assert_awaited_once()


@pytest.mark.asyncio
async def test_empresa_nao_encontrada_levanta_404() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo):
        with pytest.raises(EmpresaNaoEncontrada):
            await AdvisorService(session).gerar_digest_semanal(
                uuid.uuid4(), competencia=_COMP
            )


@pytest.mark.asyncio
async def test_default_competencia_e_hoje_br() -> None:
    """Quando ``competencia=None``, deriva de ``datetime.now(TZ_BR).date()``."""
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    digest_repo = AsyncMock()
    digest_repo.ativo_por_semana = AsyncMock(return_value=None)
    digest_repo.apuracoes_da_semana = AsyncMock(return_value=[])
    digest_repo.anomalias_abertas_para_digest = AsyncMock(return_value=[])
    digest_repo.agenda_proximos_vencimentos = AsyncMock(return_value=[])
    digest_repo.adicionar = AsyncMock(side_effect=lambda x: x)

    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo),
        patch.object(
            AdvisorService, "listar_sugestoes", AsyncMock(return_value=[])
        ),
    ):
        digest = await AdvisorService(session).gerar_digest_semanal(empresa.id)

    # Semana ISO deve refletir uma semana real
    assert digest.semana_iso.startswith("20")
    assert "-W" in digest.semana_iso


# ── Listagem + obtenção ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_listar_digests_caminho_feliz() -> None:
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    digest_repo = AsyncMock()
    digests = [_persisted_digest(empresa.id), _persisted_digest(empresa.id, "2026-W20")]
    digest_repo.listar = AsyncMock(return_value=digests)
    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo),
    ):
        result = await AdvisorService(session).listar_digests(empresa.id)
    assert result == digests


@pytest.mark.asyncio
async def test_listar_digests_empresa_inexistente() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo):
        with pytest.raises(EmpresaNaoEncontrada):
            await AdvisorService(session).listar_digests(uuid.uuid4())


@pytest.mark.asyncio
async def test_obter_digest_existente_devolve_orm() -> None:
    empresa = _empresa()
    digest = _persisted_digest(empresa.id)
    session = AsyncMock()
    digest_repo = AsyncMock()
    digest_repo.por_id = AsyncMock(return_value=digest)
    with patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo):
        result = await AdvisorService(session).obter_digest(empresa.id, digest.id)
    assert result is digest


@pytest.mark.asyncio
async def test_obter_digest_de_outra_empresa_levanta_404() -> None:
    """Defesa em profundidade — além do RLS."""
    digest = _persisted_digest(uuid.uuid4())  # outra empresa
    session = AsyncMock()
    digest_repo = AsyncMock()
    digest_repo.por_id = AsyncMock(return_value=digest)
    with patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo):
        with pytest.raises(EmpresaNaoEncontrada):
            await AdvisorService(session).obter_digest(uuid.uuid4(), digest.id)
