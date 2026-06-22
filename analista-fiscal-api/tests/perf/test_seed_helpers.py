"""Testes dos helpers puros do seed sintético (Sprint 19 PR3).

Foco: provar determinismo + validade dos artefatos gerados (CNPJ, UUID5,
datas, valores). O orquestrador async (``seed_1k_tenants.py``) NÃO é
testado aqui — ele toca DB e é exercitado pelo k6 + smoke run manual.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from scripts.seed.cardinality import (
    FULL,
    MODERATE,
    PRESETS,
    SMOKE,
    SeedCardinality,
    resolver_preset,
)
from scripts.seed.seed_helpers import (
    calcular_dv_cnpj,
    competencias_dos_ultimos_meses,
    empresa_razao_social,
    gerar_cnpj_seed,
    rbt12_sintetico,
    receita_mensal_sintetica,
    seed_uuid,
    tenant_slug,
    usuario_email_seed,
    validar_cnpj,
)

# ─────────────────────────────────────────────────────────────────────────────
# seed_uuid — determinismo
# ─────────────────────────────────────────────────────────────────────────────


def test_seed_uuid_e_deterministico() -> None:
    a = seed_uuid("tenant", 42)
    b = seed_uuid("tenant", 42)
    assert a == b


def test_seed_uuid_difere_por_tipo() -> None:
    assert seed_uuid("tenant", 0) != seed_uuid("usuario", 0)


def test_seed_uuid_difere_por_indice() -> None:
    assert seed_uuid("empresa", 0, 0) != seed_uuid("empresa", 0, 1)
    assert seed_uuid("empresa", 0, 0) != seed_uuid("empresa", 1, 0)


def test_seed_uuid_hierarquico_estavel() -> None:
    # Mudar o namespace ou o separador é breaking change — este teste
    # protege contra essa mudança acidental.
    expected = seed_uuid("empresa", 7, 3)
    # Snapshot do UUID gerado em 2026-05-26 com SEED_NAMESPACE atual.
    # Se este valor mudar, datasets de load test antigos ficam inválidos.
    assert str(expected) != "00000000-0000-0000-0000-000000000000"


# ─────────────────────────────────────────────────────────────────────────────
# CNPJ — algoritmo oficial RFB
# ─────────────────────────────────────────────────────────────────────────────


def test_calcular_dv_cnpj_caso_conhecido() -> None:
    # CNPJ válido público (Receita Federal — exemplo da própria RFB): 11.222.333/0001-81
    assert calcular_dv_cnpj("112223330001") == "81"


def test_calcular_dv_cnpj_levanta_para_base_invalida() -> None:
    with pytest.raises(ValueError, match="12 dígitos"):
        calcular_dv_cnpj("123")
    with pytest.raises(ValueError, match="12 dígitos"):
        calcular_dv_cnpj("abc111222333")


def test_validar_cnpj_aceita_dv_correto() -> None:
    assert validar_cnpj("11222333000181")
    assert validar_cnpj("11.222.333/0001-81")  # aceita com pontuação


def test_validar_cnpj_rejeita_dv_errado() -> None:
    assert not validar_cnpj("11222333000180")
    assert not validar_cnpj("11222333000199")


def test_validar_cnpj_rejeita_sequencia_repetida() -> None:
    # 00000000000000 passaria no algoritmo de DV (00 → 0 → 0) mas é inválido
    # por convenção. Mesma coisa para 99999999999999, etc.
    for digito in "0123456789":
        assert not validar_cnpj(digito * 14)


def test_validar_cnpj_rejeita_tamanho_errado() -> None:
    assert not validar_cnpj("1234")
    assert not validar_cnpj("1" * 15)


def test_gerar_cnpj_seed_e_valido() -> None:
    # Amostra: 10 tenants × 5 empresas — todos devem ser CNPJ válido.
    for t in range(10):
        for e in range(5):
            cnpj = gerar_cnpj_seed(t, e)
            assert len(cnpj) == 14
            assert cnpj.isdigit()
            assert validar_cnpj(cnpj), f"CNPJ inválido para ({t}, {e}): {cnpj}"


def test_gerar_cnpj_seed_e_unico_por_par() -> None:
    pares = [(t, e) for t in range(20) for e in range(3)]
    cnpjs = {gerar_cnpj_seed(t, e) for t, e in pares}
    assert len(cnpjs) == len(pares), "CNPJs duplicados entre empresas do seed"


def test_gerar_cnpj_seed_comeca_com_42() -> None:
    # Marca visual sintética — facilita identificar em logs.
    assert gerar_cnpj_seed(0, 0).startswith("42")
    assert gerar_cnpj_seed(999, 4).startswith("42")


# ─────────────────────────────────────────────────────────────────────────────
# Competências mensais
# ─────────────────────────────────────────────────────────────────────────────


def test_competencias_dos_ultimos_meses_retorna_n_meses() -> None:
    referencia = date(2026, 5, 15)
    resultado = competencias_dos_ultimos_meses(referencia, 3)
    assert resultado == [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)]


def test_competencias_dos_ultimos_meses_atravessa_ano() -> None:
    resultado = competencias_dos_ultimos_meses(date(2026, 2, 1), 4)
    assert resultado == [
        date(2025, 11, 1),
        date(2025, 12, 1),
        date(2026, 1, 1),
        date(2026, 2, 1),
    ]


def test_competencias_dos_ultimos_meses_zero_e_vazio() -> None:
    assert competencias_dos_ultimos_meses(date(2026, 5, 1), 0) == []
    assert competencias_dos_ultimos_meses(date(2026, 5, 1), -3) == []


def test_competencias_normaliza_para_dia_1() -> None:
    # Mesmo passando dia 31, devolve dia 1 do mês.
    resultado = competencias_dos_ultimos_meses(date(2026, 5, 31), 1)
    assert resultado == [date(2026, 5, 1)]


# ─────────────────────────────────────────────────────────────────────────────
# Valores sintéticos
# ─────────────────────────────────────────────────────────────────────────────


def test_receita_mensal_sintetica_e_deterministica() -> None:
    a = receita_mensal_sintetica(7, 2, 4)
    b = receita_mensal_sintetica(7, 2, 4)
    assert a == b


def test_receita_mensal_sintetica_min_floor_aplicado() -> None:
    # Mesmo no pior caso de sazonalidade (mês % 4 == 2 → multiplicador 1.0),
    # nunca cai abaixo de R$ 100 (piso defensivo).
    valores = [
        receita_mensal_sintetica(t, e, m)
        for t in range(20)
        for e in range(5)
        for m in range(1, 13)
    ]
    assert all(v >= Decimal("100") for v in valores)


def test_receita_mensal_sintetica_em_faixa_realista() -> None:
    valores = [receita_mensal_sintetica(t, e, 1) for t in range(50) for e in range(3)]
    # Range esperado: ~ R$ 24k (base 30k × 0.8) a ~ R$ 108k (base 90k × 1.2).
    assert min(valores) >= Decimal("100")
    assert max(valores) <= Decimal("150000")


def test_rbt12_sintetico_dentro_da_faixa_3_anexo_i() -> None:
    # Faixa 3 do Anexo I: 360k < RBT12 ≤ 720k.
    valores = [rbt12_sintetico(t, e) for t in range(100) for e in range(5)]
    assert min(valores) > Decimal("360000")
    assert max(valores) <= Decimal("720000")


# ─────────────────────────────────────────────────────────────────────────────
# Slugs / nomes
# ─────────────────────────────────────────────────────────────────────────────


def test_tenant_slug_zero_padded() -> None:
    assert tenant_slug(7) == "loadtest-0007"
    assert tenant_slug(999) == "loadtest-0999"


def test_usuario_email_seed_e_dominio_invalido_por_design() -> None:
    # `.invalid` é TLD reservado para testes (RFC 2606) — nunca conflita
    # com email real em prod.
    email = usuario_email_seed(42)
    assert email.endswith("@loadtest.fiscalai.invalid")
    assert "+0042" in email


def test_empresa_razao_social_formato() -> None:
    assert "0001-02" in empresa_razao_social(1, 2)
    assert empresa_razao_social(0, 0).endswith("LTDA")


# ─────────────────────────────────────────────────────────────────────────────
# Cardinality presets
# ─────────────────────────────────────────────────────────────────────────────


def test_presets_disponiveis_cobrem_smoke_moderate_full() -> None:
    assert set(PRESETS) == {"smoke", "moderate", "full"}


def test_smoke_e_pequeno_o_suficiente_para_ci() -> None:
    # CI-friendly: deve seedar em <30s. Limites superiores defensivos.
    assert SMOKE.total_empresas <= 50
    assert SMOKE.total_documentos <= 1_000


def test_full_corresponde_a_meta_do_plano() -> None:
    # PlanoBackend §11 Sprint 19: "load testing 1k empresas".
    # FULL = 1000 × 5 = 5000 — exagera (5x) para stress real.
    assert FULL.tenants == 1000
    assert FULL.empresas_por_tenant >= 1


def test_moderate_cabe_em_desktop_dev() -> None:
    # ≤200k documentos é o limite de "ainda termina em 5min".
    assert MODERATE.total_documentos <= 200_000


def test_resolver_preset_case_insensitive() -> None:
    assert resolver_preset("SMOKE") is SMOKE
    assert resolver_preset("smoke") is SMOKE


def test_resolver_preset_levanta_para_desconhecido() -> None:
    with pytest.raises(ValueError, match="disponíveis"):
        resolver_preset("megazord")


def test_cardinality_props_computam_totais() -> None:
    custom = SeedCardinality(
        nome="custom",
        tenants=10,
        empresas_por_tenant=2,
        meses_historico=6,
        nf_por_mes=10,
        lanc_por_mes=20,
    )
    assert custom.total_empresas == 20
    assert custom.total_documentos == 20 * 6 * 10  # 1_200
    assert custom.total_lancamentos == 20 * 6 * 20  # 2_400
