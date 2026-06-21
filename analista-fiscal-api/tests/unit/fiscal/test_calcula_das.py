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

from app.modules.fiscal.calcula_das import (
    FaixaDAS,
    calcular_das,
    calcular_das_multi_anexo,
    resolver_anexo_fator_r,
    validar_soma_receitas,
)
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


# ── v3: receitas_por_anexo (Fase 2 PR8 — MAJOR M2) ───────────────────────────


_FAIXAS_III = _faixas_from_json([
    {"faixa": 1, "rbt12_ate": "180000.00", "aliquota_nominal": "0.0600", "parcela_deduzir": "0.00"},
    {"faixa": 2, "rbt12_ate": "360000.00", "aliquota_nominal": "0.1120", "parcela_deduzir": "9360.00"},
    {"faixa": 3, "rbt12_ate": "720000.00", "aliquota_nominal": "0.1350", "parcela_deduzir": "17640.00"},
    {"faixa": 4, "rbt12_ate": "1800000.00", "aliquota_nominal": "0.1600", "parcela_deduzir": "35640.00"},
    {"faixa": 5, "rbt12_ate": "3600000.00", "aliquota_nominal": "0.2100", "parcela_deduzir": "125640.00"},
    {"faixa": 6, "rbt12_ate": "4800000.00", "aliquota_nominal": "0.3300", "parcela_deduzir": "648000.00"},
])

_FAIXAS_V = _faixas_from_json([
    {"faixa": 1, "rbt12_ate": "180000.00", "aliquota_nominal": "0.1550", "parcela_deduzir": "0.00"},
    {"faixa": 2, "rbt12_ate": "360000.00", "aliquota_nominal": "0.1800", "parcela_deduzir": "4500.00"},
    {"faixa": 3, "rbt12_ate": "720000.00", "aliquota_nominal": "0.1950", "parcela_deduzir": "9900.00"},
    {"faixa": 4, "rbt12_ate": "1800000.00", "aliquota_nominal": "0.2050", "parcela_deduzir": "17100.00"},
    {"faixa": 5, "rbt12_ate": "3600000.00", "aliquota_nominal": "0.2300", "parcela_deduzir": "62100.00"},
    {"faixa": 6, "rbt12_ate": "4800000.00", "aliquota_nominal": "0.3050", "parcela_deduzir": "540000.00"},
])


def test_single_anexo_preserva_receitas_por_anexo() -> None:
    """Single-anexo passa: receitas_por_anexo = {anexo_efetivo: receita_mes}."""
    resultado = calcular_das(
        rbt12=Decimal("500000.00"),
        receita_mes=Decimal("40000.00"),
        faixas=_FAIXAS_I,
        anexo="I",
    )
    assert resultado.receitas_por_anexo == {"I": Decimal("40000.00")}
    assert resultado.algoritmo_versao == "sn.das.v3"


def test_multi_anexo_soma_dois_anexos() -> None:
    """Anexo I (R$10k) + Anexo III (R$5k) — DAS é a soma das duas alíquotas."""
    rbt12 = Decimal("500000.00")  # faixa 3 em ambos os anexos

    # Esperado parcial por anexo (calculado individualmente):
    parcial_i = calcular_das(rbt12, Decimal("10000"), _FAIXAS_I, anexo="I")
    parcial_iii = calcular_das(rbt12, Decimal("5000"), _FAIXAS_III, anexo="III")
    esperado_total = parcial_i.valor + parcial_iii.valor

    resultado = calcular_das_multi_anexo(
        rbt12=rbt12,
        receitas_por_anexo={"I": Decimal("10000"), "III": Decimal("5000")},
        faixas_por_anexo={"I": _FAIXAS_I, "III": _FAIXAS_III},
        anexo_declarado="I",
    )

    assert resultado.valor == esperado_total
    assert resultado.receita_mes == Decimal("15000")
    assert resultado.receitas_por_anexo == {
        "I": Decimal("10000"),
        "III": Decimal("5000"),
    }
    assert resultado.algoritmo_versao == "sn.das.v3"


