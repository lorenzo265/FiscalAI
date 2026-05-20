"""Testes do ConciliacaoService (Sprint 7 PR3)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.conciliacao.schemas import RunConciliacaoIn, TipoMatch
from app.modules.conciliacao.service import ConciliacaoService
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    MatchJaResolvido,
    MatchNaoEncontrado,
)


def _empresa() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), cnpj="12345678000195")


def _tx(
    id_: uuid.UUID | None = None,
    valor: str = "1000.00",
    tipo: str = "CREDIT",
    data: date = date(2026, 4, 15),
    descricao: str | None = "PIX 98765432000110",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_ or uuid.uuid4(),
        valor=Decimal(valor),
        tipo=tipo,
        data_transacao=data,
        descricao=descricao,
    )


def _doc(
    id_: uuid.UUID | None = None,
    direcao: str = "saida",
    valor: str = "1000.00",
    data: date = date(2026, 4, 15),
    cnpj_dest: str | None = "98765432000110",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_ or uuid.uuid4(),
        direcao=direcao,
        valor_total=Decimal(valor),
        emitida_em=datetime(data.year, data.month, data.day),
        cnpj_emitente="12345678000195",
        cnpj_destinatario=cnpj_dest,
    )


# ── run ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_empresa_inexistente() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.conciliacao.service.EmpresaRepo", return_value=empresa_repo
    ):
        with pytest.raises(EmpresaNaoEncontrada):
            await ConciliacaoService().run(
                session, uuid.uuid4(), uuid.uuid4(), RunConciliacaoIn()
            )


@pytest.mark.asyncio
async def test_run_classifica_em_auto_e_sugerida() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    # Tx1 + doc1 → match perfeito (100). Tx2 + doc2 → ~70 (SUGERIDA).
    tx1 = _tx(valor="1000", data=date(2026, 4, 15), descricao="TED 98765432000110")
    tx2 = _tx(valor="500", data=date(2026, 4, 20), descricao="nada relevante")
    doc1 = _doc(valor="1000", data=date(2026, 4, 15), cnpj_dest="98765432000110")
    doc2 = _doc(valor="500", data=date(2026, 4, 16), cnpj_dest=None)

    repo = AsyncMock()
    repo.listar_transacoes_nao_conciliadas = AsyncMock(return_value=[tx1, tx2])
    repo.listar_documentos_candidatos = AsyncMock(return_value=[doc1, doc2])

    criados: list[dict] = []

    async def criar(**kwargs):
        criados.append(kwargs)
        return SimpleNamespace(id=uuid.uuid4())

    repo.criar_match = AsyncMock(side_effect=criar)

    with (
        patch("app.modules.conciliacao.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.conciliacao.service.ConciliacaoRepo", return_value=repo),
    ):
        out = await ConciliacaoService().run(
            session, uuid.uuid4(), empresa.id, RunConciliacaoIn()
        )

    assert out.transacoes_avaliadas == 2
    assert out.documentos_candidatos == 2
    assert out.pares_avaliados == 4  # 2 × 2
    assert out.matches_auto >= 1
    # Pelo menos um par foi classificado como AUTO
    tipos_criados = [c["tipo"] for c in criados]
    assert "AUTO" in tipos_criados


@pytest.mark.asyncio
async def test_run_ignora_pares_abaixo_do_limiar() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    # Valor divergente → score 0
    tx = _tx(valor="999999")
    doc = _doc(valor="100")

    repo = AsyncMock()
    repo.listar_transacoes_nao_conciliadas = AsyncMock(return_value=[tx])
    repo.listar_documentos_candidatos = AsyncMock(return_value=[doc])
    repo.criar_match = AsyncMock()

    with (
        patch("app.modules.conciliacao.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.conciliacao.service.ConciliacaoRepo", return_value=repo),
    ):
        out = await ConciliacaoService().run(
            session, uuid.uuid4(), empresa.id, RunConciliacaoIn()
        )

    assert out.matches_auto == 0
    assert out.matches_sugeridos == 0
    repo.criar_match.assert_not_called()


@pytest.mark.asyncio
async def test_run_idempotente_par_existente() -> None:
    """criar_match retorna None se par já existe — service não conta."""
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    tx = _tx(valor="1000", descricao="TED 98765432000110")
    doc = _doc(valor="1000", cnpj_dest="98765432000110")

    repo = AsyncMock()
    repo.listar_transacoes_nao_conciliadas = AsyncMock(return_value=[tx])
    repo.listar_documentos_candidatos = AsyncMock(return_value=[doc])
    repo.criar_match = AsyncMock(return_value=None)  # já existia

    with (
        patch("app.modules.conciliacao.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.conciliacao.service.ConciliacaoRepo", return_value=repo),
    ):
        out = await ConciliacaoService().run(
            session, uuid.uuid4(), empresa.id, RunConciliacaoIn()
        )

    assert out.matches_auto == 0
    assert out.matches_sugeridos == 0


# ── confirmar ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirmar_nao_encontrado() -> None:
    session = AsyncMock()
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.conciliacao.service.ConciliacaoRepo", return_value=repo
    ):
        with pytest.raises(MatchNaoEncontrado):
            await ConciliacaoService().confirmar(
                session, uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            )


@pytest.mark.asyncio
async def test_confirmar_match_de_outra_empresa_nao_encontrado() -> None:
    """Defesa em profundidade — RLS já bloqueia, mas verificamos no service."""
    session = AsyncMock()
    repo = AsyncMock()
    outra_empresa = uuid.uuid4()
    repo.por_id = AsyncMock(
        return_value=SimpleNamespace(empresa_id=outra_empresa, tipo="AUTO")
    )
    with patch(
        "app.modules.conciliacao.service.ConciliacaoRepo", return_value=repo
    ):
        with pytest.raises(MatchNaoEncontrado):
            await ConciliacaoService().confirmar(
                session, uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            )


@pytest.mark.asyncio
async def test_confirmar_match_rejeitado_levanta() -> None:
    session = AsyncMock()
    empresa_id = uuid.uuid4()
    match = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        tipo="REJEITADA",
        transacao_id=uuid.uuid4(),
        documento_fiscal_id=uuid.uuid4(),
        confianca=80,
        algoritmo_versao="x",
        score_breakdown_json={},
        criado_em=datetime.now(),
        confirmado_em=None,
        rejeitado_em=datetime.now(),
    )
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=match)
    with patch(
        "app.modules.conciliacao.service.ConciliacaoRepo", return_value=repo
    ):
        with pytest.raises(MatchJaResolvido):
            await ConciliacaoService().confirmar(
                session, empresa_id, match.id, uuid.uuid4()
            )


@pytest.mark.asyncio
async def test_confirmar_idempotente_em_manual() -> None:
    session = AsyncMock()
    empresa_id = uuid.uuid4()
    match = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        tipo="MANUAL",
        transacao_id=uuid.uuid4(),
        documento_fiscal_id=uuid.uuid4(),
        confianca=85,
        algoritmo_versao="conc-2026.05",
        score_breakdown_json={"criterios": ["valor_exato:+60"]},
        criado_em=datetime.now(),
        confirmado_em=datetime.now(),
        rejeitado_em=None,
    )
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=match)
    repo.marcar_confirmado = AsyncMock()
    with patch(
        "app.modules.conciliacao.service.ConciliacaoRepo", return_value=repo
    ):
        out = await ConciliacaoService().confirmar(
            session, empresa_id, match.id, uuid.uuid4()
        )
    assert out.tipo == TipoMatch.MANUAL
    repo.marcar_confirmado.assert_not_called()


@pytest.mark.asyncio
async def test_confirmar_sugerida_vira_manual() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa_id = uuid.uuid4()
    match = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        tipo="SUGERIDA",
        transacao_id=uuid.uuid4(),
        documento_fiscal_id=uuid.uuid4(),
        confianca=70,
        algoritmo_versao="conc-2026.05",
        score_breakdown_json={"criterios": ["valor_exato:+60"]},
        criado_em=datetime.now(),
        confirmado_em=None,
        rejeitado_em=None,
    )

    async def marcar(m, *, usuario_id, agora):
        m.tipo = "MANUAL"
        m.confirmado_em = agora

    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=match)
    repo.marcar_confirmado = AsyncMock(side_effect=marcar)
    with patch(
        "app.modules.conciliacao.service.ConciliacaoRepo", return_value=repo
    ):
        out = await ConciliacaoService().confirmar(
            session, empresa_id, match.id, uuid.uuid4()
        )
    assert out.tipo == TipoMatch.MANUAL
    repo.marcar_confirmado.assert_awaited_once()


# ── rejeitar ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rejeitar_manual_levanta() -> None:
    session = AsyncMock()
    empresa_id = uuid.uuid4()
    match = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        tipo="MANUAL",
        transacao_id=uuid.uuid4(),
        documento_fiscal_id=uuid.uuid4(),
        confianca=85,
        algoritmo_versao="x",
        score_breakdown_json={},
        criado_em=datetime.now(),
        confirmado_em=datetime.now(),
        rejeitado_em=None,
    )
    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=match)
    with patch(
        "app.modules.conciliacao.service.ConciliacaoRepo", return_value=repo
    ):
        with pytest.raises(MatchJaResolvido):
            await ConciliacaoService().rejeitar(
                session, empresa_id, match.id, uuid.uuid4()
            )


@pytest.mark.asyncio
async def test_rejeitar_sugerida_vira_rejeitada() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa_id = uuid.uuid4()
    match = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        tipo="SUGERIDA",
        transacao_id=uuid.uuid4(),
        documento_fiscal_id=uuid.uuid4(),
        confianca=60,
        algoritmo_versao="x",
        score_breakdown_json={},
        criado_em=datetime.now(),
        confirmado_em=None,
        rejeitado_em=None,
    )

    async def marcar(m, *, usuario_id, agora):
        m.tipo = "REJEITADA"
        m.rejeitado_em = agora

    repo = AsyncMock()
    repo.por_id = AsyncMock(return_value=match)
    repo.marcar_rejeitado = AsyncMock(side_effect=marcar)
    with patch(
        "app.modules.conciliacao.service.ConciliacaoRepo", return_value=repo
    ):
        out = await ConciliacaoService().rejeitar(
            session, empresa_id, match.id, uuid.uuid4()
        )
    assert out.tipo == TipoMatch.REJEITADA
