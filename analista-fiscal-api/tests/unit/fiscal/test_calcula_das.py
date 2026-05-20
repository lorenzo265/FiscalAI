"""Golden tests — DAS Simples Nacional.

Barreira de merge obrigatória (§8.4 do Plano).
Todo ramo do cálculo deve ter ao menos um caso golden cobrindo-o.

Convenção dos arquivos JSON:
  input.faixas    → tabela CGSN 140/2018 do anexo efetivo já resolvido
  expected.faixa  → número da faixa selecionada (1-6)
  expected.aliquota_efetiva → quantizada em 4 casas ROUND_HALF_EVEN
  expected.valor  → DAS em R$ com 2 casas ROUND_HALF_EVEN
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.fiscal.calcula_das import FaixaDAS, calcular_das, resolver_anexo_fator_r
from app.shared.exceptions import EmpresaForaSimplesNacional

_GOLDEN_DIR = Path(__file__).parent.parent.parent / "golden" / "simples_nacional"


def _load_golden() -> list[tuple[str, dict]]:  # type: ignore[type-arg]
    cases = []
    for path in sorted(_GOLDEN_DIR.glob("*.json")):
        data = json.loads(path.read_text("utf-8"))
        cases.append((path.stem, data))
    return cases


def _faixas_from_json(raw: list[dict]) -> list[FaixaDAS]:  # type: ignore[type-arg]
    return [
        FaixaDAS(
            faixa=item["faixa"],
            rbt12_ate=Decimal(item["rbt12_ate"]),
            aliquota_nominal=Decimal(item["aliquota_nominal"]),
            parcela_deduzir=Decimal(item["parcela_deduzir"]),
        )
        for item in raw
    ]


@pytest.mark.parametrize("nome,caso", _load_golden())
def test_calcula_das_golden(nome: str, caso: dict) -> None:  # type: ignore[type-arg]
    inp = caso["input"]
    exp = caso["expected"]

    faixas = _faixas_from_json(inp["faixas"])
    resultado = calcular_das(
        rbt12=Decimal(inp["rbt12"]),
        receita_mes=Decimal(inp["receita_mes"]),
        faixas=faixas,
        anexo=inp.get("anexo", "I"),
    )

    assert resultado.faixa == exp["faixa"], (
        f"[{nome}] faixa errada: esperado {exp['faixa']}, obtido {resultado.faixa}"
    )
    assert resultado.aliquota_efetiva == Decimal(exp["aliquota_efetiva"]), (
        f"[{nome}] alíquota efetiva errada: "
        f"esperado {exp['aliquota_efetiva']}, obtido {resultado.aliquota_efetiva}"
    )
    assert resultado.valor == Decimal(exp["valor"]), (
        f"[{nome}] valor DAS errado: esperado R${exp['valor']}, obtido R${resultado.valor}"
    )


# ── Testes unitários complementares ─────────────────────────────────────────


_FAIXAS_I = _faixas_from_json([
    {"faixa": 1, "rbt12_ate": "180000.00", "aliquota_nominal": "0.0400", "parcela_deduzir": "0.00"},
    {"faixa": 2, "rbt12_ate": "360000.00", "aliquota_nominal": "0.0730", "parcela_deduzir": "5940.00"},
    {"faixa": 3, "rbt12_ate": "720000.00", "aliquota_nominal": "0.0950", "parcela_deduzir": "13860.00"},
    {"faixa": 4, "rbt12_ate": "1800000.00", "aliquota_nominal": "0.1070", "parcela_deduzir": "22500.00"},
    {"faixa": 5, "rbt12_ate": "3600000.00", "aliquota_nominal": "0.1430", "parcela_deduzir": "87300.00"},
    {"faixa": 6, "rbt12_ate": "4800000.00", "aliquota_nominal": "0.1900", "parcela_deduzir": "378000.00"},
])


def test_rbt12_negativo_levanta_erro() -> None:
    with pytest.raises(ValueError, match="rbt12"):
        calcular_das(Decimal("-1"), Decimal("1000"), _FAIXAS_I)


def test_receita_negativa_levanta_erro() -> None:
    with pytest.raises(ValueError, match="receita_mes"):
        calcular_das(Decimal("100000"), Decimal("-1"), _FAIXAS_I)


def test_faixas_vazias_levanta_erro() -> None:
    with pytest.raises(ValueError, match="faixas"):
        calcular_das(Decimal("100000"), Decimal("8000"), [])


def test_acima_teto_federal_levanta_excecao() -> None:
    """RBT12 > R$4,8M ⇒ empresa fora do Simples Nacional (LC 123 art. 3º II).

    Comportamento mudou em v2 (Fase 1.4): antes calculava silenciosamente
    usando a faixa 6; agora levanta EmpresaForaSimplesNacional.
    """
    with pytest.raises(EmpresaForaSimplesNacional, match="teto federal"):
        calcular_das(
            rbt12=Decimal("5000000.00"),
            receita_mes=Decimal("400000.00"),
            faixas=_FAIXAS_I,
        )


def test_no_teto_federal_exato_ainda_passa() -> None:
    """RBT12 = R$4,8M exato ⇒ ainda dentro do SN (LC 123 art. 3º II: 'superar')."""
    resultado = calcular_das(
        rbt12=Decimal("4800000.00"),
        receita_mes=Decimal("400000.00"),
        faixas=_FAIXAS_I,
    )
    assert resultado.faixa == 6


# ── Sublimite estadual (LC 123 art. 19) ──────────────────────────────────────


def test_abaixo_sublimite_padrao_nao_marca_excedido() -> None:
    resultado = calcular_das(
        rbt12=Decimal("3500000.00"),  # abaixo do sublimite padrão R$3,6M
        receita_mes=Decimal("300000.00"),
        faixas=_FAIXAS_I,
        uf="SP",
    )
    assert resultado.sublimite_excedido is False
    assert resultado.sublimite_aplicado == Decimal("3600000.00")
    assert resultado.uf == "SP"


def test_acima_sublimite_padrao_marca_excedido() -> None:
    """RBT12 > R$3,6M e <= R$4,8M ⇒ ICMS/ISS saem do DAS, flag marcada.

    Sistema continua calculando o DAS cheio (a decomposição por tributo da
    tabela CGSN ainda não está no schema — pendência Fase 5), mas sinaliza
    que o cliente deve recolher ICMS/ISS por fora.
    """
    resultado = calcular_das(
        rbt12=Decimal("3700000.00"),  # acima do sublimite padrão
        receita_mes=Decimal("310000.00"),
        faixas=_FAIXAS_I,
        uf="SP",
    )
    assert resultado.sublimite_excedido is True
    assert resultado.sublimite_aplicado == Decimal("3600000.00")


def test_sublimite_estadual_reduzido_aplicado() -> None:
    """Estados que optaram pelo sublimite reduzido R$1,8M (LC 123 art. 19 §1)."""
    resultado = calcular_das(
        rbt12=Decimal("2000000.00"),
        receita_mes=Decimal("180000.00"),
        faixas=_FAIXAS_I,
        uf="RR",
        sublimite_estadual=Decimal("1800000.00"),
    )
    assert resultado.sublimite_excedido is True
    assert resultado.sublimite_aplicado == Decimal("1800000.00")


def test_sublimite_default_quando_uf_nao_informada() -> None:
    """uf=None continua válido — sublimite_padrao é aplicado."""
    resultado = calcular_das(
        rbt12=Decimal("3500000.00"),
        receita_mes=Decimal("300000.00"),
        faixas=_FAIXAS_I,
    )
    assert resultado.uf is None
    assert resultado.sublimite_aplicado == Decimal("3600000.00")
    assert resultado.sublimite_excedido is False


# ── Fator R ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "fator_r,esperado",
    [
        (Decimal("0.28"), "III"),   # exatamente no limiar → Anexo III
        (Decimal("0.30"), "III"),   # acima → Anexo III
        (Decimal("0.2799"), "V"),   # abaixo → Anexo V
        (Decimal("0.10"), "V"),     # muito abaixo → Anexo V
    ],
)
def test_resolver_anexo_fator_r(fator_r: Decimal, esperado: str) -> None:
    resultado = resolver_anexo_fator_r("III", fator_r)
    assert resultado == esperado


def test_resolver_fator_r_anexo_invalido_levanta_erro() -> None:
    with pytest.raises(ValueError, match="Fator R"):
        resolver_anexo_fator_r("I", Decimal("0.30"))