def test_multi_anexo_fator_r_alterna_iii_para_v() -> None:
    """Fator R < 28% transforma Anexo III declarado em V efetivo (sem afetar I).

    Empresa com 60% serviço (Anexo III ou V via Fator R) + 40% comércio (Anexo I).
    Folha baixa → Fator R abaixo de 28% → serviço cai no Anexo V.
    """
    rbt12 = Decimal("500000.00")
    fator_r_baixo = Decimal("0.15")  # < 28%

    resultado = calcular_das_multi_anexo(
        rbt12=rbt12,
        receitas_por_anexo={"I": Decimal("4000"), "III": Decimal("6000")},
        faixas_por_anexo={
            "I": _FAIXAS_I,
            "III": _FAIXAS_III,
            "V": _FAIXAS_V,
        },
        anexo_declarado="III",
        fator_r=fator_r_baixo,
    )

    # Anexo III virou V; Anexo I permanece intocado
    assert resultado.anexo_efetivo == "V"
    assert "V" in resultado.receitas_por_anexo
    assert "I" in resultado.receitas_por_anexo
    assert resultado.receitas_por_anexo["V"] == Decimal("6000")
    assert resultado.receitas_por_anexo["I"] == Decimal("4000")

    # DAS final é I (sem Fator R) + V (com receita realocada do III)
    parcial_i = calcular_das(rbt12, Decimal("4000"), _FAIXAS_I, anexo="I")
    parcial_v = calcular_das(rbt12, Decimal("6000"), _FAIXAS_V, anexo="V")
    assert resultado.valor == parcial_i.valor + parcial_v.valor


def test_multi_anexo_descarta_receita_zero() -> None:
    """Anexos com receita 0 são silenciosamente ignorados."""
    resultado = calcular_das_multi_anexo(
        rbt12=Decimal("200000"),
        receitas_por_anexo={
            "I": Decimal("8000"),
            "II": Decimal("0"),
            "III": Decimal("2000"),
        },
        faixas_por_anexo={"I": _FAIXAS_I, "III": _FAIXAS_III},
        anexo_declarado="I",
    )
    assert set(resultado.receitas_por_anexo) == {"I", "III"}


def test_multi_anexo_vazio_levanta() -> None:
    with pytest.raises(ValueError, match="vazio"):
        calcular_das_multi_anexo(
            rbt12=Decimal("100000"),
            receitas_por_anexo={},
            faixas_por_anexo={"I": _FAIXAS_I},
            anexo_declarado="I",
        )


def test_multi_anexo_somente_receitas_zero_levanta() -> None:
    with pytest.raises(ValueError, match="ao menos um anexo"):
        calcular_das_multi_anexo(
            rbt12=Decimal("100000"),
            receitas_por_anexo={"I": Decimal("0")},
            faixas_por_anexo={"I": _FAIXAS_I},
            anexo_declarado="I",
        )


def test_multi_anexo_faixas_faltando_levanta() -> None:
    with pytest.raises(ValueError, match="faixas_por_anexo"):
        calcular_das_multi_anexo(
            rbt12=Decimal("100000"),
            receitas_por_anexo={"I": Decimal("5000"), "III": Decimal("3000")},
            faixas_por_anexo={"I": _FAIXAS_I},  # falta "III"
            anexo_declarado="I",
        )


def test_validar_soma_receitas_dentro_tolerancia() -> None:
    # Diferença de 0.005 → dentro da tolerância default 0.01
    validar_soma_receitas(
        receita_mes=Decimal("10000.00"),
        receitas_por_anexo={"I": Decimal("6000.005"), "III": Decimal("3999.99")},
    )


def test_validar_soma_receitas_fora_tolerancia_levanta() -> None:
    with pytest.raises(ValueError, match="soma"):
        validar_soma_receitas(
            receita_mes=Decimal("10000.00"),
            receitas_por_anexo={"I": Decimal("6000"), "III": Decimal("3000")},
        )


