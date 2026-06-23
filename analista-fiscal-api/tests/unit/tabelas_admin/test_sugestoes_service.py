"""Testes do SugestaoVigenciaService — Camada 3 (Sprint 19.5 PR3)."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.modules.tabelas_admin.recheck_llm import CitacaoLLM
from app.modules.tabelas_admin.sugestoes_repo import (
    idempotency_key_para_dou,
)
from app.modules.tabelas_admin.sugestoes_service import (
    SugestaoVigenciaService,
)
from app.shared.exceptions import (
    SugestaoVigenciaForaDeFluxo,
    SugestaoVigenciaNaoEncontrada,
)
from tests.unit.tabelas_admin._helpers import faixas_inss_2026

_TZ_BR = ZoneInfo("America/Sao_Paulo")


_PAYLOAD_INSS_LLM: dict[str, object] = {
    "valid_from": "2026-01-15",
    "fonte_norma": "Portaria MPS/MF 1/2026, DOU 2026-01-15 seção 1 página 42",
    "faixas": [
        {
            "tipo": f.tipo,
            "faixa": f.faixa,
            "valor_ate": str(f.valor_ate),
            "aliquota": str(f.aliquota),
        }
        for f in faixas_inss_2026()
    ],
}

_PDF_INSS = """
ART. 1º A contribuição previdenciária dos segurados empregado, empregado
doméstico e trabalhador avulso será calculada conforme tabela.
Tabela: até R$ 1.620,00 — 7,5%; de R$ 1.620,01 a R$ 2.966,68 — 9,0%;
de R$ 2.966,69 a R$ 4.450,02 — 12,0%; de R$ 4.450,03 a R$ 8.530,06 — 14,0%.
Vigência a partir de 1º de janeiro de 2026.
"""

_CITACOES_OK = [
    CitacaoLLM(pagina=42, trecho="ART. 1º A contribuição previdenciária"),
    CitacaoLLM(pagina=42, trecho="Tabela: até R$ 1.620,00 — 7,5%"),
    CitacaoLLM(pagina=42, trecho="Vigência a partir de 1º de janeiro de 2026"),
]


def _svc(
    *,
    log_existente: object | None = None,
    sugestao_existente: object | None = None,
    tabela_admin_service: AsyncMock | None = None,
) -> tuple[SugestaoVigenciaService, AsyncMock, AsyncMock]:
    sugestao_repo = AsyncMock()
    sugestao_repo.por_idempotency_key = AsyncMock(return_value=None)
    sugestao_repo.por_id = AsyncMock(return_value=sugestao_existente)
    sugestao_repo.criar = AsyncMock(side_effect=lambda s: s)
    sugestao_repo.marcar_aprovada = AsyncMock(side_effect=lambda s, **k: s)
    sugestao_repo.marcar_rejeitada = AsyncMock(side_effect=lambda s, **k: s)
    sugestao_repo.expirar_pendentes_antigas = AsyncMock(return_value=0)
    sugestao_repo.listar = AsyncMock(return_value=[])

    session = AsyncMock()
    svc = SugestaoVigenciaService(
        sugestao_repo=sugestao_repo,
        tabela_admin_service=tabela_admin_service,
    )
    return svc, sugestao_repo, session


# ── Idempotency key DOU ────────────────────────────────────────────────────


def test_idempotency_key_dou_estavel_por_tipo_url() -> None:
    k1 = idempotency_key_para_dou(
        url_dou="https://in.gov.br/web/dou/-/portaria-mps-mf-1-2026-...",
        tipo_tabela="inss",
    )
    k2 = idempotency_key_para_dou(
        url_dou="https://in.gov.br/web/dou/-/portaria-mps-mf-1-2026-...",
        tipo_tabela="inss",
    )
    assert k1 == k2
    assert k1.version == 5


def test_idempotency_key_dou_muda_por_tipo() -> None:
    k_inss = idempotency_key_para_dou(
        url_dou="https://in.gov.br/x", tipo_tabela="inss"
    )
    k_irrf = idempotency_key_para_dou(
        url_dou="https://in.gov.br/x", tipo_tabela="irrf"
    )
    assert k_inss != k_irrf


# ── persistir_extracao_llm ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_persistir_extracao_llm_cria_sugestao_pendente() -> None:
    svc, sugestao_repo, session = _svc()
    sugestao = await svc.persistir_extracao_llm(
        session,
        tipo_tabela="inss",
        payload_llm=_PAYLOAD_INSS_LLM,
        citacoes_llm=_CITACOES_OK,
        confianca_llm=Decimal("0.95"),
        texto_pdf=_PDF_INSS,
        fonte_dou_url="https://in.gov.br/x",
        fonte_dou_pagina=42,
        fonte_norma="Portaria MPS/MF 1/2026, DOU 2026-01-15 página 42",
        llm_modelo="gemini-2.5-flash",
        llm_versao_prompt="extrair_tabela_inss_v1",
    )
    assert sugestao.tipo_tabela == "inss"
    assert sugestao.recheck_passou is True
    assert sugestao.llm_modelo == "gemini-2.5-flash"
    sugestao_repo.criar.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persistir_extracao_llm_idempotente_segunda_vez() -> None:
    """Worker rodando 2× na mesma matéria DOU devolve sugestão anterior."""
    existente = SimpleNamespace(
        id=uuid4(),
        tipo_tabela="inss",
        status="pendente",
    )
    svc, sugestao_repo, session = _svc()
    sugestao_repo.por_idempotency_key = AsyncMock(return_value=existente)

    devolvida = await svc.persistir_extracao_llm(
        session,
        tipo_tabela="inss",
        payload_llm=_PAYLOAD_INSS_LLM,
        citacoes_llm=_CITACOES_OK,
        confianca_llm=Decimal("0.95"),
        texto_pdf=_PDF_INSS,
        fonte_dou_url="https://in.gov.br/x",
        fonte_dou_pagina=42,
        fonte_norma="Portaria MPS/MF 1/2026, DOU 2026-01-15 página 42",
        llm_modelo="gemini-2.5-flash",
        llm_versao_prompt="extrair_tabela_inss_v1",
    )
    assert devolvida is existente
    sugestao_repo.criar.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_persistir_extracao_llm_grava_mesmo_se_recheck_falha() -> None:
    """LLM erra a aliquota — sugestão é criada com recheck_passou=false."""
    payload_quebrado = dict(_PAYLOAD_INSS_LLM)
    faixas = [dict(f) for f in payload_quebrado["faixas"]]  # type: ignore[arg-type]
    faixas[0]["aliquota"] = "0.75"  # implausível
    payload_quebrado["faixas"] = faixas

    svc, sugestao_repo, session = _svc()
    sugestao = await svc.persistir_extracao_llm(
        session,
        tipo_tabela="inss",
        payload_llm=payload_quebrado,
        citacoes_llm=_CITACOES_OK,
        confianca_llm=Decimal("0.95"),
        texto_pdf=_PDF_INSS,
        fonte_dou_url="https://in.gov.br/x",
        fonte_dou_pagina=42,
        fonte_norma="Portaria MPS/MF 1/2026, DOU 2026-01-15 página 42",
        llm_modelo="gemini-2.5-flash",
        llm_versao_prompt="extrair_tabela_inss_v1",
    )
    # Sugestão é criada — admin decide se aprova mesmo assim
    assert sugestao.recheck_passou is False
    assert "falhas" in sugestao.recheck_observacoes
    sugestao_repo.criar.assert_awaited_once()


# ── Aprovar ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_aprovar_sugestao_pendente_chama_camada_1_e_linka_log() -> None:
    sugestao_pendente = SimpleNamespace(
        id=uuid4(),
        tipo_tabela="inss",
        status="pendente",
        payload_jsonb=_PAYLOAD_INSS_LLM,
        # campos para marcar_aprovada
        aprovada_em=None,
        aprovada_por_usuario_id=None,
        vigencia_tabela_log_id=None,
    )
    log_criado = SimpleNamespace(id=uuid4())

    tabela_admin_svc = AsyncMock()
    tabela_admin_svc.criar_vigencia_inss = AsyncMock(return_value=log_criado)

    svc, sugestao_repo, session = _svc(
        sugestao_existente=sugestao_pendente,
        tabela_admin_service=tabela_admin_svc,
    )

    devolvida = await svc.aprovar(session, sugestao_pendente.id)

    tabela_admin_svc.criar_vigencia_inss.assert_awaited_once()
    sugestao_repo.marcar_aprovada.assert_awaited_once()
    assert devolvida is sugestao_pendente


@pytest.mark.asyncio
async def test_aprovar_inexistente_devolve_404() -> None:
    svc, _, session = _svc(
        sugestao_existente=None,
        tabela_admin_service=AsyncMock(),
    )
    with pytest.raises(SugestaoVigenciaNaoEncontrada):
        await svc.aprovar(session, uuid4())


@pytest.mark.asyncio
async def test_aprovar_ja_aprovada_devolve_409() -> None:
    sugestao = SimpleNamespace(
        id=uuid4(),
        tipo_tabela="inss",
        status="aprovada",  # já aprovada
    )
    svc, _, session = _svc(
        sugestao_existente=sugestao,
        tabela_admin_service=AsyncMock(),
    )
    with pytest.raises(SugestaoVigenciaForaDeFluxo, match="aprovada"):
        await svc.aprovar(session, sugestao.id)


# ── Rejeitar ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rejeitar_sugestao_pendente_marca_rejeitada() -> None:
    sugestao = SimpleNamespace(
        id=uuid4(),
        status="pendente",
        rejeitada_motivo=None,
    )
    svc, sugestao_repo, session = _svc(sugestao_existente=sugestao)
    devolvida = await svc.rejeitar(
        session, sugestao.id, motivo="LLM acertou estrutura mas ano errado"
    )
    sugestao_repo.marcar_rejeitada.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert devolvida is sugestao


@pytest.mark.asyncio
async def test_rejeitar_ja_rejeitada_devolve_409() -> None:
    sugestao = SimpleNamespace(id=uuid4(), status="rejeitada")
    svc, _, session = _svc(sugestao_existente=sugestao)
    with pytest.raises(SugestaoVigenciaForaDeFluxo):
        await svc.rejeitar(session, sugestao.id, motivo="qualquer")


# ── Expirar ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expirar_pendentes_antigas_chama_repo_e_comita() -> None:
    svc, sugestao_repo, session = _svc()
    sugestao_repo.expirar_pendentes_antigas = AsyncMock(return_value=3)
    n = await svc.expirar_pendentes_antigas(session, max_dias=60)
    assert n == 3
    sugestao_repo.expirar_pendentes_antigas.assert_awaited_with(max_dias=60)
    session.commit.assert_awaited_once()
