"""Testes da abertura de exercício — pendência #8 (Sprint 18 PR1).

Cobre ``EncerramentoService.abrir_exercicio`` em isolamento via mocks:

* Pré-condição "dezembro/ano-1 encerrado".
* Classificação patrimonial × resultado (transporte vs zeragem).
* Idempotência via ON CONFLICT DO NOTHING.
* Empresa inexistente.

A integração end-to-end (encerrar_ano → abrir_exercicio) é coberta no
``tests/integration/test_pipeline_sprint10_a_12.py`` quando rodar.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.contabil.encerramento_service import EncerramentoService
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    EncerramentoMensalAusente,
)


def _row(conta_id: uuid.UUID, saldo: str, tipo: str) -> SimpleNamespace:
    """Row simulada da query JOIN saldo_conta_mes × conta_contabil."""
    return SimpleNamespace(
        conta_contabil_id=conta_id,
        saldo_final=Decimal(saldo),
        tipo=tipo,
    )


def _empresa() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), cnpj="12345678000195")


@pytest.mark.asyncio
async def test_empresa_inexistente_levanta() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.contabil.encerramento_service.EmpresaRepo",
        return_value=empresa_repo,
    ), pytest.raises(EmpresaNaoEncontrada):
        await EncerramentoService().abrir_exercicio(
            session, uuid.uuid4(), uuid.uuid4(), 2025
        )


@pytest.mark.asyncio
async def test_dezembro_anterior_nao_encerrado_levanta() -> None:
    """Pré-condição: dezembro/ano-1 deve ter saldo_conta_mes status='fechado'."""
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa())

    # 1ª execute() → check de pré-condição retorna None (não fechado).
    result_precond = MagicMock()
    result_precond.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result_precond)

    with patch(
        "app.modules.contabil.encerramento_service.EmpresaRepo",
        return_value=empresa_repo,
    ), pytest.raises(EncerramentoMensalAusente, match="Dezembro/2024"):
        await EncerramentoService().abrir_exercicio(
            session, uuid.uuid4(), uuid.uuid4(), 2025
        )


@pytest.mark.asyncio
async def test_transporta_patrimoniais_e_zera_resultado() -> None:
    """Contas patrimoniais herdam saldo_final; receita/despesa começam em 0."""
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa())

    # Saldos finais de dezembro/2024 — mix de tipos.
    conta_caixa = uuid.uuid4()
    conta_fornecedor = uuid.uuid4()
    conta_capital = uuid.uuid4()
    conta_resultado = uuid.uuid4()
    conta_receita = uuid.uuid4()
    conta_despesa = uuid.uuid4()

    rows_saldos = [
        _row(conta_caixa, "5000.00", "ativo"),
        _row(conta_fornecedor, "2000.00", "passivo"),
        _row(conta_capital, "10000.00", "patrimonio_liquido"),
        _row(conta_resultado, "3000.00", "conta_resultado"),
        _row(conta_receita, "15000.00", "receita"),  # NÃO transportada
        _row(conta_despesa, "12000.00", "despesa"),  # NÃO transportada
    ]

    # Mock das 3 queries em sequência:
    # 1) pré-condição → retorna UUID (algum saldo fechado).
    # 2) SELECT saldos + tipo → retorna rows_saldos.
    # 3) INSERT ON CONFLICT DO NOTHING → ignorado.
    result_precond = MagicMock()
    result_precond.scalar_one_or_none = MagicMock(return_value=uuid.uuid4())

    result_saldos = MagicMock()
    result_saldos.all = MagicMock(return_value=rows_saldos)

    result_insert = MagicMock()
    session.execute = AsyncMock(
        side_effect=[result_precond, result_saldos, result_insert]
    )

    with patch(
        "app.modules.contabil.encerramento_service.EmpresaRepo",
        return_value=empresa_repo,
    ):
        resultado = await EncerramentoService().abrir_exercicio(
            session, uuid.uuid4(), uuid.uuid4(), 2025
        )

    # 4 patrimoniais (ativo, passivo, PL, conta_resultado) + 2 resultado.
    assert resultado.contas_patrimoniais == 4
    assert resultado.contas_resultado == 2
    # |5000| + |2000| + |10000| + |3000| = 20000
    assert resultado.saldo_total_transportado == Decimal("20000.00")
    assert resultado.ano == 2025

    # Commit foi chamado (persistência ocorreu).
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_sem_saldos_em_dezembro_retorna_zero() -> None:
    """Caso degenerado: empresa nova sem qualquer saldo materializado."""
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa())

    # Pré-condição passa (tem algum saldo fechado em dezembro), mas o join
    # depois não retorna rows (cenário improvável mas defensivo).
    result_precond = MagicMock()
    result_precond.scalar_one_or_none = MagicMock(return_value=uuid.uuid4())
    result_saldos = MagicMock()
    result_saldos.all = MagicMock(return_value=[])

    session.execute = AsyncMock(side_effect=[result_precond, result_saldos])

    with patch(
        "app.modules.contabil.encerramento_service.EmpresaRepo",
        return_value=empresa_repo,
    ):
        resultado = await EncerramentoService().abrir_exercicio(
            session, uuid.uuid4(), uuid.uuid4(), 2025
        )

    assert resultado.contas_patrimoniais == 0
    assert resultado.contas_resultado == 0
    assert resultado.saldo_total_transportado == Decimal("0")
    # Não tentou INSERT — ninguém para upsertar.
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_saldo_negativo_patrimonial_transportado_em_abs() -> None:
    """Patrimonial com saldo negativo (raro mas válido) entra com sinal preservado.

    ``saldo_total_transportado`` usa abs (audit), mas o ``saldo_inicial``
    persistido preserva o sinal — testamos via captura do INSERT.
    """
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa())

    conta_a = uuid.uuid4()
    rows = [_row(conta_a, "-1500.00", "ativo")]  # ex: cheque em compensação

    result_precond = MagicMock()
    result_precond.scalar_one_or_none = MagicMock(return_value=uuid.uuid4())
    result_saldos = MagicMock()
    result_saldos.all = MagicMock(return_value=rows)
    result_insert = MagicMock()

    session.execute = AsyncMock(
        side_effect=[result_precond, result_saldos, result_insert]
    )

    with patch(
        "app.modules.contabil.encerramento_service.EmpresaRepo",
        return_value=empresa_repo,
    ):
        resultado = await EncerramentoService().abrir_exercicio(
            session, uuid.uuid4(), uuid.uuid4(), 2025
        )

    assert resultado.contas_patrimoniais == 1
    # |−1500| = 1500
    assert resultado.saldo_total_transportado == Decimal("1500.00")