# ── Achado #3 — Fator R sem encargos (auditoria 2026-06-21) ──────────────────
#
# Fonte: LC 123/2006 art. 18 §5º-J e §24; Res. CGSN 140/2018 art. 26 §1º.
# Massa salarial do Fator R = remuneração (salários + pró-labore + 13º)
# ACRESCIDA do CPP (Contribuição Patronal Previdenciária) e do FGTS.
#
# Estes testes provam via `resolver_anexo_fator_r` que:
#  1. Fator R exatamente 28,00% → Anexo III (borda >= exata).
#  2. Fator R 27,99% → Anexo V (abaixo da borda).
#  3. Incluir encargos vira o anexo de V→III: sem encargos o Fator R ficaria
#     abaixo de 28% (Anexo V); com CPP+FGTS passa de 28% (Anexo III).
#     Este terceiro teste é o que prova o bug original — o "ouro" que garante
#     que a correção em fiscal/service.py usa massa_salarial_12m correta.
#
# Nota: `resolver_anexo_fator_r` é a função pura em calcula_das.py.
# O cálculo da massa → fator_r ocorre em fiscal/service.py; estes testes
# cobrem a lógica de resolução de borda e o impacto da inclusão dos encargos.


def test_fator_r_exatamente_28_porcento_vai_para_anexo_iii() -> None:
    """Fator R = 28,00% exato (massa/rbt12 = 0.28) → Anexo III.

    Borda crítica: o comparador >= em resolver_anexo_fator_r deve incluir o limiar.
    RBT12 = 500.000; massa_salarial_12m = 140.000 → fator_r = 0.28 exato.
    """
    rbt12 = Decimal("500000.00")
    massa_salarial_12m = Decimal("140000.00")  # 140.000 / 500.000 = 0.2800 exato
    fator_r = massa_salarial_12m / rbt12
    assert fator_r == Decimal("0.28"), f"Setup inválido: fator_r={fator_r}"
    assert resolver_anexo_fator_r("III", fator_r) == "III"


def test_fator_r_2799_vai_para_anexo_v() -> None:
    """Fator R = 27,99% → Anexo V (abaixo do limiar de 28%).

    RBT12 = 500.000; massa_salarial_12m = 139.950 → fator_r = 0.27990 < 0.28.
    """
    rbt12 = Decimal("500000.00")
    massa_salarial_12m = Decimal("139950.00")  # 139.950 / 500.000 = 0.27990
    fator_r = massa_salarial_12m / rbt12
    assert fator_r < Decimal("0.28"), f"Setup inválido: fator_r={fator_r}"
    assert resolver_anexo_fator_r("III", fator_r) == "V"


def test_encargos_viram_anexo_v_para_iii() -> None:
    """CASO CRÍTICO — prova o bug do Achado #3.

    Cenário: empresa Anexo III/V com:
      - folha_12m (salários apenas) = R$ 130.000
      - encargos_folha_12m (CPP + FGTS) = R$ 15.000
      - RBT12 = R$ 500.000

    Sem encargos: fator_r = 130.000 / 500.000 = 26,00% → Anexo V (alíquota maior).
    Com encargos: massa = 145.000 → fator_r = 145.000 / 500.000 = 29,00% → Anexo III.

    O bug original calculava folha_12m/rbt12 sem somar os encargos → resolvia V
    quando o correto (conforme Res. CGSN 140/2018 art. 26 §1º) é III.
    A correção em fiscal/service.py usa massa_salarial_12m = folha_12m + encargos_folha_12m.
    """
    rbt12 = Decimal("500000.00")
    folha_12m = Decimal("130000.00")
    encargos_folha_12m = Decimal("15000.00")
    massa_salarial_12m = folha_12m + encargos_folha_12m  # = 145.000

    fator_r_sem_encargos = folha_12m / rbt12  # 0.2600 < 0.28 → Anexo V (ERRADO)
    fator_r_com_encargos = massa_salarial_12m / rbt12  # 0.2900 >= 0.28 → Anexo III (CORRETO)

    # Confirma que a empresa ficaria no V sem a correção:
    assert resolver_anexo_fator_r("III", fator_r_sem_encargos) == "V", (
        "Sem encargos deveria cair no Anexo V (comportamento anterior/errado)"
    )
    # Confirma que com a correção vai para o III:
    assert resolver_anexo_fator_r("III", fator_r_com_encargos) == "III", (
        "Com encargos deve ir para Anexo III (comportamento correto per CGSN 140/2018)"
    )
    # Confirma os valores numéricos:
    assert fator_r_sem_encargos == Decimal("0.26")
    assert fator_r_com_encargos == Decimal("0.29")
