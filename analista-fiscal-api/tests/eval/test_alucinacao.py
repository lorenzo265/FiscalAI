"""
Eval: alucinação de valor monetário — testa validar_resposta() com 50 casos focados em valores R$.

Esses testes rodam em CI (função pura, sem LLM).
Threshold: 0% de alucinação de valor monetário (zero tolerância absoluta).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.shared.llm.citacao import validar_resposta
from app.shared.llm.client import Citacao, FonteFato, LLMProvider, LLMResponse
from tests.eval.conftest import carregar_jsonl

_CASOS = carregar_jsonl("alucinacao_valor.jsonl")
assert len(_CASOS) >= 50, f"Esperado ≥50 casos de alucinação, encontrado {len(_CASOS)}"


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
        custo_usd=Decimal("0"),
        provider=LLMProvider.GEMINI_2_5_FLASH_LITE,
        latencia_ms=0,
    )


def _montar_fontes(caso: dict[str, Any]) -> list[FonteFato]:
    return [
        FonteFato(id=f["id"], tipo=f["tipo"], payload=f["payload"], data=f.get("data"))
        for f in caso.get("fontes", [])
    ]


@pytest.mark.parametrize("caso", _CASOS, ids=[c["id"] for c in _CASOS])
def test_alucinacao_valor(caso: dict[str, Any]) -> None:
    """Alucinação de valor monetário deve ser sempre detectada (resultado == esperado)."""
    resp = _montar_response(caso)
    fontes = _montar_fontes(caso)
    esperado = caso["esperado_valida"]
    motivo = caso.get("motivo", "sem motivo")

    resultado = validar_resposta(resp, fontes)

    assert resultado == esperado, (
        f"[{caso['id']}] Motivo: {motivo} — "
        f"Esperado valida={esperado}, obtido {resultado}. "
        f"Texto: '{resp.texto[:100]}'"
    )


def test_alucinacao_zero_porcento_tolerancia() -> None:
    """CI gate: nenhum caso de alucinação de valor deve passar como válido."""
    casos_alucinacao_real = [c for c in _CASOS if not c["esperado_valida"]]
    falsos_positivos = 0

    for caso in casos_alucinacao_real:
        resp = _montar_response(caso)
        fontes = _montar_fontes(caso)
        resultado = validar_resposta(resp, fontes)
        if resultado is True:  # validou algo que era alucinação → falso positivo
            falsos_positivos += 1

    assert falsos_positivos == 0, (
        f"CRÍTICO: {falsos_positivos} alucinações de valor monetário passaram como válidas. "
        "Zero tolerância — cada falso positivo representa risco real de erro fiscal para o cliente."
    )


def test_casos_alucinacao_contam_50_minimo() -> None:
    """Garante que o eval suite tem casos suficientes para ser estatisticamente relevante."""
    assert len(_CASOS) >= 50, f"Eval de alucinação precisa de ≥50 casos, tem {len(_CASOS)}"
