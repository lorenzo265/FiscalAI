"""
Eval: classificação de intent — 100 casos.

Esses testes verificam a cobertura e estrutura dos casos de eval.
Para executar contra LLM real: RUN_EVAL_LIVE=true poetry run pytest tests/eval/test_intent.py -m eval_live
"""
from __future__ import annotations

import os

import pytest

from tests.eval.conftest import carregar_jsonl

_CASOS = carregar_jsonl("intent_classification.jsonl")

_INTENTS_ESPERADOS = {
    "consulta_das", "consulta_pgdas", "emissao_nota", "consulta_situacao",
    "consulta_relatorio", "consulta_regime", "consulta_agenda", "explicacao_fiscal",
    "out_of_scope", "consulta_folha", "consulta_financeiro", "acao_rh", "acao_nota",
    "consulta_reforma", "consulta_ingestao",
}


def test_casos_intent_contam_100_minimo() -> None:
    """Barreira de merge: eval suite deve ter ≥100 casos de intent."""
    assert len(_CASOS) >= 100, f"Esperado ≥100 casos de intent, encontrado {len(_CASOS)}"


def test_casos_intent_tem_campos_obrigatorios() -> None:
    """Todos os casos devem ter os campos mínimos esperados."""
    campos_obrigatorios = {"id", "pergunta", "intento_esperado", "out_of_scope", "mock_resposta"}
    for caso in _CASOS:
        faltando = campos_obrigatorios - set(caso.keys())
        assert not faltando, f"Caso {caso.get('id', '?')} falta campos: {faltando}"


def test_casos_intent_intents_validos() -> None:
    """Todos os intents esperados devem ser do conjunto conhecido."""
    for caso in _CASOS:
        intento = caso["intento_esperado"]
        assert intento in _INTENTS_ESPERADOS, (
            f"Caso {caso['id']}: intent desconhecido '{intento}'. "
            f"Válidos: {sorted(_INTENTS_ESPERADOS)}"
        )


def test_casos_intent_cobertura_out_of_scope() -> None:
    """Deve haver pelo menos 10 casos de out-of-scope no eval suite."""
    out_of_scope = [c for c in _CASOS if c["out_of_scope"]]
    assert len(out_of_scope) >= 10, (
        f"Poucos casos out-of-scope: {len(out_of_scope)}. Mínimo: 10."
    )


def test_casos_intent_ids_unicos() -> None:
    """Todos os IDs de casos devem ser únicos."""
    ids = [c["id"] for c in _CASOS]
    assert len(ids) == len(set(ids)), "IDs duplicados encontrados nos casos de intent"


@pytest.mark.skipif(
    os.getenv("RUN_EVAL_LIVE") != "true",
    reason="Skipped em CI. Executar com RUN_EVAL_LIVE=true para eval com LLM real.",
)
def test_intent_accuracy_live() -> None:
    """Eval live: requer GEMINI_API_KEY ou Ollama rodando. Threshold: ≥95%."""
    pytest.skip("Implementar quando provider LLM estiver disponível no ambiente de teste.")
