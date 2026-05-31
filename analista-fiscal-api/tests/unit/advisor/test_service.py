"""Testes do AdvisorService — orquestração + idempotência (Sprint 15 PR1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.modules.advisor.calcula_anomalias import (
    AnomaliaDetectada,
    MetodoDeteccao,
    PontoApuracao,
    SeveridadeAnomalia,
    TipoTributoAnomalia,
)
from app.modules.advisor.service import AdvisorService
from app.shared.exceptions import (
    AnomaliaJaDispensada,
    AnomaliaNaoEncontrada,
    EmpresaNaoEncontrada,
)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


def _empresa() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4())


def _anomalia_ok() -> AnomaliaDetectada:
    return AnomaliaDetectada(
        tipo=TipoTributoAnomalia.PIS,
        competencia=date(2026, 5, 1),
        valor_observado=Decimal("3000.00"),
        valor_esperado=Decimal("1000.00"),
        z_score=Decimal("4.250"),
        delta_percentual=Decimal("2.0000"),
        severidade=SeveridadeAnomalia.ALTA,
        metodo=MetodoDeteccao.ZSCORE,
        amostra_n=7,
        mensagem="PIS subiu 200% (de R$ 1.000,00 para R$ 3.000,00).",
    )


def _serie_simples() -> list[PontoApuracao]:
    return [
        PontoApuracao(competencia=date(2025, m, 1), valor=Decimal("1000"))
        for m in range(1, 8)
    ] + [PontoApuracao(competencia=date(2025, 8, 1), valor=Decimal("3000"))]


# ── redetectar_empresa ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_redetectar_empresa_nao_encontrada() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo
    ):
        with pytest.raises(EmpresaNaoEncontrada):
            await AdvisorService(session).redetectar_empresa(uuid.uuid4())


@pytest.mark.asyncio
async def test_redetectar_empresa_sem_apuracoes_retorna_zero() -> None:
    """Empresa nova sem apurações em nenhum tipo → 0 anomalias, sem erro."""
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    serie_repo = AsyncMock()
    serie_repo.serie_por_tipo = AsyncMock(return_value=[])
    anomalia_repo = AsyncMock()
    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.ApuracaoSerieRepo", return_value=serie_repo),
        patch(
            "app.modules.advisor.service.AnomaliaFiscalRepo",
            return_value=anomalia_repo,
        ),
    ):
        resultado = await AdvisorService(session).redetectar_empresa(empresa.id)
    assert resultado.anomalias_registradas == 0
    assert resultado.tipos_analisados == 7  # 7 tipos no enum
    anomalia_repo.registrar_ou_atualizar.assert_not_awaited()


@pytest.mark.asyncio
async def test_redetectar_empresa_registra_anomalia_quando_detecta() -> None:
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    serie_repo = AsyncMock()
    # Só tipo PIS tem série; os outros são vazios.
    serie_repo.serie_por_tipo = AsyncMock(
        side_effect=lambda *_a, **k: _serie_simples()
        if _a[1] is TipoTributoAnomalia.PIS
        else []
    )
    anomalia_repo = AsyncMock()
    anomalia_repo.registrar_ou_atualizar = AsyncMock(
        return_value=(SimpleNamespace(id=uuid.uuid4()), True)
    )
    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.ApuracaoSerieRepo", return_value=serie_repo),
        patch(
            "app.modules.advisor.service.AnomaliaFiscalRepo",
            return_value=anomalia_repo,
        ),
    ):
        resultado = await AdvisorService(session).redetectar_empresa(empresa.id)
    assert resultado.anomalias_registradas == 1
    anomalia_repo.registrar_ou_atualizar.assert_awaited_once()


@pytest.mark.asyncio
async def test_redetectar_empresa_idempotente_quando_mesmo_valor() -> None:
    """Repo devolve criou=False → service NÃO conta como registrada (§8.9)."""
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    serie_repo = AsyncMock()
    serie_repo.serie_por_tipo = AsyncMock(
        side_effect=lambda *_a, **k: _serie_simples()
        if _a[1] is TipoTributoAnomalia.COFINS
        else []
    )
    anomalia_repo = AsyncMock()
    anomalia_repo.registrar_ou_atualizar = AsyncMock(
        return_value=(SimpleNamespace(id=uuid.uuid4()), False)
    )
    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.ApuracaoSerieRepo", return_value=serie_repo),
        patch(
            "app.modules.advisor.service.AnomaliaFiscalRepo",
            return_value=anomalia_repo,
        ),
    ):
        resultado = await AdvisorService(session).redetectar_empresa(empresa.id)
    assert resultado.anomalias_registradas == 0


# ── listar_abertas ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_listar_abertas_devolve_lista_do_repo() -> None:
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    anomalia_repo = AsyncMock()
    mock_anomalias = [SimpleNamespace(id=uuid.uuid4()) for _ in range(3)]
    anomalia_repo.listar_abertas = AsyncMock(return_value=mock_anomalias)
    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.advisor.service.AnomaliaFiscalRepo",
            return_value=anomalia_repo,
        ),
    ):
        result = await AdvisorService(session).listar_abertas(empresa.id)
    assert result == mock_anomalias
    anomalia_repo.listar_abertas.assert_awaited_once_with(empresa.id, limit=100)


@pytest.mark.asyncio
async def test_listar_abertas_empresa_nao_encontrada() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo
    ):
        with pytest.raises(EmpresaNaoEncontrada):
            await AdvisorService(session).listar_abertas(uuid.uuid4())


# ── dispensar ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispensar_anomalia_aberta_marca_dispensada() -> None:
    empresa_id = uuid.uuid4()
    usuario_id = uuid.uuid4()
    aberta = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        superseded_by=None,
        dispensada_em=None,
        dispensada_por=None,
        motivo_dispensa=None,
    )
    session = AsyncMock()
    anomalia_repo = AsyncMock()
    anomalia_repo.por_id = AsyncMock(return_value=aberta)
    anomalia_repo.dispensar = AsyncMock(return_value=aberta)
    with patch(
        "app.modules.advisor.service.AnomaliaFiscalRepo",
        return_value=anomalia_repo,
    ):
        await AdvisorService(session).dispensar(
            empresa_id,
            aberta.id,
            dispensada_por=usuario_id,
            motivo="Valor já validado com o contador",
        )
    anomalia_repo.dispensar.assert_awaited_once()
    kwargs = anomalia_repo.dispensar.call_args.kwargs
    assert kwargs["dispensada_por"] == usuario_id
    assert kwargs["motivo"] == "Valor já validado com o contador"


@pytest.mark.asyncio
async def test_dispensar_anomalia_inexistente_levanta_404() -> None:
    session = AsyncMock()
    anomalia_repo = AsyncMock()
    anomalia_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.advisor.service.AnomaliaFiscalRepo",
        return_value=anomalia_repo,
    ):
        with pytest.raises(AnomaliaNaoEncontrada):
            await AdvisorService(session).dispensar(
                uuid.uuid4(),
                uuid.uuid4(),
                dispensada_por=uuid.uuid4(),
                motivo="x",
            )


@pytest.mark.asyncio
async def test_dispensar_anomalia_de_outra_empresa_404() -> None:
    """Cross-empresa: defesa em profundidade além do RLS."""
    aberta = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=uuid.uuid4(),  # empresa diferente da requisitada
        superseded_by=None,
        dispensada_em=None,
    )
    session = AsyncMock()
    anomalia_repo = AsyncMock()
    anomalia_repo.por_id = AsyncMock(return_value=aberta)
    with patch(
        "app.modules.advisor.service.AnomaliaFiscalRepo",
        return_value=anomalia_repo,
    ):
        with pytest.raises(AnomaliaNaoEncontrada):
            await AdvisorService(session).dispensar(
                uuid.uuid4(),  # empresa diferente
                aberta.id,
                dispensada_por=uuid.uuid4(),
                motivo="x",
            )


@pytest.mark.asyncio
async def test_dispensar_anomalia_ja_superada_404() -> None:
    empresa_id = uuid.uuid4()
    superada = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        superseded_by=uuid.uuid4(),
        dispensada_em=None,
    )
    session = AsyncMock()
    anomalia_repo = AsyncMock()
    anomalia_repo.por_id = AsyncMock(return_value=superada)
    with patch(
        "app.modules.advisor.service.AnomaliaFiscalRepo",
        return_value=anomalia_repo,
    ):
        with pytest.raises(AnomaliaNaoEncontrada):
            await AdvisorService(session).dispensar(
                empresa_id,
                superada.id,
                dispensada_por=uuid.uuid4(),
                motivo="x",
            )


@pytest.mark.asyncio
async def test_dispensar_anomalia_ja_dispensada_409() -> None:
    """Segunda dispensa → 409 AnomaliaJaDispensada (idempotência exposta)."""
    empresa_id = uuid.uuid4()
    ja_disp = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        superseded_by=None,
        dispensada_em=datetime.now(_TZ_BR),
    )
    session = AsyncMock()
    anomalia_repo = AsyncMock()
    anomalia_repo.por_id = AsyncMock(return_value=ja_disp)
    with patch(
        "app.modules.advisor.service.AnomaliaFiscalRepo",
        return_value=anomalia_repo,
    ):
        with pytest.raises(AnomaliaJaDispensada):
            await AdvisorService(session).dispensar(
                empresa_id,
                ja_disp.id,
                dispensada_por=uuid.uuid4(),
                motivo="x",
            )
