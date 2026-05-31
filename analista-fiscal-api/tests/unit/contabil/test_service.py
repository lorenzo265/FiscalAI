"""Testes do ContabilService (Sprint 9 PR1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.contabil.schemas import (
    CriarContaIn,
    CriarLancamentoIn,
    NaturezaConta,
    PartidaIn,
    StatusLancamento,
    TipoConta,
)
from app.modules.contabil.service import ContabilService
from app.shared.exceptions import (
    ContaJaExiste,
    EmpresaNaoEncontrada,
    LancamentoEmMesEncerrado,
    LancamentoInvalido,
    LancamentoJaConfirmado,
    LancamentoNaoEncontrado,
)


def _empresa() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), cnpj="12345678000195")


def _conta_db(
    empresa_id: uuid.UUID,
    *,
    aceita: bool = True,
    valid_from: date = date(2025, 1, 1),
    valid_to: date | None = None,
    codigo: str = "1.1.1.01",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codigo=codigo,
        descricao="Conta teste",
        parent_id=None,
        natureza="D",
        tipo="ativo",
        nivel=4,
        aceita_lancamento=aceita,
        codigo_ecd_referencial=None,
        valid_from=valid_from,
        valid_to=valid_to,
    )


# ── criar_conta ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_criar_conta_empresa_inexistente() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.contabil.service.EmpresaRepo", return_value=empresa_repo
    ):
        with pytest.raises(EmpresaNaoEncontrada):
            await ContabilService().criar_conta(
                session,
                uuid.uuid4(),
                uuid.uuid4(),
                CriarContaIn(
                    codigo="1.1",
                    descricao="Conta",
                    natureza=NaturezaConta.DEBITO,
                    tipo=TipoConta.ATIVO,
                    nivel=2,
                    valid_from=date(2026, 1, 1),
                ),
            )


@pytest.mark.asyncio
async def test_criar_conta_codigo_duplicado_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    repo = AsyncMock()
    repo.por_codigo = AsyncMock(return_value=_conta_db(empresa.id))

    with (
        patch("app.modules.contabil.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.contabil.service.ContaContabilRepo", return_value=repo),
    ):
        with pytest.raises(ContaJaExiste):
            await ContabilService().criar_conta(
                session,
                uuid.uuid4(),
                empresa.id,
                CriarContaIn(
                    codigo="1.1.1.01",
                    descricao="Caixa",
                    natureza=NaturezaConta.DEBITO,
                    tipo=TipoConta.ATIVO,
                    nivel=4,
                    aceita_lancamento=True,
                    valid_from=date(2026, 1, 1),
                ),
            )


@pytest.mark.asyncio
async def test_criar_conta_sucesso() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    repo = AsyncMock()
    repo.por_codigo = AsyncMock(return_value=None)
    conta_criada = _conta_db(empresa.id, codigo="1.2.3")
    repo.criar = AsyncMock(return_value=conta_criada)

    with (
        patch("app.modules.contabil.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.contabil.service.ContaContabilRepo", return_value=repo),
    ):
        out = await ContabilService().criar_conta(
            session,
            uuid.uuid4(),
            empresa.id,
            CriarContaIn(
                codigo="1.2.3",
                descricao="Imobilizado",
                natureza=NaturezaConta.DEBITO,
                tipo=TipoConta.ATIVO,
                nivel=3,
                valid_from=date(2026, 1, 1),
            ),
        )

    assert out.codigo == "1.2.3"
    repo.criar.assert_awaited_once()


# ── clonar_plano_referencial ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clonar_plano_cria_todas_as_contas() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    from app.modules.contabil.plano_referencial import PLANO_REFERENCIAL

    criadas: list[dict[str, object]] = []

    async def por_codigo(empresa_id: uuid.UUID, codigo: str, *, em: date | None = None):
        return None

    async def criar(**kwargs):
        criadas.append(kwargs)
        return _conta_db(empresa.id, codigo=kwargs["codigo"])

    repo = AsyncMock()
    repo.por_codigo = AsyncMock(side_effect=por_codigo)
    repo.criar = AsyncMock(side_effect=criar)

    with (
        patch("app.modules.contabil.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.contabil.service.ContaContabilRepo", return_value=repo),
    ):
        out = await ContabilService().clonar_plano_referencial(
            session, uuid.uuid4(), empresa.id, date(2026, 1, 1)
        )

    assert out.contas_criadas == len(PLANO_REFERENCIAL)
    assert out.contas_existentes == 0
    # Verifica que parent_id foi resolvido para contas filhas
    chamada_caixa = next(c for c in criadas if c["codigo"] == "1.1.1.01")
    assert chamada_caixa["parent_id"] is not None


@pytest.mark.asyncio
async def test_clonar_plano_idempotente() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    from app.modules.contabil.plano_referencial import PLANO_REFERENCIAL

    # Tudo já existe
    async def por_codigo(empresa_id: uuid.UUID, codigo: str, *, em: date | None = None):
        return _conta_db(empresa.id, codigo=codigo)

    repo = AsyncMock()
    repo.por_codigo = AsyncMock(side_effect=por_codigo)
    repo.criar = AsyncMock()

    with (
        patch("app.modules.contabil.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.contabil.service.ContaContabilRepo", return_value=repo),
    ):
        out = await ContabilService().clonar_plano_referencial(
            session, uuid.uuid4(), empresa.id, date(2026, 1, 1)
        )

    assert out.contas_criadas == 0
    assert out.contas_existentes == len(PLANO_REFERENCIAL)
    repo.criar.assert_not_called()


# ── criar_lancamento_manual ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_criar_lancamento_partidas_invalidas_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    c1 = _conta_db(empresa.id)
    c2 = _conta_db(empresa.id)

    conta_repo = AsyncMock()
    conta_repo.carregar_para_validacao = AsyncMock(
        return_value={c1.id: c1, c2.id: c2}
    )

    saldo_repo = AsyncMock()
    saldo_repo.competencia_encerrada = AsyncMock(return_value=False)

    with (
        patch("app.modules.contabil.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.contabil.service.ContaContabilRepo", return_value=conta_repo
        ),
        patch(
            "app.modules.contabil.service.SaldoContaMesRepo", return_value=saldo_repo
        ),
    ):
        with pytest.raises(LancamentoInvalido, match="desbalanceadas"):
            await ContabilService().criar_lancamento_manual(
                session,
                uuid.uuid4(),
                empresa.id,
                CriarLancamentoIn(
                    data_lancamento=date(2026, 5, 15),
                    competencia=date(2026, 5, 1),
                    historico="Teste",
                    partidas=[
                        PartidaIn(conta_id=c1.id, tipo=NaturezaConta.DEBITO, valor=Decimal("100")),
                        PartidaIn(conta_id=c2.id, tipo=NaturezaConta.CREDITO, valor=Decimal("90")),
                    ],
                ),
            )


@pytest.mark.asyncio
async def test_criar_lancamento_sucesso_persiste_partidas() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    c1 = _conta_db(empresa.id)
    c2 = _conta_db(empresa.id)

    conta_repo = AsyncMock()
    conta_repo.carregar_para_validacao = AsyncMock(
        return_value={c1.id: c1, c2.id: c2}
    )

    lanc_persistido = SimpleNamespace(
        id=uuid.uuid4(),
        data_lancamento=date(2026, 5, 15),
        competencia=date(2026, 5, 1),
        historico="Pagamento fornecedor",
        origem_tipo="manual",
        origem_id=None,
        total_debito=Decimal("100"),
        total_credito=Decimal("100"),
        status="rascunho",
        criado_em=datetime.now(),
    )
    lanc_repo = AsyncMock()
    lanc_repo.criar = AsyncMock(return_value=lanc_persistido)

    partida_repo = AsyncMock()
    partida_repo.criar_lote = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=uuid.uuid4(),
                conta_contabil_id=c1.id,
                tipo="D",
                valor=Decimal("100"),
                ordem=1,
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                conta_contabil_id=c2.id,
                tipo="C",
                valor=Decimal("100"),
                ordem=2,
            ),
        ]
    )

    saldo_repo = AsyncMock()
    saldo_repo.competencia_encerrada = AsyncMock(return_value=False)

    with (
        patch("app.modules.contabil.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.contabil.service.ContaContabilRepo", return_value=conta_repo
        ),
        patch("app.modules.contabil.service.LancamentoRepo", return_value=lanc_repo),
        patch("app.modules.contabil.service.PartidaRepo", return_value=partida_repo),
        patch(
            "app.modules.contabil.service.SaldoContaMesRepo", return_value=saldo_repo
        ),
    ):
        out = await ContabilService().criar_lancamento_manual(
            session,
            uuid.uuid4(),
            empresa.id,
            CriarLancamentoIn(
                data_lancamento=date(2026, 5, 15),
                competencia=date(2026, 5, 1),
                historico="Pagamento fornecedor",
                partidas=[
                    PartidaIn(conta_id=c1.id, tipo=NaturezaConta.DEBITO, valor=Decimal("100")),
                    PartidaIn(conta_id=c2.id, tipo=NaturezaConta.CREDITO, valor=Decimal("100")),
                ],
            ),
        )

    assert out.status == StatusLancamento.RASCUNHO
    assert out.total_debito == Decimal("100")
    assert len(out.partidas) == 2
    lanc_repo.criar.assert_awaited_once()
    partida_repo.criar_lote.assert_awaited_once()


# ── confirmar_lancamento ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirmar_nao_encontrado() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=None)
    with patch("app.modules.contabil.service.LancamentoRepo", return_value=repo):
        with pytest.raises(LancamentoNaoEncontrado):
            await ContabilService().confirmar_lancamento(
                session, uuid.uuid4(), uuid.uuid4()
            )


@pytest.mark.asyncio
async def test_confirmar_outra_empresa_nao_encontrado() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_id = AsyncMock(
        return_value=SimpleNamespace(empresa_id=uuid.uuid4(), status="rascunho")
    )
    with patch("app.modules.contabil.service.LancamentoRepo", return_value=repo):
        with pytest.raises(LancamentoNaoEncontrado):
            await ContabilService().confirmar_lancamento(
                session, uuid.uuid4(), uuid.uuid4()
            )


@pytest.mark.asyncio
async def test_confirmar_encerrado_levanta() -> None:
    session = AsyncMock()
    empresa_id = uuid.uuid4()
    repo = AsyncMock()
    repo.por_id = AsyncMock(
        return_value=SimpleNamespace(empresa_id=empresa_id, status="encerrado")
    )
    with patch("app.modules.contabil.service.LancamentoRepo", return_value=repo):
        with pytest.raises(LancamentoJaConfirmado):
            await ContabilService().confirmar_lancamento(
                session, empresa_id, uuid.uuid4()
            )


@pytest.mark.asyncio
async def test_confirmar_ja_confirmado_idempotente() -> None:
    session = AsyncMock()
    empresa_id = uuid.uuid4()
    lanc = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        data_lancamento=date(2026, 5, 15),
        competencia=date(2026, 5, 1),
        historico="X",
        origem_tipo="manual",
        origem_id=None,
        total_debito=Decimal("100"),
        total_credito=Decimal("100"),
        status="confirmado",
        criado_em=datetime.now(),
    )
    lanc_repo = AsyncMock()
    lanc_repo.por_id = AsyncMock(return_value=lanc)
    lanc_repo.confirmar = AsyncMock()
    partida_repo = AsyncMock()
    partida_repo.por_lancamento = AsyncMock(return_value=[])
    saldo_repo = AsyncMock()
    saldo_repo.competencia_encerrada = AsyncMock(return_value=False)

    with (
        patch("app.modules.contabil.service.LancamentoRepo", return_value=lanc_repo),
        patch("app.modules.contabil.service.PartidaRepo", return_value=partida_repo),
        patch(
            "app.modules.contabil.service.SaldoContaMesRepo", return_value=saldo_repo
        ),
    ):
        out = await ContabilService().confirmar_lancamento(
            session, empresa_id, lanc.id
        )

    assert out.status == StatusLancamento.CONFIRMADO
    lanc_repo.confirmar.assert_not_called()


@pytest.mark.asyncio
async def test_confirmar_rascunho_vira_confirmado() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa_id = uuid.uuid4()
    lanc = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        data_lancamento=date(2026, 5, 15),
        competencia=date(2026, 5, 1),
        historico="X",
        origem_tipo="manual",
        origem_id=None,
        total_debito=Decimal("100"),
        total_credito=Decimal("100"),
        status="rascunho",
        criado_em=datetime.now(),
    )

    async def confirmar(l):
        l.status = "confirmado"

    lanc_repo = AsyncMock()
    lanc_repo.por_id = AsyncMock(return_value=lanc)
    lanc_repo.confirmar = AsyncMock(side_effect=confirmar)
    partida_repo = AsyncMock()
    partida_repo.por_lancamento = AsyncMock(return_value=[])
    saldo_repo = AsyncMock()
    saldo_repo.competencia_encerrada = AsyncMock(return_value=False)

    with (
        patch("app.modules.contabil.service.LancamentoRepo", return_value=lanc_repo),
        patch("app.modules.contabil.service.PartidaRepo", return_value=partida_repo),
        patch(
            "app.modules.contabil.service.SaldoContaMesRepo", return_value=saldo_repo
        ),
    ):
        out = await ContabilService().confirmar_lancamento(
            session, empresa_id, lanc.id
        )

    assert out.status == StatusLancamento.CONFIRMADO
    lanc_repo.confirmar.assert_awaited_once()


# ── Bloqueio de lançamento em mês encerrado (Fase 2 PR10) ────────────────────


@pytest.mark.asyncio
async def test_criar_lancamento_em_mes_encerrado_bloqueia() -> None:
    """§8.2 — defesa em profundidade: service barra antes do DB CHECK."""
    session = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    saldo_repo = AsyncMock()
    saldo_repo.competencia_encerrada = AsyncMock(return_value=True)

    with (
        patch("app.modules.contabil.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.contabil.service.SaldoContaMesRepo", return_value=saldo_repo
        ),
    ):
        with pytest.raises(LancamentoEmMesEncerrado, match="encerrada"):
            await ContabilService().criar_lancamento_manual(
                session,
                uuid.uuid4(),
                empresa.id,
                CriarLancamentoIn(
                    data_lancamento=date(2026, 5, 15),
                    competencia=date(2026, 5, 1),
                    historico="Tentativa retroativa",
                    partidas=[
                        PartidaIn(
                            conta_id=uuid.uuid4(),
                            tipo=NaturezaConta.DEBITO,
                            valor=Decimal("100"),
                        ),
                        PartidaIn(
                            conta_id=uuid.uuid4(),
                            tipo=NaturezaConta.CREDITO,
                            valor=Decimal("100"),
                        ),
                    ],
                ),
            )

    # Guard checa ANTES de validar partidas — não vai ao DB de contas.
    saldo_repo.competencia_encerrada.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirmar_rascunho_em_mes_encerrado_bloqueia() -> None:
    """Rascunho pré-existente não pode ser promovido após encerramento."""
    session = AsyncMock()
    empresa_id = uuid.uuid4()
    lanc = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        data_lancamento=date(2026, 5, 15),
        competencia=date(2026, 5, 1),
        historico="X",
        origem_tipo="manual",
        origem_id=None,
        total_debito=Decimal("100"),
        total_credito=Decimal("100"),
        status="rascunho",
        criado_em=datetime.now(),
    )
    lanc_repo = AsyncMock()
    lanc_repo.por_id = AsyncMock(return_value=lanc)
    lanc_repo.confirmar = AsyncMock()
    saldo_repo = AsyncMock()
    saldo_repo.competencia_encerrada = AsyncMock(return_value=True)

    with (
        patch("app.modules.contabil.service.LancamentoRepo", return_value=lanc_repo),
        patch(
            "app.modules.contabil.service.SaldoContaMesRepo", return_value=saldo_repo
        ),
    ):
        with pytest.raises(LancamentoEmMesEncerrado, match="rascunho"):
            await ContabilService().confirmar_lancamento(
                session, empresa_id, lanc.id
            )

    lanc_repo.confirmar.assert_not_called()
