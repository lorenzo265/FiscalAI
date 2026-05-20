"""Testes do carregador de prompts versionados (ADR 0012)."""

from __future__ import annotations

import pytest

from app.shared.llm.prompts import get_prompt


def test_carrega_prompt_assistente_v1() -> None:
    p = get_prompt("assistente_resposta_v1")
    assert p.nome == "assistente_resposta_v1"
    assert p.versao == "1"
    assert "Analista Fiscal" in p.texto
    assert "Cite todos os fatos" in p.texto
    assert p.path.name == "assistente_resposta_v1.md"


def test_prompt_inexistente_levanta() -> None:
    with pytest.raises(FileNotFoundError):
        get_prompt("nao_existe_v1")


def test_prompt_cacheado_retorna_mesma_instancia() -> None:
    """``@lru_cache`` garante que carregar duas vezes retorna o mesmo objeto."""
    a = get_prompt("assistente_resposta_v1")
    b = get_prompt("assistente_resposta_v1")
    assert a is b


def test_versao_extraida_do_sufixo() -> None:
    """Sufixo ``_vN`` no nome → versão ``N``."""
    p = get_prompt("assistente_resposta_v1")
    assert p.versao == "1"
