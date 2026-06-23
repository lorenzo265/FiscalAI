"""
Eval: citação obrigatória — testa validar_resposta() com 50 casos reais.

Esses testes rodam em CI (função pura, sem LLM).
Threshold: 100% de acurácia (zero tolerância para citação inválida não detectada).
"""
from __future__ import annotations

from typing import Any

import pytest

from app.shared.llm.citacao import validar_resposta
from app.shared.llm.client import Citacao, FonteFato, LLMProvider, LLMResponse
from tests.eval.conftest import carregar_jsonl

_CASOS = carregar_jsonl("citacao_obrigatoria.jsonl")
assert len(_CASOS) >= 50, f"Esperado ≥50 casos de citação, encontrado {len(_CASOS)}"


def _montar_response(caso: dict[str, Any]) -> LLMResponse:
    citacoes = [
        Citacao(fato_id=c["fato_id"], trecho_citado=c["trecho_citado"])
        for c in caso.get("llm_citacoes", [])
    ]
    return LLMResponse(
        texto=caso["llm_texto"],
        citacoes=citacoes,
        tokens_input=0,
        tokens_output=0,
        tokens_cached=0,
        custo_usd=0,
        provider=LLMProvider.GEMINI_2_5_FLASH_LITE,
        latencia_ms=0,
    )


def _montar_fontes(caso: dict[str, Any]) -> list[FonteFato]:
    return [
        FonteFato(
            id=f["id"],
            tipo=f["tipo"],
            payload=f["payload"],
            data=f.get("data"),
        )
        for f in caso.get("fontes", [])
    ]


@pytest.mark.parametrize("caso", _CASOS, ids=[c["id"] for c in _CASOS])
def test_citacao_obrigatoria(caso: dict[str, Any]) -> None:
    """Cada caso deve ter resultado de validação igual ao esperado."""
    resp = _montar_response(caso)
    fontes = _montar_fontes(caso)
    esperado = caso["esperado_valida"]

    resultado = validar_resposta(resp, fontes)

    assert resultado == esperado, (
        f"[{caso['id']}] Esperado valida={esperado}, obtido {resultado}. "
        f"Texto: '{resp.texto[:80]}...'"
    )


def test_citacao_threshold_100_porcento() -> None:
    """CI gate: taxa de citação válida deve ser 100% (zero tolerância)."""
    corretos = 0
    total = len(_CASOS)

    for caso in _CASOS:
        resp = _montar_response(caso)
        fontes = _montar_fontes(caso)
        resultado = validar_resposta(resp, fontes)
        if resultado == caso["esperado_valida"]:
            corretos += 1

    acuracia = corretos / total
    assert acuracia == 1.0, (
        f"Threshold citação: 100% requerido, obtido {acuracia:.1%} "
        f"({corretos}/{total} corretos)"
    )
