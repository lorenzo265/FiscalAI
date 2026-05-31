"""Testes do pipeline DOU → LLM → sugestão (Sprint 19.6 PR3 #41).

Mocka http_client, llm_client, pdf_extractor e service para testar a
orquestração fail-soft do ``processar_materia_dou``. Não chama Gemini
nem DOU real.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from app.modules.tabelas_admin.pipeline_dou import (
    _parse_citacoes,
    _parse_decimal_field,
    _parsear_resposta_llm,
    processar_materia_dou,
)
from app.modules.tabelas_admin.recheck_llm import CitacaoLLM
from app.shared.integrations.dou.client import MateriaDou


# ── helpers de fixture ────────────────────────────────────────────────────


def _materia_inss(*, com_pdf: bool = True) -> MateriaDou:
    return MateriaDou(
        titulo="Portaria MPS/MF 1/2026 — Tabela INSS",
        url_html="https://in.gov.br/web/dou/-/portaria-1-2026",
        url_pdf=(
            "https://in.gov.br/web/dou/-/portaria-1-2026.pdf"
            if com_pdf else None
        ),
        data_publicacao=date(2026, 1, 15),
        secao="Seção 1",
    )


def _http_mock(*, pdf_bytes: bytes = b"%PDF-1.4 fake") -> AsyncMock:
    """Mock httpx.AsyncClient.get devolvendo Response(200) com pdf_bytes."""
    response = MagicMock()
    response.content = pdf_bytes
    response.raise_for_status = MagicMock(return_value=None)
    http = AsyncMock()
    http.get = AsyncMock(return_value=response)
    return http


def _pdf_extractor_ok() -> MagicMock:
    """Mock retornando objeto com texto_total não vazio."""
    return MagicMock(
        return_value=SimpleNamespace(
            texto_total="Tabela INSS empregado: faixa 1 até 1620, 7,5%..."
        )
    )


def _llm_response(payload: dict[str, object]) -> SimpleNamespace:
    """Envelopa um payload dict como LLMResponse-like."""
    return SimpleNamespace(texto=json.dumps(payload))


def _service_mock_sucesso() -> AsyncMock:
    """Mock do SugestaoVigenciaService devolvendo sugestão fake."""
    svc = AsyncMock()
    svc.persistir_extracao_llm = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid4(),
            tipo_tabela="inss",
            status="pendente",
        )
    )
    return svc


# ── Happy path ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_happy_path_persiste_sugestao() -> None:
    payload_llm = {
        "valid_from": "2026-01-15",
        "fonte_norma": "Portaria MPS/MF 1/2026 DOU 2026-01-15",
        "faixas": [
            {"tipo": "empregado", "faixa": 1, "valor_ate": "1620.00",
             "aliquota": "0.075"},
        ],
        "llm_confianca": "0.95",
        "citacoes": [
            {"pagina": 42, "trecho": "Art. 1º Tabela INSS..."},
        ],
    }
    llm = AsyncMock()
    llm.chamar = AsyncMock(return_value=_llm_response(payload_llm))
    svc = _service_mock_sucesso()
    session = AsyncMock()

    sugestao = await processar_materia_dou(
        session,
        _materia_inss(),
        tipo_tabela="inss",
        http_client=_http_mock(),
        llm_client=llm,
        pdf_extractor=_pdf_extractor_ok(),
        service=svc,
    )
    assert sugestao is not None
    svc.persistir_extracao_llm.assert_awaited_once()
    # Citação parseada do payload LLM.
    chamada = svc.persistir_extracao_llm.await_args
    assert chamada.kwargs["tipo_tabela"] == "inss"
    assert chamada.kwargs["confianca_llm"] == Decimal("0.95")
    assert len(chamada.kwargs["citacoes_llm"]) == 1


# ── Fail-soft: sem PDF, sem prompt, download falha ─────────────────────────


@pytest.mark.asyncio
async def test_sem_pdf_url_skipa_materia() -> None:
    svc = _service_mock_sucesso()
    sugestao = await processar_materia_dou(
        AsyncMock(),
        _materia_inss(com_pdf=False),
        tipo_tabela="inss",
        http_client=_http_mock(),
        llm_client=AsyncMock(),
        pdf_extractor=_pdf_extractor_ok(),
        service=svc,
    )
    assert sugestao is None
    svc.persistir_extracao_llm.assert_not_awaited()


@pytest.mark.asyncio
async def test_tipo_desconhecido_skipa() -> None:
    """Tipo sem prompt versionado (ex.: 'icms_uf') retorna None sem chamar LLM."""
    svc = _service_mock_sucesso()
    llm = AsyncMock()
    sugestao = await processar_materia_dou(
        AsyncMock(),
        _materia_inss(),
        tipo_tabela="icms_uf",  # sem prompt em _PROMPT_POR_TIPO
        http_client=_http_mock(),
        llm_client=llm,
        pdf_extractor=_pdf_extractor_ok(),
        service=svc,
    )
    assert sugestao is None
    llm.chamar.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_pdf_falha_skipa() -> None:
    http = AsyncMock()
    http.get = AsyncMock(side_effect=httpx.ConnectError("rede down"))
    svc = _service_mock_sucesso()
    sugestao = await processar_materia_dou(
        AsyncMock(),
        _materia_inss(),
        tipo_tabela="inss",
        http_client=http,
        llm_client=AsyncMock(),
        pdf_extractor=_pdf_extractor_ok(),
        service=svc,
    )
    assert sugestao is None


@pytest.mark.asyncio
async def test_pdf_vazio_skipa() -> None:
    """Extração retorna texto vazio → pula sem chamar LLM."""
    extractor = MagicMock(return_value=SimpleNamespace(texto_total=""))
    llm = AsyncMock()
    svc = _service_mock_sucesso()
    sugestao = await processar_materia_dou(
        AsyncMock(),
        _materia_inss(),
        tipo_tabela="inss",
        http_client=_http_mock(),
        llm_client=llm,
        pdf_extractor=extractor,
        service=svc,
    )
    assert sugestao is None
    llm.chamar.assert_not_awaited()


@pytest.mark.asyncio
async def test_llm_resposta_invalida_skipa() -> None:
    """LLM devolve texto que não é JSON válido → skip."""
    llm = AsyncMock()
    llm.chamar = AsyncMock(
        return_value=SimpleNamespace(texto="isso não é JSON nem em sonho")
    )
    svc = _service_mock_sucesso()
    sugestao = await processar_materia_dou(
        AsyncMock(),
        _materia_inss(),
        tipo_tabela="inss",
        http_client=_http_mock(),
        llm_client=llm,
        pdf_extractor=_pdf_extractor_ok(),
        service=svc,
    )
    assert sugestao is None
    svc.persistir_extracao_llm.assert_not_awaited()


# ── Parsers auxiliares ────────────────────────────────────────────────────


def test_parsear_resposta_llm_aceita_code_fence() -> None:
    """LLM costuma envolver JSON em ```json ... ```."""
    texto = """```json
{"valid_from": "2026-01-15", "faixas": []}
```"""
    result = _parsear_resposta_llm(texto)
    assert result is not None
    assert result["valid_from"] == "2026-01-15"


def test_parsear_resposta_llm_aceita_json_puro() -> None:
    result = _parsear_resposta_llm('{"valid_from": "2026-01-15"}')
    assert result == {"valid_from": "2026-01-15"}


def test_parsear_resposta_llm_invalido_retorna_none() -> None:
    assert _parsear_resposta_llm("xyz") is None
    assert _parsear_resposta_llm("") is None
    # JSON válido mas não-dict (lista) também retorna None.
    assert _parsear_resposta_llm("[1, 2, 3]") is None


def test_parse_decimal_field_fallback() -> None:
    assert _parse_decimal_field("0.95") == Decimal("0.95")
    assert _parse_decimal_field(0.5) == Decimal("0.5")
    # Inválido → 0.5 default.
    assert _parse_decimal_field("abc") == Decimal("0.5")
    assert _parse_decimal_field(None) == Decimal("0.5")


def test_parse_citacoes_aceita_formato_canonico() -> None:
    raw = [
        {"pagina": 42, "trecho": "Art. 1º..."},
        {"pagina": "43", "trecho": "Art. 2º..."},
    ]
    out = _parse_citacoes(raw)
    assert len(out) == 2
    assert all(isinstance(c, CitacaoLLM) for c in out)
    assert out[0].pagina == 42
    assert out[1].pagina == 43  # string convertida


def test_parse_citacoes_ignora_mal_formado() -> None:
    raw = [
        {"pagina": 42, "trecho": "OK"},
        "string solta",  # ignora
        {"pagina": 1},  # sem trecho — ignora
        {"trecho": "Sem página explícita"},  # OK, pagina default 1
    ]
    out = _parse_citacoes(raw)
    assert len(out) == 2
    assert out[1].pagina == 1


def test_parse_citacoes_lista_invalida_devolve_vazio() -> None:
    assert _parse_citacoes("não é lista") == []
    assert _parse_citacoes(None) == []
