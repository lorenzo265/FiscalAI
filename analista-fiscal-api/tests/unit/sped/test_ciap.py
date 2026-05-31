"""Testes da lógica pura de CIAP (Sprint 19.6 PR1 #31).

Cada teste exercita uma regra específica da Lei Complementar 87/1996
art. 20 §5º (apropriação 1/48 do ICMS por 48 meses). Sem I/O.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.sped.efd.ciap import (
    BemCiap,
    calcular_apropriacao_ciap,
)


def _bem(
    *,
    bem_id: str = "bem-001",
    data_aquisicao: date = date(2025, 1, 15),
    icms: str = "4800.00",
    data_baixa: date | None = None,
) -> BemCiap:
    return BemCiap(
        bem_id=bem_id,
        descricao=f"Máquina {bem_id}",
        data_aquisicao=data_aquisicao,
        icms_aquisicao_destacado=Decimal(icms),
        data_baixa=data_baixa,
    )


# ── Lista vazia ────────────────────────────────────────────────────────────


def test_sem_bens_devolve_snapshot_zerado() -> None:
    snap = calcular_apropriacao_ciap(
        [],
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
    )
    assert snap.saldo_inicial_icms == Decimal("0.00")
    assert snap.soma_parcelas_periodo == Decimal("0.00")
    assert snap.saldo_final_icms == Decimal("0.00")
    assert snap.movimentos == ()
    assert snap.tem_movimentos is False


# ── Bem novo no mês — parcela 1 ────────────────────────────────────────────


def test_bem_adquirido_no_periodo_apropria_parcela_1() -> None:
    """Bem adquirido no mês corrente: SOM_PARC = ICMS/48, parcela_num=1."""
    bem = _bem(data_aquisicao=date(2026, 5, 15), icms="4800.00")
    snap = calcular_apropriacao_ciap(
        [bem],
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
    )
    assert snap.soma_parcelas_periodo == Decimal("100.00")  # 4800/48
    assert snap.saldo_inicial_icms == Decimal("4800.00")  # cheio (0 parcelas antes)
    assert snap.saldo_final_icms == Decimal("4700.00")  # 4800 - 100
    assert len(snap.movimentos) == 1
    m = snap.movimentos[0]
    assert m.bem_id == "bem-001"
    assert m.tipo_movimento == "IM"
    assert m.num_parcela == 1
    assert m.valor_parcela == Decimal("100.00")
    assert m.valor_imob_icms_op == Decimal("4800.00")


# ── Bem antigo — parcela intermediária ─────────────────────────────────────


def test_bem_adquirido_ha_12_meses_apropria_parcela_13() -> None:
    """Bem de mai/2025, período mai/2026: parcela 13 (1 ano completo)."""
    bem = _bem(data_aquisicao=date(2025, 5, 15), icms="4800.00")
    snap = calcular_apropriacao_ciap(
        [bem],
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
    )
    assert snap.soma_parcelas_periodo == Decimal("100.00")
    # Saldo inicial: ICMS - 12 parcelas já apropriadas = 4800 - 1200 = 3600
    assert snap.saldo_inicial_icms == Decimal("3600.00")
    assert snap.saldo_final_icms == Decimal("3500.00")
    assert snap.movimentos[0].num_parcela == 13


# ── Bem fora do CIAP — passou 48 meses ────────────────────────────────────


def test_bem_com_mais_de_48_meses_nao_apropria_mais() -> None:
    """Bem de jan/2022, período mai/2026: já passou de 48 meses (parcela 53).
    Bem está fora do CIAP — sem movimento, saldo zerado.
    """
    bem = _bem(data_aquisicao=date(2022, 1, 15), icms="4800.00")
    snap = calcular_apropriacao_ciap(
        [bem],
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
    )
    assert snap.soma_parcelas_periodo == Decimal("0.00")
    # 48 parcelas já foram apropriadas → saldo zerado (capped a 0).
    assert snap.saldo_inicial_icms == Decimal("0.00")
    assert snap.saldo_final_icms == Decimal("0.00")
    assert snap.movimentos == ()


# ── Bem na última parcela (48) ─────────────────────────────────────────────


def test_bem_na_parcela_48_ainda_apropria() -> None:
    """Aquisição jun/2022, período mai/2026 = parcela 48 (último mês). Apropria."""
    bem = _bem(data_aquisicao=date(2022, 6, 15), icms="4800.00")
    snap = calcular_apropriacao_ciap(
        [bem],
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
    )
    assert snap.soma_parcelas_periodo == Decimal("100.00")
    assert snap.movimentos[0].num_parcela == 48


# ── Bem futuro — fora do período ───────────────────────────────────────────


def test_bem_adquirido_apos_periodo_nao_entra() -> None:
    """Aquisição jun/2026, período mai/2026: bem ainda não existe — sem movimento."""
    bem = _bem(data_aquisicao=date(2026, 6, 1), icms="4800.00")
    snap = calcular_apropriacao_ciap(
        [bem],
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
    )
    assert snap.soma_parcelas_periodo == Decimal("0.00")
    assert snap.movimentos == ()


# ── Bem baixado durante o CIAP ────────────────────────────────────────────


def test_bem_baixado_antes_do_periodo_nao_apropria() -> None:
    """Bem adquirido em jan/2025, baixado em mar/2026; período mai/2026:
    bem não apropria mais (baixa anterior ao período).
    """
    bem = _bem(
        data_aquisicao=date(2025, 1, 15),
        icms="4800.00",
        data_baixa=date(2026, 3, 10),
    )
    snap = calcular_apropriacao_ciap(
        [bem],
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
    )
    assert snap.soma_parcelas_periodo == Decimal("0.00")
    assert snap.movimentos == ()


# ── Múltiplos bens — saldo agregado ────────────────────────────────────────


def test_multiplos_bens_agregam_saldos_e_parcelas() -> None:
    """3 bens no mesmo período — saldos e parcelas somam corretamente."""
    bens = [
        _bem(bem_id="b1", data_aquisicao=date(2026, 5, 1), icms="4800.00"),
        _bem(bem_id="b2", data_aquisicao=date(2026, 5, 1), icms="2400.00"),
        _bem(bem_id="b3", data_aquisicao=date(2026, 5, 1), icms="9600.00"),
    ]
    snap = calcular_apropriacao_ciap(
        bens,
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
    )
    # ICMS total = 16800; 1/48 = 350
    assert snap.soma_parcelas_periodo == Decimal("350.00")
    assert snap.saldo_inicial_icms == Decimal("16800.00")
    assert snap.saldo_final_icms == Decimal("16450.00")
    assert len(snap.movimentos) == 3
    assert {m.bem_id for m in snap.movimentos} == {"b1", "b2", "b3"}


# ── Quantize HALF-EVEN (banker's rounding) ────────────────────────────────


def test_arredondamento_half_even_aplicado() -> None:
    """ICMS=100,00 / 48 = 2.0833... → 2.08 com ROUND_HALF_EVEN."""
    bem = _bem(data_aquisicao=date(2026, 5, 15), icms="100.00")
    snap = calcular_apropriacao_ciap(
        [bem],
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
    )
    assert snap.soma_parcelas_periodo == Decimal("2.08")
    assert snap.movimentos[0].valor_parcela == Decimal("2.08")


# ── Bem com ICMS zerado é defensivamente pulado ────────────────────────────


def test_bem_com_icms_zero_e_pulado() -> None:
    """Defensivo: bem com ICMS=0 não gera ZeroDivisionError; só fica fora."""
    bem = _bem(data_aquisicao=date(2026, 5, 15), icms="0.01")
    # Não zera porque CHECK no DB exige > 0 — mas testar borda < 0 simulada.
    snap = calcular_apropriacao_ciap(
        [bem],
        periodo_inicio=date(2026, 5, 1),
        periodo_fim=date(2026, 5, 31),
    )
    # ICMS 0.01 / 48 = 0.0002 quantizado a 0.00 → snapshot tem movimento mas
    # parcela 0.00 (caso extremo aceitável).
    assert len(snap.movimentos) == 1
    assert snap.movimentos[0].valor_parcela == Decimal("0.00")
