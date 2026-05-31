"""Testes de pontos do router admin de tabelas (Sprint 19.5 PR1).

O guard ``require_tax_table_admin_token`` é estruturalmente idêntico ao
``require_admin_token`` do marketplace (Sprint 13 PR1 — já coberto por
``test_auth_parceiro.py``). Aqui testamos só o resolvedor de tipo
kebab-case→snake_case e a cobertura do mapeamento URL→tipo.
"""

from __future__ import annotations

import pytest

from app.modules.tabelas_admin.router import _URL_PARA_TIPO, _resolver_tipo
from app.modules.tabelas_admin.schemas import TIPOS_TABELA_SUPORTADOS
from app.shared.exceptions import TipoTabelaDesconhecido


def test_url_para_tipo_cobre_todos_os_tipos_suportados() -> None:
    """Garantia de invariante: o mapa kebab-case→snake_case do router cobre
    exatamente os 7 tipos em TIPOS_TABELA_SUPORTADOS.
    """
    assert set(_URL_PARA_TIPO.values()) == set(TIPOS_TABELA_SUPORTADOS)


def test_resolver_tipo_kebab_para_snake() -> None:
    assert _resolver_tipo("simples-nacional") == "simples_nacional"
    assert _resolver_tipo("presuncao-lp") == "presuncao_lp"
    assert _resolver_tipo("icms-uf") == "icms_uf"
    assert _resolver_tipo("cbs-ibs") == "cbs_ibs"
    assert _resolver_tipo("inss") == "inss"
    assert _resolver_tipo("irrf") == "irrf"
    assert _resolver_tipo("fgts") == "fgts"


def test_resolver_tipo_desconhecido_levanta_422() -> None:
    with pytest.raises(TipoTabelaDesconhecido, match="desconhecido"):
        _resolver_tipo("tipo-que-nao-existe")


def test_tipo_em_snake_case_no_url_nao_resolve() -> None:
    """URL precisa estar em kebab-case (``simples-nacional``), não snake."""
    with pytest.raises(TipoTabelaDesconhecido):
        _resolver_tipo("simples_nacional")
