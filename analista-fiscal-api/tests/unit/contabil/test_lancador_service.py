"""Testes do LancadorService — orquestrador do motor automático (Sprint 9 PR2)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.contabil.lancador_auto import (
    LancamentoCandidato,
    PartidaCandidata,
)
from app.modules.contabil.lancador_service import LancadorService
from app.modules.contabil.plano_referencial import (
    CODIGOS_PADRAO_LANCAMENTO_AUTO,
    _CHAVES_CORE,
)
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    PlanoContasIncompleto,
)


def _empresa() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), cnpj="12345678000195")


def _conta_db(*, aceita: bool = True) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), aceita_lancamento=aceita)


# ── resolver_contas ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolver_contas_tudo_existe() -> None:
    session = AsyncMock()

    async def por_codigo(empresa_id, codigo, *, em=None):
        return _conta_db(aceita=True)

    repo = AsyncMock()
    repo.por_codigo = AsyncMock(side_effect=por_codigo)

    with patch(
        "app.modules.contabil.lancador_service.ContaContabilRepo",
        return_value=repo,
    ):
        contas = await LancadorService().resolver_contas(
            session, uuid.uuid4(), date(2026, 5, 1)
        )

    # resolver_contas agora itera _CHAVES_CORE (20 chaves fixas), NÃO o dict
    # inteiro — garante que contas de imposto adicionadas ao dict não quebrem
    # empresas antigas.
    assert contas.banco is not None
    assert contas.provisao_ferias is not None
    assert contas.outras_receitas is not None
    # Chamado exatamente uma vez por chave de _CHAVES_CORE.
    assert repo.por_codigo.await_count == len(_CHAVES_CORE)


@pytest.mark.asyncio
async def test_resolver_contas_faltando_levanta() -> None:
    session = AsyncMock()

    async def por_codigo(empresa_id, codigo, *, em=None):
        # Banco não existe
        if codigo == CODIGOS_PADRAO_LANCAMENTO_AUTO["banco"]:
            return None
        return _conta_db(aceita=True)

    repo = AsyncMock()
    repo.por_codigo = AsyncMock(side_effect=por_codigo)

    with patch(
        "app.modules.contabil.lancador_service.ContaContabilRepo",
        return_value=repo,
    ):
        with pytest.raises(PlanoContasIncompleto, match="banco"):
            await LancadorService().resolver_contas(
                session, uuid.uuid4(), date(2026, 5, 1)
            )


@pytest.mark.asyncio
async def test_resolver_contas_sintetica_levanta() -> None:
    """Conta existe mas é sintética (aceita_lancamento=False) → também falha."""
    session = AsyncMock()

    async def por_codigo(empresa_id, codigo, *, em=None):
        if codigo == CODIGOS_PADRAO_LANCAMENTO_AUTO["clientes"]:
            return _conta_db(aceita=False)
        return _conta_db(aceita=True)

    repo = AsyncMock()
    repo.por_codigo = AsyncMock(side_effect=por_codigo)

    with patch(
        "app.modules.contabil.lancador_service.ContaContabilRepo",
        return_value=repo,
    ):
        with pytest.raises(PlanoContasIncompleto, match="clientes"):
            await LancadorService().resolver_contas(
                session, uuid.uuid4(), date(2026, 5, 1)
            )


# ── Empresa inexistente ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lote_empresa_inexistente_levanta() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.contabil.lancador_service.EmpresaRepo",
        return_value=empresa_repo,
    ):
        with pytest.raises(EmpresaNaoEncontrada):
            await LancadorService().lote_depreciacao(
                session, uuid.uuid4(), uuid.uuid4(), date(2026, 5, 1)
            )


# ── _persistir idempotência ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persistir_idempotente_origem_existente() -> None:
    """Se já existe lançamento com origem (tipo,id), retorna False."""
    session = AsyncMock()
    origem_id = uuid.uuid4()

    candidato = LancamentoCandidato(
        historico="Teste",
        data_lancamento=date(2026, 5, 1),
        competencia=date(2026, 5, 1),
        origem_tipo="nfe",
        origem_id=origem_id,
        partidas=(
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="D", valor=Decimal("100")),
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="C", valor=Decimal("100")),
        ),
    )

    lanc_repo = AsyncMock()
    lanc_repo.por_origem = AsyncMock(
        return_value=SimpleNamespace(id=uuid.uuid4())
    )
    lanc_repo.criar = AsyncMock()
    partida_repo = AsyncMock()
    partida_repo.criar_lote = AsyncMock()

    with (
        patch(
            "app.modules.contabil.lancador_service.LancamentoRepo",
            return_value=lanc_repo,
        ),
        patch(
            "app.modules.contabil.lancador_service.PartidaRepo",
            return_value=partida_repo,
        ),
    ):
        criou = await LancadorService()._persistir(
            session, uuid.uuid4(), uuid.uuid4(), candidato
        )

    assert criou is False
    lanc_repo.criar.assert_not_called()
    partida_repo.criar_lote.assert_not_called()


@pytest.mark.asyncio
async def test_persistir_cria_lancamento_confirmado() -> None:
    session = AsyncMock()

    candidato = LancamentoCandidato(
        historico="Teste",
        data_lancamento=date(2026, 5, 1),
        competencia=date(2026, 5, 1),
        origem_tipo="depreciacao",
        origem_id=uuid.uuid4(),
        partidas=(
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="D", valor=Decimal("50")),
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="C", valor=Decimal("50")),
        ),
    )

    lanc_persistido = SimpleNamespace(id=uuid.uuid4())
    lanc_repo = AsyncMock()
    lanc_repo.por_origem = AsyncMock(return_value=None)
    lanc_repo.criar = AsyncMock(return_value=lanc_persistido)
    partida_repo = AsyncMock()
    partida_repo.criar_lote = AsyncMock()

    with (
        patch(
            "app.modules.contabil.lancador_service.LancamentoRepo",
            return_value=lanc_repo,
        ),
        patch(
            "app.modules.contabil.lancador_service.PartidaRepo",
            return_value=partida_repo,
        ),
    ):
        criou = await LancadorService()._persistir(
            session, uuid.uuid4(), uuid.uuid4(), candidato
        )

    assert criou is True
    chamada = lanc_repo.criar.await_args
    assert chamada.kwargs["status"] == "confirmado"
    assert chamada.kwargs["total_debito"] == Decimal("50")
    partida_repo.criar_lote.assert_awaited_once()
