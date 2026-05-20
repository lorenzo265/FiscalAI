"""
Eval: encaminhamento para marketplace de contadores.

Testa detectar_out_of_scope() com 50 casos (pattern matching puro).
Esses testes rodam em CI sem LLM.
Threshold: >90% de acurácia no encaminhamento.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.shared.llm.citacao import detectar_out_of_scope
from tests.eval.conftest import carregar_jsonl

_CASOS = carregar_jsonl("encaminhamento_marketplace.jsonl")
assert len(_CASOS) >= 50, f"Esperado ≥50 casos marketplace, encontrado {len(_CASOS)}"

_THRESHOLD = 0.90


@pytest.mark.parametrize("caso", _CASOS, ids=[c["id"] for c in _CASOS])
def test_deteccao_out_of_scope(caso: dict[str, Any]) -> None:
    """Verifica se a detecção de out-of-scope coincide com o esperado."""
    pergunta = caso["pergunta"]
    esperado_out = caso["esperado_out_of_scope"]
    esperada_cat = caso.get("esperada_categoria")

    eh_out_of_scope, categoria = detectar_out_of_scope(pergunta)

    assert eh_out_of_scope == esperado_out, (
        f"[{caso['id']}] Pergunta: '{pergunta}' — "
        f"Esperado out_of_scope={esperado_out}, obtido {eh_out_of_scope}"
    )
    if esperado_out and esperada_cat:
        assert categoria == esperada_cat, (
            f"[{caso['id']}] Categoria esperada='{esperada_cat}', obtida '{categoria}'"
        )


def test_marketplace_accuracy_threshold() -> None:
    """CI gate: acurácia de encaminhamento deve ser ≥90%."""
    corretos = 0
    total = len(_CASOS)

    for caso in _CASOS:
        eh_out_of_scope, _ = detectar_out_of_scope(caso["pergunta"])
        if eh_out_of_scope == caso["esperado_out_of_scope"]:
            corretos += 1

    acuracia = corretos / total
    assert acuracia >= _THRESHOLD, (
        f"Threshold marketplace: {_THRESHOLD:.0%} requerido, obtido {acuracia:.1%} "
        f"({corretos}/{total})"
    )


def test_casos_marketplace_contam_50_minimo() -> None:
    assert len(_CASOS) >= 50


def test_sem_falsos_negativos_criticos() -> None:
    """Casos críticos de out-of-scope (contencioso fiscal) nunca devem passar como in-scope."""
    criticos = [c for c in _CASOS if c.get("esperada_categoria") == "contencioso_fiscal"]
    falsos_negativos = 0

    for caso in criticos:
        eh_out, _ = detectar_out_of_scope(caso["pergunta"])
        if not eh_out:
            falsos_negativos += 1

    assert falsos_negativos == 0, (
        f"{falsos_negativos} perguntas de contencioso fiscal passaram como in-scope. "
        "Esses casos devem SEMPRE ser encaminhados ao marketplace."
    )
