from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


def carregar_jsonl(nome_arquivo: str) -> list[dict[str, Any]]:
    """Carrega casos de um arquivo JSONL na pasta tests/eval/."""
    caminho = Path(__file__).parent / nome_arquivo
    casos: list[dict[str, Any]] = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#"):
            casos.append(json.loads(linha))
    return casos


@pytest.fixture(scope="session")
def casos_citacao() -> list[dict[str, Any]]:
    return carregar_jsonl("citacao_obrigatoria.jsonl")


@pytest.fixture(scope="session")
def casos_alucinacao() -> list[dict[str, Any]]:
    return carregar_jsonl("alucinacao_valor.jsonl")


@pytest.fixture(scope="session")
def casos_marketplace() -> list[dict[str, Any]]:
    return carregar_jsonl("encaminhamento_marketplace.jsonl")


@pytest.fixture(scope="session")
def casos_intent() -> list[dict[str, Any]]:
    return carregar_jsonl("intent_classification.jsonl")


@pytest.fixture(scope="session")
def casos_extracao() -> list[dict[str, Any]]:
    return carregar_jsonl("extracao_estruturada.jsonl")
