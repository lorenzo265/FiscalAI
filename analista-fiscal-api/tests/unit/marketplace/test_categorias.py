"""Golden tests do catálogo de categorias (Sprint 13 PR1).

Cobre as 9 categorias do §10.3 + lookup fail-fast + invariantes de comissão.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.modules.marketplace.categorias import (
    CATALOGO_VERSAO,
    CATEGORIAS,
    categoria_do_assistente,
    comissao,
    pricing_para,
)


def test_versao_estavel() -> None:
    assert CATALOGO_VERSAO == "mkt-categorias-2026.05"


def test_nove_categorias_do_plano() -> None:
    esperadas = {
        "consulta_rapida",
        "analise_intimacao_simples",
        "analise_intimacao_complexa",
        "parecer_tecnico",
        "peticao_administrativa",
        "defesa_auto",
        "planejamento_tributario",
        "holding",
        "sucessao",
    }
    assert esperadas == CATEGORIAS


def test_pricing_consulta_rapida() -> None:
    p = pricing_para("consulta_rapida")
    assert p.preco_base == Decimal("80.00")
    assert p.comissao_pct == Decimal("0.30")
    assert p.sla_aceitar == timedelta(hours=4)
    assert p.sla_responder == timedelta(hours=24)


def test_pricing_holding_premium() -> None:
    p = pricing_para("holding")
    assert p.preco_base == Decimal("3000.00")
    assert p.comissao_pct == Decimal("0.15")
    assert p.sla_responder == timedelta(days=30)


def test_pricing_fail_fast_em_categoria_invalida() -> None:
    with pytest.raises(ValueError, match="Categoria desconhecida"):
        pricing_para("rebaba")


@pytest.mark.parametrize(
    "categoria,valor,esperado",
    [
        ("consulta_rapida", Decimal("100.00"), Decimal("30.00")),       # 30%
        ("analise_intimacao_simples", Decimal("200.00"), Decimal("50.00")),  # 25%
        ("parecer_tecnico", Decimal("1000.00"), Decimal("200.00")),     # 20%
        ("holding", Decimal("5000.00"), Decimal("750.00")),             # 15%
        # Arredondamento half-even sobre fração — quantize(0.01)
        ("consulta_rapida", Decimal("99.99"), Decimal("30.00")),
    ],
)
def test_comissao_calcula_correto(
    categoria: str, valor: Decimal, esperado: Decimal
) -> None:
    assert comissao(categoria, valor) == esperado


def test_comissao_nunca_excede_valor() -> None:
    # Sanity — invariante exigida pelo CHECK do DB.
    for cat in CATEGORIAS:
        c = comissao(cat, Decimal("100.00"))
        assert c <= Decimal("100.00"), f"{cat}: comissão {c} > valor 100"


def test_mapping_assistente_marketplace() -> None:
    assert categoria_do_assistente("contencioso_fiscal") == "analise_intimacao_complexa"
    assert categoria_do_assistente("societario") == "holding"
    assert categoria_do_assistente("planejamento_tributario") == "planejamento_tributario"
    assert categoria_do_assistente("operacoes_complexas") == "parecer_tecnico"
    assert categoria_do_assistente("inexistente") is None


def test_sla_aceitar_menor_que_responder() -> None:
    """Invariante de UX: tempo para aceitar < tempo para responder."""
    for cat in CATEGORIAS:
        p = pricing_para(cat)
        assert p.sla_aceitar < p.sla_responder, (
            f"{cat}: sla_aceitar {p.sla_aceitar} >= sla_responder {p.sla_responder}"
        )
