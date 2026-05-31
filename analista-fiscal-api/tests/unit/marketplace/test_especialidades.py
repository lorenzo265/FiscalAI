"""Testes do conjunto fechado de especialidades + mapping (Sprint 13 PR1)."""

from __future__ import annotations

import pytest

from app.modules.marketplace.categorias import CATEGORIAS
from app.modules.marketplace.especialidades import (
    ESPECIALIDADES,
    ESPECIALIDADES_VERSAO,
    especialidade_para,
    validar_especialidades,
)


def test_versao_estavel() -> None:
    assert ESPECIALIDADES_VERSAO == "mkt-especialidades-2026.05"


def test_especialidades_fechadas() -> None:
    assert ESPECIALIDADES == {
        "tributario",
        "trabalhista",
        "societario",
        "contencioso",
        "planejamento",
        "operacoes",
    }


def test_mapping_cobre_todas_as_categorias() -> None:
    """Toda categoria do marketplace tem que mapear para uma especialidade válida."""
    for cat in CATEGORIAS:
        esp = especialidade_para(cat)
        assert esp in ESPECIALIDADES, f"{cat} → {esp} fora do conjunto"


@pytest.mark.parametrize(
    "categoria,esperada",
    [
        ("consulta_rapida", "tributario"),
        ("defesa_auto", "contencioso"),
        ("holding", "societario"),
        ("sucessao", "societario"),
        ("planejamento_tributario", "planejamento"),
    ],
)
def test_mapping_pontual(categoria: str, esperada: str) -> None:
    assert especialidade_para(categoria) == esperada


def test_especialidade_para_fail_fast() -> None:
    with pytest.raises(ValueError, match="Categoria desconhecida"):
        especialidade_para("rebaba")


def test_validar_vazia_levanta() -> None:
    with pytest.raises(ValueError, match="vazias"):
        validar_especialidades([])


def test_validar_uma_invalida_levanta() -> None:
    with pytest.raises(ValueError, match="inválidas"):
        validar_especialidades(["tributario", "futebol"])


def test_validar_todas_validas_passa() -> None:
    # Não deve levantar
    validar_especialidades(["tributario", "trabalhista"])
    validar_especialidades(list(ESPECIALIDADES))
