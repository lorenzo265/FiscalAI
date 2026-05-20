"""
Eval: extração estruturada — 100 casos.

Valida estrutura e cobertura dos casos de extração.
Para eval live: RUN_EVAL_LIVE=true poetry run pytest tests/eval/test_extracao.py -m eval_live
"""
from __future__ import annotations

import json
import os
from typing import Any

import pytest

from tests.eval.conftest import carregar_jsonl

_CASOS = carregar_jsonl("extracao_estruturada.jsonl")


def test_casos_extracao_contam_100_minimo() -> None:
    """Barreira de merge: eval suite deve ter ≥100 casos de extração."""
    assert len(_CASOS) >= 100, f"Esperado ≥100 casos de extração, encontrado {len(_CASOS)}"


def test_casos_extracao_tem_campos_obrigatorios() -> None:
    campos = {"id", "texto", "esperado", "mock_resposta"}
    for caso in _CASOS:
        faltando = campos - set(caso.keys())
        assert not faltando, f"Caso {caso.get('id', '?')} falta campos: {faltando}"


def test_casos_extracao_mock_resposta_e_json_valido() -> None:
    """O campo mock_resposta de cada caso deve ser JSON válido."""
    for caso in _CASOS:
        try:
            json.loads(caso["mock_resposta"])
        except json.JSONDecodeError as e:
            pytest.fail(f"Caso {caso['id']}: mock_resposta não é JSON válido: {e}")


def test_casos_extracao_ids_unicos() -> None:
    ids = [c["id"] for c in _CASOS]
    assert len(ids) == len(set(ids)), "IDs duplicados nos casos de extração"


def test_casos_extracao_esperado_nao_vazio() -> None:
    """Cada caso deve ter pelo menos um campo no objeto 'esperado'."""
    for caso in _CASOS:
        assert isinstance(caso["esperado"], dict) and len(caso["esperado"]) > 0, (
            f"Caso {caso['id']}: campo 'esperado' está vazio"
        )


@pytest.mark.skipif(
    os.getenv("RUN_EVAL_LIVE") != "true",
    reason="Skipped em CI. Executar com RUN_EVAL_LIVE=true para eval com LLM real.",
)
def test_extracao_f1_live() -> None:
    """Eval live: F1 de extração deve ser ≥90%. Requer provider LLM disponível."""
    pytest.skip("Implementar quando provider LLM estiver disponível no ambiente de teste.")
