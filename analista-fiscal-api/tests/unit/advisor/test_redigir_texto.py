"""Testes do redator de texto do digest (Sprint 15 PR3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.modules.advisor.gera_digest_semanal import (
    AnomaliaResumo,
    ApuracaoResumo,
    DigestEstruturado,
    FonteCitavel,
    SugestaoResumo,
    VencimentoResumo,
    gerar_digest_estruturado,
)
from app.modules.advisor.redigir_texto import (
    FonteRedacao,
    redigir_template,
    redigir_via_llm,
)
from app.shared.llm.client import Citacao, LLMProvider, LLMResponse


def _digest_completo() -> DigestEstruturado:
    return gerar_digest_estruturado(
        empresa_nome="ACME COMERCIO LTDA",
        apuracoes_semana=[
            ApuracaoResumo(
                apuracao_id="a1",
                tipo="das",
                competencia=date(2026, 4, 1),
                valor=Decimal("1234.56"),
            )
        ],
        anomalias_abertas=[
            AnomaliaResumo(
                anomalia_id="an1",
                tipo="pis",
                competencia=date(2026, 4, 1),
                severidade="alta",
                mensagem="PIS subiu 200% em abril/2026.",
                valor_observado=Decimal("3000.00"),
                valor_esperado=Decimal("1000.00"),
            )
        ],
        agenda_proximos=[
            VencimentoResumo(
                agenda_item_id="v1",
                titulo="DAS abril/2026",
                data_vencimento=date(2026, 5, 22),
                tipo_obrigacao="das_sn",
            )
        ],
        sugestoes=[
            SugestaoResumo(
                codigo="fator_r_migrar_anexo_iii",
                titulo="Migre para o Anexo III",
                descricao="Aumente folha para chegar a 28%",
                severidade="alta",
                economia_anual_estimada=Decimal("5000.00"),
            )
        ],
        referencia=date(2026, 5, 20),
    )


# ── Template determinístico ─────────────────────────────────────────────────


def test_template_inclui_apelido_empresa() -> None:
    digest = _digest_completo()
    result = redigir_template(digest)
    assert "ACME" in result.texto
    assert result.fonte is FonteRedacao.TEMPLATE


def test_template_cita_apuracao_anomalia_vencimento_sugestao() -> None:
    digest = _digest_completo()
    result = redigir_template(digest)
    assert "apuracao:a1" in result.citacoes_fato_ids
    assert "anomalia:an1" in result.citacoes_fato_ids
    assert "agenda:v1" in result.citacoes_fato_ids
    assert "sugestao:fator_r_migrar_anexo_iii" in result.citacoes_fato_ids


def test_template_inclui_valor_apuracao_literal() -> None:
    """Valor deve aparecer no texto exatamente como na fonte (§8.5)."""
    digest = _digest_completo()
    result = redigir_template(digest)
    assert "R$ 1,234.56" in result.texto


def test_template_inclui_data_vencimento_iso() -> None:
    digest = _digest_completo()
    result = redigir_template(digest)
    assert "2026-05-22" in result.texto


def test_template_economia_estimada_formatada() -> None:
    digest = _digest_completo()
    result = redigir_template(digest)
    assert "R$ 5,000.00" in result.texto


def test_template_digest_vazio_emite_mensagem_padrao() -> None:
    digest = gerar_digest_estruturado(
        empresa_nome="X",
        apuracoes_semana=[],
        anomalias_abertas=[],
        agenda_proximos=[],
        sugestoes=[],
        referencia=date(2026, 5, 20),
    )
    result = redigir_template(digest)
    assert "Nenhuma novidade" in result.texto
    assert result.citacoes_fato_ids == []


def test_template_call_to_action_no_fim() -> None:
    digest = _digest_completo()
    result = redigir_template(digest)
    assert result.texto.rstrip().endswith("para detalhes e tomar ações.")


def test_template_fonte_redacao_sem_custo_llm() -> None:
    digest = _digest_completo()
    result = redigir_template(digest)
    assert result.llm_provider is None
    assert result.custo_usd is None
    assert result.tokens_input is None


# ── LLM com fallback ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_quando_falha_cai_no_template() -> None:
    digest = _digest_completo()
    llm = AsyncMock()
    llm.chamar = AsyncMock(side_effect=RuntimeError("Gemini down"))
    result = await redigir_via_llm(digest, llm_client=llm, empresa_id="emp1")
    assert result.fonte is FonteRedacao.LLM_FALLBACK
    # Texto vem do template — deve incluir apelido
    assert "ACME" in result.texto


@pytest.mark.asyncio
async def test_llm_quando_aluciona_cai_no_fallback_preservando_custo() -> None:
    """Se ``validar_resposta`` rejeita a saída do LLM, fonte=llm_fallback mas o
    custo já incorrido pelo LLM é preservado para observabilidade (§8.10)."""
    digest = _digest_completo()
    resposta_invalida = LLMResponse(
        texto="Você pagou R$ 9.999,99 — valor que não existe nas fontes.",
        citacoes=[],
        tokens_input=100,
        tokens_output=50,
        tokens_cached=0,
        custo_usd=Decimal("0.0005"),
        provider=LLMProvider.GEMINI_2_5_FLASH,
        latencia_ms=300,
    )
    llm = AsyncMock()
    llm.chamar = AsyncMock(return_value=resposta_invalida)
    result = await redigir_via_llm(digest, llm_client=llm, empresa_id="emp1")
    assert result.fonte is FonteRedacao.LLM_FALLBACK
    assert result.custo_usd == Decimal("0.0005")
    assert result.tokens_input == 100
    # Texto não é a alucinação; é o template
    assert "9,999.99" not in result.texto


@pytest.mark.asyncio
async def test_llm_quando_resposta_valida_persiste_metadados() -> None:
    digest = _digest_completo()
    # Resposta usa só valores presentes nas fontes geradas pelo digest.
    texto_valido = (
        "Resumo da semana ACME. "
        "Apuração DAS competência 2026-04-01: R$ 1,234.56. "
        "DAS abril/2026 vence em 2026-05-22. "
        "PIS subiu 200% em abril/2026."
    )
    resposta_valida = LLMResponse(
        texto=texto_valido,
        citacoes=[
            Citacao(fato_id="apuracao:a1", trecho_citado="DAS 2026-04-01"),
        ],
        tokens_input=120,
        tokens_output=60,
        tokens_cached=80,
        custo_usd=Decimal("0.0003"),
        provider=LLMProvider.GEMINI_2_5_FLASH,
        latencia_ms=250,
    )
    llm = AsyncMock()
    llm.chamar = AsyncMock(return_value=resposta_valida)
    result = await redigir_via_llm(digest, llm_client=llm, empresa_id="emp1")
    assert result.fonte is FonteRedacao.LLM_GEMINI
    assert result.llm_provider == LLMProvider.GEMINI_2_5_FLASH.value
    assert result.custo_usd == Decimal("0.0003")
    assert result.tokens_cached == 80
    assert "apuracao:a1" in result.citacoes_fato_ids


@pytest.mark.asyncio
async def test_llm_usa_cache_key_por_semana() -> None:
    """``cache_key`` inclui empresa_id + semana_iso para isolamento (§8.10)."""
    digest = _digest_completo()
    llm = AsyncMock()
    llm.chamar = AsyncMock(side_effect=RuntimeError("ignore"))
    await redigir_via_llm(digest, llm_client=llm, empresa_id="emp-xyz")
    # llm.chamar foi tentado uma vez antes do fallback
    llm.chamar.assert_awaited_once()
    request = llm.chamar.call_args.args[0]
    assert request.cache_key == "digest:empresa:emp-xyz:2026-W21"
    # Fontes foram passadas para validar_resposta no caller
    assert isinstance(request.fontes_disponiveis, list)
    assert len(request.fontes_disponiveis) > 0
