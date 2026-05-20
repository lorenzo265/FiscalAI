"""Golden tests — cálculo de multa e juros de mora (Lei 9.430/1996, art. 61, §2º).

Cada caso é derivado das regras da RFB / Sicalc:
  - Multa: 0,33%/dia, teto 20% (atingido no ~61º dia)
  - Juros: SELIC acumulada (meses cheios pós-vencimento, não compostos)
  - Acréscimo mês pagamento: 1% fixo

Denúncia espontânea (CTN art. 138): sem multa, apenas SELIC + 1%.

Todos os valores calculados manualmente via Decimal antes de serem usados como golden.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.multa_juros.calcula_selic import (
    ResultadoMora,
    calcular_denuncia_espontanea,
    calcular_mora,
)

# Taxa SELIC fixa para testes determinísticos
_SELIC_FIXED = Decimal("0.0119")  # ~14,75% a.a.

_TAXA_PADRAO: list[tuple[date, Decimal]] = [
    (date(2025, m, 1), _SELIC_FIXED)
    for m in range(1, 13)
] + [
    (date(2026, m, 1), _SELIC_FIXED)
    for m in range(1, 7)
]


def _mora(
    valor: str,
    venc: date,
    pgto: date,
    taxas: list[tuple[date, Decimal]] | None = None,
) -> ResultadoMora:
    return calcular_mora(
        valor=Decimal(valor),
        data_vencimento=venc,
        data_pagamento=pgto,
        taxas_selic=taxas or _TAXA_PADRAO,
    )


def _espontanea(
    valor: str,
    venc: date,
    pgto: date,
    taxas: list[tuple[date, Decimal]] | None = None,
) -> ResultadoMora:
    return calcular_denuncia_espontanea(
        valor=Decimal(valor),
        data_vencimento=venc,
        data_pagamento=pgto,
        taxas_selic=taxas or _TAXA_PADRAO,
    )


# ── Caso base: sem atraso ────────────────────────────────────────────────────


def test_sem_atraso_zero_acrescimos() -> None:
    r = _mora("1000.00", date(2025, 5, 20), date(2025, 5, 20))
    assert r.dias_atraso == 0
    assert r.multa_mora == Decimal("0")
    assert r.juros_selic == Decimal("0")
    assert r.acrescimo_mes_pagamento == Decimal("0")
    assert r.total_acrescimos == Decimal("0")
    assert r.valor_atualizado == Decimal("1000.00")


# ── Multa de mora ────────────────────────────────────────────────────────────


def test_multa_5_dias_dentro_mesmo_mes() -> None:
    """5 dias de atraso no mesmo mês: multa = 5 × 0,33% = 1,65%; juros 0 (sem mês cheio).
    Acréscimo mês pagamento: 1%.
    """
    r = _mora("1000.00", date(2025, 5, 20), date(2025, 5, 25))
    assert r.dias_atraso == 5
    assert r.aliquota_multa == Decimal("0.0165")
    assert r.multa_mora == Decimal("16.50")
    assert r.meses_selic == 0
    assert r.juros_selic == Decimal("0.00")
    assert r.acrescimo_mes_pagamento == Decimal("10.00")
    assert r.valor_atualizado == Decimal("1026.50")


def test_multa_teto_20_porcento() -> None:
    """61 dias ≥ (20% / 0,33%) ≈ 60,6 dias → teto 20%."""
    r = _mora("1000.00", date(2025, 1, 1), date(2025, 3, 3))  # 61 dias
    assert r.aliquota_multa == Decimal("0.20")
    assert r.multa_mora == Decimal("200.00")


def test_multa_exatamente_60_dias() -> None:
    """60 dias × 0,33% = 19,80% < 20% → não aplica teto."""
    r = _mora("1000.00", date(2025, 1, 1), date(2025, 3, 2))  # 60 dias
    assert r.aliquota_multa == Decimal("0.1980")
    assert r.multa_mora == Decimal("198.00")


# ── Juros SELIC ──────────────────────────────────────────────────────────────


def test_atraso_1_mes_zero_meses_selic_cheios() -> None:
    """Vence em 20/mai; paga em 20/jun.
    Mês seguinte ao vencimento = jun; mês do pagamento = jun.
    Intervalo cheio: jun < jun → 0 meses SELIC (Sicalc só conta meses completos).
    Só o acréscimo fixo de 1%.
    """
    r = _mora("1000.00", date(2025, 5, 20), date(2025, 6, 20))
    assert r.dias_atraso == 31
    assert r.meses_selic == 0
    assert r.juros_selic == Decimal("0.00")
    assert r.acrescimo_mes_pagamento == Decimal("10.00")


def test_atraso_2_meses_1_mes_selic_cheio() -> None:
    """Vence em 20/mai; paga em 20/jul.
    Mês seguinte = jun; mês pagamento = jul.
    Meses cheios: jun < jul → 1 mês (jun). SELIC: 1 × 0,0119 = 1,19%.
    """
    r = _mora("1000.00", date(2025, 5, 20), date(2025, 7, 20))
    assert r.meses_selic == 1
    assert r.aliquota_juros_acumulada == Decimal("0.0119")
    assert r.juros_selic == Decimal("11.90")


def test_atraso_3_meses_2_meses_selic_cheios() -> None:
    """Vence em 20/mai; paga em 20/ago.
    Meses cheios: jun, jul (2 meses). Acréscimo: 1%.
    """
    r = _mora("1000.00", date(2025, 5, 20), date(2025, 8, 20))
    assert r.meses_selic == 2
    assert r.aliquota_juros_acumulada == Decimal("0.0238")
    assert r.juros_selic == Decimal("23.80")
    assert r.acrescimo_mes_pagamento == Decimal("10.00")


# ── Caso completo: multa no teto + vários meses SELIC ────────────────────────


def test_caso_completo_multa_teto_3_meses_selic() -> None:
    """Valor R$500; vence 01/jan/2025; paga 15/abr/2025.
    Dias: 104 → multa = teto 20% = R$100,00
    Meses cheios: fev, mar (2). SELIC: 2 × 0,0119 = 0,0238 → R$11,90
    Acréscimo: 1% = R$5,00
    Total acréscimos: R$116,90; valor atualizado: R$616,90
    """
    r = _mora("500.00", date(2025, 1, 1), date(2025, 4, 15))
    assert r.dias_atraso == 104
    assert r.aliquota_multa == Decimal("0.20")
    assert r.multa_mora == Decimal("100.00")
    assert r.meses_selic == 2
    assert r.juros_selic == Decimal("11.90")
    assert r.acrescimo_mes_pagamento == Decimal("5.00")
    assert r.total_acrescimos == Decimal("116.90")
    assert r.valor_atualizado == Decimal("616.90")


# ── Denúncia espontânea (CTN art. 138) ───────────────────────────────────────


def test_denuncia_espontanea_sem_multa() -> None:
    """Denúncia espontânea: multa zero; SELIC e 1% mantidos."""
    r = _espontanea("1000.00", date(2025, 1, 1), date(2025, 4, 15))
    assert r.multa_mora == Decimal("0")
    assert r.aliquota_multa == Decimal("0")
    # SELIC: fev + mar = 2 × 0,0119; acréscimo 1%
    assert r.meses_selic == 2
    assert r.juros_selic == Decimal("23.80")
    assert r.acrescimo_mes_pagamento == Decimal("10.00")
    assert r.total_acrescimos == Decimal("33.80")
    assert r.valor_atualizado == Decimal("1033.80")


def test_denuncia_espontanea_sem_atraso_zero_tudo() -> None:
    """Denúncia espontânea no prazo: sem acréscimo nenhum."""
    r = _espontanea("500.00", date(2025, 5, 20), date(2025, 5, 20))
    assert r.multa_mora == Decimal("0")
    assert r.juros_selic == Decimal("0")
    assert r.total_acrescimos == Decimal("0")
    assert r.valor_atualizado == Decimal("500.00")


def test_denuncia_espontanea_vs_mora_mesmos_juros() -> None:
    """Juros e acréscimo mês devem ser iguais; mora tem multa extra."""
    mora = _mora("2000.00", date(2025, 3, 20), date(2025, 7, 20))
    espont = _espontanea("2000.00", date(2025, 3, 20), date(2025, 7, 20))
    assert espont.juros_selic == mora.juros_selic
    assert espont.acrescimo_mes_pagamento == mora.acrescimo_mes_pagamento
    assert mora.multa_mora > Decimal("0")
    assert espont.multa_mora == Decimal("0")
    assert espont.valor_atualizado < mora.valor_atualizado


# ── Erro: pagamento anterior ao vencimento ────────────────────────────────────


def test_erro_pagamento_anterior_a_vencimento() -> None:
    with pytest.raises(ValueError, match="anterior a data_vencimento"):
        _mora("1000.00", date(2025, 5, 20), date(2025, 5, 19))


# ── SELIC insuficiente ────────────────────────────────────────────────────────


def test_erro_selic_insuficiente() -> None:
    """Pagamento requer mês sem SELIC na tabela."""
    taxas_parciais = [(date(2025, 1, 1), Decimal("0.0119"))]
    with pytest.raises(ValueError, match="Taxa SELIC não disponível"):
        _mora("1000.00", date(2024, 12, 20), date(2025, 3, 20), taxas=taxas_parciais)


# ── Invariantes ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("dias", [1, 10, 30, 60, 90, 180])
def test_total_acrescimos_coerente(dias: int) -> None:
    """total_acrescimos == multa + juros + acréscimo mês; valor_atualizado = valor + total."""
    from datetime import timedelta

    venc = date(2025, 1, 20)
    pgto = venc + timedelta(days=dias)

    # Garante SELIC disponível para todos os meses do período
    meses_necessarios = set()
    d = date(venc.year, venc.month + 1, 1) if venc.month < 12 else date(venc.year + 1, 1, 1)
    while d <= date(pgto.year, pgto.month, 1):
        meses_necessarios.add(d)
        d = date(d.year, d.month + 1, 1) if d.month < 12 else date(d.year + 1, 1, 1)
    taxas = [(m, Decimal("0.0119")) for m in sorted(meses_necessarios)]
    # Adiciona meses anteriores para completar
    taxas += [(date(2025, m, 1), Decimal("0.0119")) for m in range(1, 13) if date(2025, m, 1) not in dict(taxas)]

    r = calcular_mora(Decimal("1000.00"), venc, pgto, taxas)
    assert r.total_acrescimos == r.multa_mora + r.juros_selic + r.acrescimo_mes_pagamento
    assert r.valor_atualizado == r.valor_original + r.total_acrescimos
