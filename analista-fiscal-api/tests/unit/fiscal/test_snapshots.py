"""Testes do discriminator de `apuracao_fiscal.output_jsonb`.

Cobertura por tipo + retro-compat (versão v1 do IRPJ sem `irpj_devido`).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.fiscal.snapshots import (
    CsllLpSnapshot,
    DasSnapshot,
    IcmsSnapshot,
    IrpjLpSnapshot,
    IssSnapshot,
    PisCofinsSnapshot,
    parse_apuracao_output,
)


def test_parse_das_snapshot() -> None:
    snap = parse_apuracao_output(
        "das",
        {
            "valor": "1500.00",
            "aliquota_efetiva": "0.0728",
            "receita_mes": "20600.00",
            "rbt12": "247200.00",
            "anexo_efetivo": "III",
        },
    )
    assert isinstance(snap, DasSnapshot)
    assert snap.valor_devido == Decimal("1500.00")
    assert snap.base_calculo is None


def test_parse_irpj_lp_v2_com_irrf() -> None:
    """v2 (Fase 1.5/1.6) — IRRF a compensar + irpj_devido separado."""
    snap = parse_apuracao_output(
        "irpj",
        {
            "irpj_total": "9000.00",
            "irpj_devido": "8500.00",
            "irrf_consumido": "500.00",
            "irrf_saldo_credor": "0",
            "base_total": "60000.00",
            "base_presumida": "60000.00",
            "receita_bruta_trimestre": "500000.00",
            "meses_periodo": 3,
        },
    )
    assert isinstance(snap, IrpjLpSnapshot)
    # DRE usa valor_devido = irpj_total (despesa accrued)
    assert snap.valor_devido == Decimal("9000.00")
    # Fluxo de caixa usa valor_caixa = irpj_devido (saída efetiva)
    assert snap.valor_caixa == Decimal("8500.00")
    assert snap.base_calculo == Decimal("60000.00")


def test_parse_irpj_lp_v1_legado_sem_irpj_devido() -> None:
    """v1 legado — só `irpj_total`. `valor_caixa` cai pra `irpj_total`."""
    snap = parse_apuracao_output(
        "irpj",
        {
            "irpj_total": "7500.00",
            "base_total": "50000.00",
        },
    )
    assert isinstance(snap, IrpjLpSnapshot)
    assert snap.valor_devido == Decimal("7500.00")
    assert snap.valor_caixa == Decimal("7500.00")  # fallback


def test_parse_csll_lp() -> None:
    snap = parse_apuracao_output(
        "csll",
        {
            "csll": "5400.00",
            "base_total": "60000.00",
            "receita_bruta_trimestre": "500000.00",
        },
    )
    assert isinstance(snap, CsllLpSnapshot)
    assert snap.valor_devido == Decimal("5400.00")
    assert snap.base_calculo == Decimal("60000.00")


def test_parse_pis_cumulativo() -> None:
    snap = parse_apuracao_output(
        "pis",
        {
            "tributo": "650.00",
            "base_calculo": "100000.00",
            "aliquota": "0.0065",
            "receita_bruta": "100000.00",
            "exclusoes": "0",
        },
    )
    assert isinstance(snap, PisCofinsSnapshot)
    assert snap.tipo == "pis"
    assert snap.valor_devido == Decimal("650.00")
    assert snap.base_calculo == Decimal("100000.00")


def test_parse_cofins_cumulativo() -> None:
    snap = parse_apuracao_output(
        "cofins",
        {"tributo": "3000.00", "base_calculo": "100000.00"},
    )
    assert isinstance(snap, PisCofinsSnapshot)
    assert snap.tipo == "cofins"
    assert snap.valor_devido == Decimal("3000.00")


def test_parse_icms() -> None:
    snap = parse_apuracao_output(
        "icms",
        {
            "icms_a_recolher": "850.00",
            "saldo_credor_a_transportar": "0",
            "debito": "1500.00",
            "credito": "650.00",
            "uf": "SP",
        },
    )
    assert isinstance(snap, IcmsSnapshot)
    assert snap.valor_devido == Decimal("850.00")
    assert snap.base_calculo is None


def test_parse_iss_legado_fallback_input() -> None:
    """ISS antigo: output sem `iss`; fallback usa input.valor."""
    snap = parse_apuracao_output(
        "iss",
        {},  # output vazio
        input_jsonb={"valor": "500.00"},
    )
    assert isinstance(snap, IssSnapshot)
    assert snap.valor_devido == Decimal("500.00")


def test_parse_iss_output_preenchido() -> None:
    snap = parse_apuracao_output("iss", {"iss": "300.00"})
    assert isinstance(snap, IssSnapshot)
    assert snap.valor_devido == Decimal("300.00")


def test_parse_tipo_desconhecido_retorna_zero() -> None:
    """Tipo novo não modelado: fallback genérico, valor=0."""
    snap = parse_apuracao_output("ipi_2030", {"campo_qualquer": "1234.56"})
    assert snap.valor_devido == Decimal("0")
    assert snap.base_calculo is None


def test_parse_payload_corrompido_retorna_zero() -> None:
    """Payload inválido (campo obrigatório ausente): não levanta — retorna 0."""
    snap = parse_apuracao_output("irpj", {})  # sem irpj_total
    assert snap.valor_devido == Decimal("0")


def test_extra_field_eh_ignorado() -> None:
    """Versão futura com campo novo não quebra parse retroativo."""
    snap = parse_apuracao_output(
        "csll",
        {
            "csll": "1000.00",
            "base_total": "10000.00",
            "campo_v2_futuro": "qualquer coisa",
        },
    )
    assert isinstance(snap, CsllLpSnapshot)
    assert snap.valor_devido == Decimal("1000.00")


def test_decimal_aceito_como_string_ou_decimal() -> None:
    """`output_jsonb` pode vir com strings (via _stringify) ou Decimals."""
    snap_str = parse_apuracao_output("das", {"valor": "100.00"})
    snap_dec = parse_apuracao_output("das", {"valor": Decimal("100.00")})
    assert snap_str.valor_devido == snap_dec.valor_devido == Decimal("100.00")


@pytest.mark.parametrize(
    "tipo,payload,esperado",
    [
        ("das", {"valor": "1500.00"}, Decimal("1500.00")),
        ("irpj", {"irpj_total": "9000.00"}, Decimal("9000.00")),
        ("csll", {"csll": "5400.00"}, Decimal("5400.00")),
        ("pis", {"tributo": "650.00"}, Decimal("650.00")),
        ("cofins", {"tributo": "3000.00"}, Decimal("3000.00")),
        ("icms", {"icms_a_recolher": "850.00"}, Decimal("850.00")),
    ],
)
def test_valor_devido_normalizado_por_tipo(
    tipo: str, payload: dict[str, str], esperado: Decimal
) -> None:
    snap = parse_apuracao_output(tipo, payload)
    assert snap.valor_devido == esperado
