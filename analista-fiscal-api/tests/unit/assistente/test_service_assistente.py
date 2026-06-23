"""Testes unitários do serviço do assistente — out-of-scope, fallback LLM, citação."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.assistente.schemas import PerguntaIn
from app.modules.assistente.service import responder_pergunta
from app.shared.llm.client import Citacao, LLMProvider, LLMResponse


def _llm_resp(
    texto: str = "Sua empresa está regular.",
    citacoes: list[Citacao] | None = None,
    provider: LLMProvider = LLMProvider.GEMINI_2_5_FLASH_LITE,
) -> LLMResponse:
    return LLMResponse(
        texto=texto,
        citacoes=citacoes or [],
        tokens_input=10,
        tokens_output=20,
        tokens_cached=0,
        custo_usd=Decimal("0.001"),
        provider=provider,
        latencia_ms=300,
    )


def _mock_settings() -> MagicMock:
    s = MagicMock()
    s.OLLAMA_URL = "http://localhost:11434"
    return s


# ── Out-of-scope ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("pergunta,categoria", [
    ("Como me defender de um auto de infração do CARF?", "contencioso_fiscal"),
    ("Quero abrir uma holding familiar", "societario"),
    ("Reduzir impostos com planejamento tributário", "planejamento_tributario"),
    ("Importação com drawback", "operacoes_complexas"),
])
async def test_pergunta_out_of_scope_encaminha_marketplace(
    pergunta: str, categoria: str
) -> None:
    empresa_id = uuid4()
    payload = PerguntaIn(pergunta=pergunta)
    session = AsyncMock()
    llm_client = AsyncMock()
    settings = _mock_settings()

    # Sprint 13 PR2: o assistente também resolve parceiros sugeridos para
    # out-of-scope. Aqui o lookup retorna lista vazia (sem parceiros
    # cadastrados); o teste cobre apenas o roteamento, não a lista.
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    parceiro_repo = AsyncMock()
    parceiro_repo.listar_ativos = AsyncMock(return_value=[])

    with (
        patch(
            "app.modules.assistente.service.EmpresaRepo", return_value=empresa_repo
        ),
        patch(
            "app.modules.assistente.service.ContadorParceiroRepo",
            return_value=parceiro_repo,
        ),
    ):
        resposta = await responder_pergunta(empresa_id, payload, session, llm_client, settings)

    assert resposta.encaminhar_marketplace is True
    assert resposta.categoria_marketplace == categoria
    assert resposta.provider_usado == "deterministic"
    assert resposta.tokens_input == 0
    assert resposta.parceiros_sugeridos == []
    llm_client.chamar.assert_not_called()


async def test_pergunta_in_scope_chama_llm() -> None:
    empresa_id = uuid4()
    payload = PerguntaIn(pergunta="Quanto pago de DAS em maio?")
    session = AsyncMock()
    llm_client = AsyncMock()
    llm_client.chamar = AsyncMock(return_value=_llm_resp())
    settings = _mock_settings()

    with patch(
        "app.modules.assistente.service.buscar_contexto_rag",
        new=AsyncMock(return_value=MagicMock(nodes=[], similaridade_media=0.0, query_usada="")),
    ), patch(
        "app.modules.assistente.service.contexto_para_fontes",
        return_value=[],
    ):
        resposta = await responder_pergunta(empresa_id, payload, session, llm_client, settings)

    llm_client.chamar.assert_called_once()
    assert resposta.encaminhar_marketplace is False
    assert resposta.resposta == "Sua empresa está regular."


# ── Fallback quando LLM falha ─────────────────────────────────────────────────


async def test_fallback_quando_llm_levanta_excecao() -> None:
    from app.shared.llm.citacao import RESPOSTA_PADRAO_VERIFICAR

    empresa_id = uuid4()
    payload = PerguntaIn(pergunta="Quanto pago de DAS?")
    session = AsyncMock()
    llm_client = AsyncMock()
    llm_client.chamar = AsyncMock(side_effect=Exception("LLM down"))
    settings = _mock_settings()

    with patch(
        "app.modules.assistente.service.buscar_contexto_rag",
        new=AsyncMock(return_value=MagicMock(nodes=[], similaridade_media=0.0, query_usada="")),
    ), patch(
        "app.modules.assistente.service.contexto_para_fontes",
        return_value=[],
    ):
        resposta = await responder_pergunta(empresa_id, payload, session, llm_client, settings)

    assert resposta.resposta == RESPOSTA_PADRAO_VERIFICAR
    assert resposta.provider_usado == "fallback"


# ── Fallback quando citação inválida ─────────────────────────────────────────


async def test_fallback_quando_citacao_invalida_apos_2_tentativas() -> None:
    """LLM retorna valor inventado 2 vezes → fallback."""
    from app.shared.llm.citacao import RESPOSTA_PADRAO_VERIFICAR

    empresa_id = uuid4()
    payload = PerguntaIn(pergunta="Qual meu DAS de maio?")
    session = AsyncMock()
    llm_client = AsyncMock()
    # Resposta com valor inventado (não nas fontes)
    llm_client.chamar = AsyncMock(return_value=_llm_resp("O DAS foi R$ 99.999,99."))
    settings = _mock_settings()

    with patch(
        "app.modules.assistente.service.buscar_contexto_rag",
        new=AsyncMock(return_value=MagicMock(nodes=[], similaridade_media=0.0, query_usada="")),
    ), patch(
        "app.modules.assistente.service.contexto_para_fontes",
        return_value=[],
    ):
        resposta = await responder_pergunta(empresa_id, payload, session, llm_client, settings)

    # Duas tentativas feitas (fontes vazias → valor R$ não pode estar em fontes)
    assert llm_client.chamar.call_count == 2
    assert resposta.resposta == RESPOSTA_PADRAO_VERIFICAR


# ── Regra 5 (§8.5) — fallback quando afirmação fiscal sem citação ─────────────


async def test_fallback_quando_afirmacao_fiscal_sem_citacao_e_fontes_presentes() -> None:
    """Regra 5 §8.5: resposta com R$ + fontes disponíveis mas zero citações → fallback."""
    from app.shared.llm.citacao import RESPOSTA_PADRAO_VERIFICAR

    empresa_id = uuid4()
    payload = PerguntaIn(pergunta="Qual meu DAS de maio?")
    session = AsyncMock()
    llm_client = AsyncMock()

    # LLM responde com valor monetário mas sem [ID] de citação
    llm_client.chamar = AsyncMock(
        return_value=_llm_resp(
            texto="O DAS de maio foi R$ 1.234,56.",
            citacoes=[],  # cliente não extraiu citação (ou modelo não citou ID)
        )
    )
    settings = _mock_settings()

    # RAG retorna uma fonte (grafo não vazio)

    fontes_rag = [{"id": "ap-001", "tipo": "apuracao_das", "payload": "DAS: R$ 1.234,56"}]

    with patch(
        "app.modules.assistente.service.buscar_contexto_rag",
        new=AsyncMock(return_value=MagicMock(nodes=[], similaridade_media=0.0, query_usada="")),
    ), patch(
        "app.modules.assistente.service.contexto_para_fontes",
        return_value=fontes_rag,
    ):
        resposta = await responder_pergunta(empresa_id, payload, session, llm_client, settings)

    # Duas tentativas (LLM sempre responde sem citação) → fallback
    assert llm_client.chamar.call_count == 2
    assert resposta.resposta == RESPOSTA_PADRAO_VERIFICAR
    assert resposta.provider_usado == "fallback"


# ── RAG falha graciosamente ───────────────────────────────────────────────────


async def test_rag_falha_continua_sem_contexto() -> None:
    """Se o RAG falhar (Ollama down), o assistente ainda responde sem contexto."""
    empresa_id = uuid4()
    payload = PerguntaIn(pergunta="Qual meu regime tributário?")
    session = AsyncMock()
    llm_client = AsyncMock()
    llm_client.chamar = AsyncMock(return_value=_llm_resp("Você é Simples Nacional."))
    settings = _mock_settings()

    with patch(
        "app.modules.assistente.service.buscar_contexto_rag",
        new=AsyncMock(side_effect=Exception("Ollama down")),
    ):
        resposta = await responder_pergunta(empresa_id, payload, session, llm_client, settings)

    # Deve responder mesmo sem RAG
    llm_client.chamar.assert_called_once()
    assert "Simples Nacional" in resposta.resposta


# ── PII roteamento ───────────────────────────────────────────────────────────


async def test_contem_pii_passa_para_llm_request() -> None:
    """contem_pii=True deve ser repassado no LLMRequest para roteamento Ollama."""
    empresa_id = uuid4()
    payload = PerguntaIn(pergunta="Qual meu CPF cadastrado?", contem_pii=True)
    session = AsyncMock()
    llm_client = AsyncMock()
    llm_client.chamar = AsyncMock(return_value=_llm_resp())
    settings = _mock_settings()

    captured_request = []

    async def _capture(req: object, **kwargs: object) -> LLMResponse:
        captured_request.append(req)
        return _llm_resp()

    llm_client.chamar = _capture

    with patch(
        "app.modules.assistente.service.buscar_contexto_rag",
        new=AsyncMock(return_value=MagicMock(nodes=[], similaridade_media=0.0, query_usada="")),
    ), patch(
        "app.modules.assistente.service.contexto_para_fontes",
        return_value=[],
    ):
        await responder_pergunta(empresa_id, payload, session, llm_client, settings)

    assert len(captured_request) == 1
    assert captured_request[0].contem_pii is True
