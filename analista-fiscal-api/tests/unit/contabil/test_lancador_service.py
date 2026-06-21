"""Testes do LancadorService — orquestrador do motor automático (Sprint 9 PR2).

FA achado #6 (2026-06-21): validação de partidas dobradas em _persistir.
Lei 6.404 art. 177 / NBC TG — Σ D == Σ C; todo valor de partida > 0.
"""

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
    LancamentoInvalido,
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


# ── Achado #6 — validação partidas dobradas em _persistir ──────────────────
# Lei 6.404 art. 177 / NBC TG + §8.4 do projeto.
# _persistir DEVE rejeitar candidatos desbalanceados ou com valores <= 0
# antes de qualquer I/O no banco.


def _candidato_balanceado() -> LancamentoCandidato:
    """Candidato válido: D=100 C=100."""
    return LancamentoCandidato(
        historico="Folha 2026-05",
        data_lancamento=date(2026, 5, 1),
        competencia=date(2026, 5, 1),
        origem_tipo="folha",
        origem_id=uuid.uuid4(),
        partidas=(
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="D", valor=Decimal("100")),
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="C", valor=Decimal("100")),
        ),
    )


def _candidato_desbalanceado() -> LancamentoCandidato:
    """Candidato inválido: D=100 C=90 → desbalanceado."""
    return LancamentoCandidato(
        historico="Folha corrompida",
        data_lancamento=date(2026, 5, 1),
        competencia=date(2026, 5, 1),
        origem_tipo="folha",
        origem_id=uuid.uuid4(),
        partidas=(
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="D", valor=Decimal("100")),
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="C", valor=Decimal("90")),
        ),
    )


def _candidato_valor_zero() -> LancamentoCandidato:
    """Candidato inválido: partida com valor=0."""
    return LancamentoCandidato(
        historico="IRRF sem desconto",
        data_lancamento=date(2026, 5, 1),
        competencia=date(2026, 5, 1),
        origem_tipo="folha",
        origem_id=uuid.uuid4(),
        partidas=(
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="D", valor=Decimal("500")),
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="C", valor=Decimal("500")),
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="C", valor=Decimal("0")),
        ),
    )


def _candidato_valor_negativo() -> LancamentoCandidato:
    """Candidato inválido: partida com valor negativo (folha com líquido negativo)."""
    return LancamentoCandidato(
        historico="Folha com líquido negativo",
        data_lancamento=date(2026, 5, 1),
        competencia=date(2026, 5, 1),
        origem_tipo="folha",
        origem_id=uuid.uuid4(),
        partidas=(
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="D", valor=Decimal("1000")),
            PartidaCandidata(
                conta_id=uuid.uuid4(), tipo="C", valor=Decimal("-200")
            ),  # líquido negativo
            PartidaCandidata(conta_id=uuid.uuid4(), tipo="C", valor=Decimal("1200")),
        ),
    )


@pytest.mark.asyncio
async def test_persistir_candidato_desbalanceado_levanta() -> None:
    """Candidato D≠C → LancamentoInvalido ANTES de qualquer I/O.

    Por que é borda: conversor puro (lancador_auto) bem escrito nunca gera
    desbalanceamento; mas regressão de código ou alteração futura pode.
    Esta trava captura a inconsistência sem deixar gravar dado inválido.

    Input:  D=100 / C=90 (diferença R$10)
    Esperado: raise LancamentoInvalido com "partidas_desbalanceadas"
    """
    session = AsyncMock()
    candidato = _candidato_desbalanceado()
    lanc_repo = AsyncMock()
    lanc_repo.por_origem = AsyncMock(return_value=None)

    with (
        patch(
            "app.modules.contabil.lancador_service.LancamentoRepo",
            return_value=lanc_repo,
        ),
        pytest.raises(LancamentoInvalido, match="partidas_desbalanceadas"),
    ):
        await LancadorService()._persistir(
            session, uuid.uuid4(), uuid.uuid4(), candidato
        )

    # Banco NÃO deve ter sido tocado.
    lanc_repo.criar.assert_not_called()


@pytest.mark.asyncio
async def test_persistir_candidato_valor_zero_levanta() -> None:
    """Partida com valor=0 → LancamentoInvalido.

    Por que é borda: folha sem IRRF geraria partida valor=0 para
    'IRRF Funcionários a Recolher' se o conversor não filtrar — quebra
    partida dobrada (valor não positivo).

    Input:  D=500 / C=500 / C=0
    Esperado: raise LancamentoInvalido com "_valor_nao_positivo"
    """
    session = AsyncMock()
    candidato = _candidato_valor_zero()
    lanc_repo = AsyncMock()
    lanc_repo.por_origem = AsyncMock(return_value=None)

    with (
        patch(
            "app.modules.contabil.lancador_service.LancamentoRepo",
            return_value=lanc_repo,
        ),
        pytest.raises(LancamentoInvalido, match="_valor_nao_positivo"),
    ):
        await LancadorService()._persistir(
            session, uuid.uuid4(), uuid.uuid4(), candidato
        )

    lanc_repo.criar.assert_not_called()


@pytest.mark.asyncio
async def test_persistir_candidato_valor_negativo_levanta() -> None:
    """Partida com valor negativo (líquido negativo da folha) → LancamentoInvalido.

    Por que é borda: folha onde INSS + IRRF > salário bruto (raro mas possível
    em folha retroativa com desconto judicial) geraria `liquido_pagar` negativo
    no conversor. Sem esta trava, gravaria crédito negativo — viola integridade.

    Input:  D=1000 / C=-200 / C=1200
    Esperado: raise LancamentoInvalido com "_valor_nao_positivo"
    """
    session = AsyncMock()
    candidato = _candidato_valor_negativo()
    lanc_repo = AsyncMock()
    lanc_repo.por_origem = AsyncMock(return_value=None)

    with (
        patch(
            "app.modules.contabil.lancador_service.LancamentoRepo",
            return_value=lanc_repo,
        ),
        pytest.raises(LancamentoInvalido, match="_valor_nao_positivo"),
    ):
        await LancadorService()._persistir(
            session, uuid.uuid4(), uuid.uuid4(), candidato
        )

    lanc_repo.criar.assert_not_called()


@pytest.mark.asyncio
async def test_persistir_candidato_balanceado_persiste_normalmente() -> None:
    """Candidato válido (D==C, valores > 0) persiste e retorna True.

    Por que é borda: garante que a nova validação NÃO bloqueia o caminho
    feliz — regressão na trava quebraria todos os lotes automáticos.

    Input:  D=100 / C=100 (balanceado, valores positivos)
    Esperado: True (criado), total_debito == 100 passado ao criar()
    """
    session = AsyncMock()
    candidato = _candidato_balanceado()
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
    assert chamada.kwargs["total_debito"] == Decimal("100")
    assert chamada.kwargs["total_credito"] == Decimal("100")
    partida_repo.criar_lote.assert_awaited_once()
