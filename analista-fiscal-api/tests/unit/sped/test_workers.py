"""Testes dos workers Celery sped.gerar_ecd_anual / sped.gerar_ecf_anual.

Resiliência: falha em uma empresa não aborta as demais. Idempotência:
``SpedJaGerado`` é absorvido como ``empresas_ja_gerada``. ``SemDadosParaSped``
e ``EmpresaNaoElegivelEcd`` também são absorvidos como categorias separadas
no contador final.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.exceptions import (
    EmpresaNaoElegivelEcd,
    SemDadosParaSped,
    SpedJaGerado,
)
from app.workers.tasks import sped_gerar_anual


def _empresa(regime: str = "lucro_presumido") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        ativa=True,
        regime_tributario=regime,
    )


def _patch_engine_e_empresas(empresas: list[SimpleNamespace]) -> AsyncMock:
    """Mocka async_sessionmaker + select(Empresa) → lista informada."""
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = empresas
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_session.execute.return_value = result_mock
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    return mock_session


@pytest.mark.asyncio
async def test_executar_geracao_conta_categorias_corretamente() -> None:
    """Cada categoria de retorno do gerar_fn vai no contador certo."""
    empresas = [
        _empresa("lucro_presumido") for _ in range(5)
    ]
    chamadas = {"ok": 0, "ja": 0, "sem_dados": 0, "ne": 0, "erro": 0}

    async def gerar_fake(session, empresa, ano):  # type: ignore[no-untyped-def]
        # Distribuir: ok, ja, sem_dados, ne, erro.
        idx = empresas.index(empresa)
        if idx == 0:
            chamadas["ok"] += 1
            return
        if idx == 1:
            chamadas["ja"] += 1
            raise SpedJaGerado("já existe")
        if idx == 2:
            chamadas["sem_dados"] += 1
            raise SemDadosParaSped("sem dados")
        if idx == 3:
            chamadas["ne"] += 1
            raise EmpresaNaoElegivelEcd("regime")
        if idx == 4:
            chamadas["erro"] += 1
            raise RuntimeError("boom")

    mock_session = _patch_engine_e_empresas(empresas)
    mock_factory = MagicMock(return_value=mock_session)
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    with (
        patch(
            "app.workers.tasks.sped_gerar_anual.build_async_engine",
            return_value=mock_engine,
        ),
        patch(
            "app.workers.tasks.sped_gerar_anual.async_sessionmaker",
            return_value=mock_factory,
        ),
    ):
        resultado = await sped_gerar_anual._executar_geracao_async(
            ano_alvo=2024,
            gerar_fn=gerar_fake,
            nome_log="sped.test",
            regimes_aceitos=("lucro_presumido",),
        )

    assert resultado["empresas_ok"] == 1
    assert resultado["empresas_ja_gerada"] == 1
    assert resultado["empresas_sem_dados"] == 1
    assert resultado["empresas_nao_elegivel"] == 1
    assert resultado["empresas_erro"] == 1
    assert resultado["ano_alvo"] == 2024
    # Engine descartado mesmo com erros.
    mock_engine.dispose.assert_awaited()


@pytest.mark.asyncio
async def test_executar_geracao_sem_empresas_retorna_zeros() -> None:
    mock_session = _patch_engine_e_empresas([])
    mock_factory = MagicMock(return_value=mock_session)
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    async def gerar_nunca_chamada(session, empresa, ano):  # type: ignore[no-untyped-def]
        pytest.fail("não deveria ser chamada quando lista é vazia")

    with (
        patch(
            "app.workers.tasks.sped_gerar_anual.build_async_engine",
            return_value=mock_engine,
        ),
        patch(
            "app.workers.tasks.sped_gerar_anual.async_sessionmaker",
            return_value=mock_factory,
        ),
    ):
        resultado = await sped_gerar_anual._executar_geracao_async(
            ano_alvo=2024,
            gerar_fn=gerar_nunca_chamada,
            nome_log="sped.test",
            regimes_aceitos=("lucro_presumido",),
        )

    assert resultado["empresas_ok"] == 0
    assert resultado["empresas_erro"] == 0


@pytest.mark.asyncio
async def test_falha_em_uma_empresa_nao_aborta_demais() -> None:
    """3 empresas; a 2ª levanta exceção inesperada — as outras 2 são processadas."""
    empresas = [_empresa() for _ in range(3)]
    contagem = {"calls": 0}

    async def gerar_fake(session, empresa, ano):  # type: ignore[no-untyped-def]
        contagem["calls"] += 1
        if empresa is empresas[1]:
            raise RuntimeError("falha do meio")

    mock_session = _patch_engine_e_empresas(empresas)
    mock_factory = MagicMock(return_value=mock_session)
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    with (
        patch(
            "app.workers.tasks.sped_gerar_anual.build_async_engine",
            return_value=mock_engine,
        ),
        patch(
            "app.workers.tasks.sped_gerar_anual.async_sessionmaker",
            return_value=mock_factory,
        ),
    ):
        resultado = await sped_gerar_anual._executar_geracao_async(
            ano_alvo=2024,
            gerar_fn=gerar_fake,
            nome_log="sped.test",
            regimes_aceitos=("lucro_presumido",),
        )

    assert contagem["calls"] == 3
    assert resultado["empresas_ok"] == 2
    assert resultado["empresas_erro"] == 1
