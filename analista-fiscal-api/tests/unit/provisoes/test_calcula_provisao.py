"""Golden tests do algoritmo de provisão trabalhista (Sprint 8 PR2 / FA5-M8).

FA5 — Provisão regime-aware (M8, 2026-06-04):
  * ``calcular_provisoes`` agora aceita ``aliquota_inss_patronal`` explícita.
  * ``aliquota_patronal_regime`` encapsula a lógica regime+anexo.
  * SN Anexos I–III,V → aliq=0 (CPP no DAS; golden TestSNAnexoDesoneracao).
  * LP/LR/SN-IV → 20%+RAT+Terceiros (golden TestGoldenLPComRatTerceiros).
  * Default do parâmetro é ALIQ_CPP_BASE (0,20) — backward-compat.
    Resultado com default = resultado anterior (TestBackwardCompatCPPBase).
  * Versão bumped: prov-2026.07 → prov-2026.08.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.provisoes.calcula_provisao import (
    ALGORITMO_VERSAO,
    ALIQ_CPP_BASE,
    aliquota_patronal_regime,
    calcular_provisoes,
    inss_patronal_aplicavel,
)

# ── inss_patronal_aplicavel ─────────────────────────────────────────────────


class TestInssAplicavel:
    def test_lucro_presumido_aplica(self) -> None:
        assert inss_patronal_aplicavel("lucro_presumido") is True

    def test_lucro_real_aplica(self) -> None:
        assert inss_patronal_aplicavel("lucro_real") is True

    def test_simples_nacional_nao_aplica(self) -> None:
        # Nota: esta função retorna False para todo SN (sem distinção de anexo).
        # A distinção de Anexo IV é feita por aliquota_patronal_regime().
        assert inss_patronal_aplicavel("simples_nacional") is False

    def test_mei_nao_aplica(self) -> None:
        assert inss_patronal_aplicavel("mei") is False

    def test_case_insensitive(self) -> None:
        assert inss_patronal_aplicavel("Simples_Nacional") is False


# ── aliquota_patronal_regime ────────────────────────────────────────────────


class TestAliquotaPatronalRegime:
    """Testa a helper regime-aware que fornece a alíquota ao calcular_provisoes."""

    # MEI / SN Anexos I–V (exceto IV): alíquota = 0
    def test_mei_zero(self) -> None:
        assert aliquota_patronal_regime("mei") == Decimal("0")

    def test_sn_sem_anexo_zero(self) -> None:
        # SN sem anexo → assume desonerado (evita dupla contagem).
        assert aliquota_patronal_regime("simples_nacional") == Decimal("0")

    def test_sn_anexo_i_zero(self) -> None:
        assert aliquota_patronal_regime("simples_nacional", "I") == Decimal("0")

    def test_sn_anexo_ii_zero(self) -> None:
        assert aliquota_patronal_regime("simples_nacional", "II") == Decimal("0")

    def test_sn_anexo_iii_zero(self) -> None:
        assert aliquota_patronal_regime("simples_nacional", "III") == Decimal("0")

    def test_sn_anexo_v_zero(self) -> None:
        assert aliquota_patronal_regime("simples_nacional", "V") == Decimal("0")

    # SN Anexo IV: CPP fora do DAS → 20% base
    def test_sn_anexo_iv_cpp_base_sem_rat(self) -> None:
        resultado = aliquota_patronal_regime("simples_nacional", "IV")
        assert resultado == Decimal("0.20")

    def test_sn_anexo_iv_com_rat_e_terceiros(self) -> None:
        # RAT 2% + Terceiros 5,8% = 27,8% total
        resultado = aliquota_patronal_regime(
            "simples_nacional",
            "IV",
            rat_sat=Decimal("0.02"),
            aliquota_terceiros=Decimal("0.058"),
        )
        assert resultado == Decimal("0.278")

    # LP / LR
    def test_lp_cpp_base_sem_rat(self) -> None:
        resultado = aliquota_patronal_regime("lucro_presumido")
        assert resultado == Decimal("0.20")

    def test_lr_cpp_base_sem_rat(self) -> None:
        resultado = aliquota_patronal_regime("lucro_real")
        assert resultado == Decimal("0.20")

    def test_lp_com_rat_e_terceiros(self) -> None:
        # RAT 2% + Terceiros 5,8% = 27,8%
        resultado = aliquota_patronal_regime(
            "lucro_presumido",
            rat_sat=Decimal("0.02"),
            aliquota_terceiros=Decimal("0.058"),
        )
        assert resultado == Decimal("0.278")

    def test_lp_case_insensitive(self) -> None:
        resultado = aliquota_patronal_regime("Lucro_Presumido")
        assert resultado == Decimal("0.20")

    def test_sn_anexo_minusculo_normalizado(self) -> None:
        # Banco pode devolver "iv" em minúsculo por CHAR(1) trim.
        resultado = aliquota_patronal_regime("simples_nacional", "iv")
        assert resultado == Decimal("0.20")

    def test_sn_anexo_com_espacos(self) -> None:
        # CHAR(1) com espaço à direita (banco antigo).
        resultado = aliquota_patronal_regime("simples_nacional", " IV ")
        assert resultado == Decimal("0.20")


# ── Golden cases — Lucro Presumido piso 20% (backward-compat) ──────────────
# IMPORTANTE: estes valores usam o default ALIQ_CPP_BASE=0,20 (RAT=0, Terceiros=0).
# Representam o PISO conservador — a provisão correta para LP/LR incluirá
# RAT e Terceiros quando o seed estiver disponível (ver pendência rat-fap).
# O valor 222.22 para inss_ferias era o único valor na v07 — mantido com
# default para provar backward-compat, mas renomeado de "LP golden" para
# "piso 20%" a fim de não induzir a ideia de que 20% é suficiente para LP.


class TestBackwardCompatCPPBase:
    """Prova que chamar calcular_provisoes com default = ALIQ_CPP_BASE (0,20)
    produz EXATAMENTE o mesmo resultado que a v07 produzia.
    O golden v07 asseria inss_ferias=222.22 — preservado aqui."""

    def test_folha_10k_piso_20pct(self) -> None:
        r = calcular_provisoes(
            Decimal("10000.00"),
            "lucro_presumido",
            aliquota_inss_patronal=ALIQ_CPP_BASE,
        )
        # 1/12 de 10.000 = 833,33
        assert r.decimo_terceiro.valor_provisao == Decimal("833.33")
        # Férias: 833,33 + 277,78 = 1111,11
        assert r.ferias.valor_provisao == Decimal("1111.11")
        # INSS 20% sobre férias_total = 0,20 × 1111,11 = 222,22
        assert r.inss_ferias.valor_provisao == Decimal("222.22")
        assert r.inss_ferias.aliquota == ALIQ_CPP_BASE
        # INSS 20% sobre 13º = 0,20 × 833,33 = 166,67
        assert r.inss_13.valor_provisao == Decimal("166.67")
        # FGTS 8% sobre férias_total = 88,89
        assert r.fgts_ferias.valor_provisao == Decimal("88.89")
        # FGTS 8% sobre 13º = 66,67
        assert r.fgts_13.valor_provisao == Decimal("66.67")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_folha_10k_lp_sem_parametro_aliq(self) -> None:
        """Chamada sem aliquota_inss_patronal (omitido) = default = backward-compat."""
        r = calcular_provisoes(Decimal("10000.00"), "lucro_presumido")
        assert r.inss_ferias.valor_provisao == Decimal("222.22")
        assert r.inss_13.valor_provisao == Decimal("166.67")

    def test_folha_grande_30k_piso_20pct(self) -> None:
        r = calcular_provisoes(
            Decimal("30000.00"),
            "lucro_presumido",
            aliquota_inss_patronal=ALIQ_CPP_BASE,
        )
        assert r.decimo_terceiro.valor_provisao == Decimal("2500.00")
        assert r.ferias.valor_provisao == Decimal("3333.33")
        # INSS 20% × 3333,33 = 666,67 (ROUND_HALF_EVEN)
        assert r.inss_ferias.valor_provisao == Decimal("666.67")
        assert r.fgts_ferias.valor_provisao == Decimal("266.67")

    def test_folha_pequena_3k_piso_20pct(self) -> None:
        r = calcular_provisoes(
            Decimal("3000.00"),
            "lucro_presumido",
            aliquota_inss_patronal=ALIQ_CPP_BASE,
        )
        assert r.decimo_terceiro.valor_provisao == Decimal("250.00")
        assert r.ferias.valor_provisao == Decimal("333.33")
        assert r.inss_ferias.valor_provisao == Decimal("66.67")
        assert r.inss_13.valor_provisao == Decimal("50.00")
        assert r.fgts_ferias.valor_provisao == Decimal("26.67")
        assert r.fgts_13.valor_provisao == Decimal("20.00")


# ── Golden cases — LP / LR com RAT 2% + Terceiros 5,8% (encargo real) ──────
# RAT 2% × FAP 1,0 + Terceiros 5,8% = 27,8% total.
# Este é o encargo real típico de LP/LR para atividades não-beneficiadas.
# aliq_patronal = ALIQ_CPP_BASE + 0.02 + 0.058 = 0.278


class TestGoldenLPComRatTerceiros:
    """Golden com encargo previdenciário patronal completo: CPP 20% + RAT 2% + Terceiros 5,8%."""

    _ALIQ_278 = Decimal("0.278")

    def test_folha_10k_lp_278pct_ferias(self) -> None:
        """inss_ferias correto para LP com 27,8% encargo."""
        # ferias_total = 1111,11
        # 0,278 × 1111,11 = 308,8885... → ROUND_HALF_EVEN → 308,89
        r = calcular_provisoes(
            Decimal("10000.00"),
            "lucro_presumido",
            aliquota_inss_patronal=self._ALIQ_278,
        )
        assert r.inss_ferias.valor_provisao == Decimal("308.89")
        assert r.inss_ferias.aliquota == self._ALIQ_278

    def test_folha_10k_lp_278pct_13(self) -> None:
        """inss_13 correto para LP com 27,8% encargo."""
        # base_13 = 833,33
        # 0,278 × 833,33 = 231,6657... → ROUND_HALF_EVEN → 231.67
        r = calcular_provisoes(
            Decimal("10000.00"),
            "lucro_presumido",
            aliquota_inss_patronal=self._ALIQ_278,
        )
        assert r.inss_13.valor_provisao == Decimal("231.67")
        assert r.inss_13.aliquota == self._ALIQ_278

    def test_folha_10k_lp_278pct_ferias_13_fgts_inalterados(self) -> None:
        """Férias, 13º e FGTS NÃO mudam — só o INSS patronal."""
        r = calcular_provisoes(
            Decimal("10000.00"),
            "lucro_presumido",
            aliquota_inss_patronal=self._ALIQ_278,
        )
        # Férias e 13º não dependem da alíquota patronal
        assert r.ferias.valor_provisao == Decimal("1111.11")
        assert r.decimo_terceiro.valor_provisao == Decimal("833.33")
        # FGTS 8% — nunca muda por regime
        assert r.fgts_ferias.valor_provisao == Decimal("88.89")
        assert r.fgts_13.valor_provisao == Decimal("66.67")

    def test_via_aliquota_patronal_regime_lp(self) -> None:
        """Integração: aliquota_patronal_regime → calcular_provisoes produz 27,8%."""
        aliq = aliquota_patronal_regime(
            "lucro_presumido",
            rat_sat=Decimal("0.02"),
            aliquota_terceiros=Decimal("0.058"),
        )
        r = calcular_provisoes(
            Decimal("10000.00"),
            "lucro_presumido",
            aliquota_inss_patronal=aliq,
        )
        assert r.inss_ferias.valor_provisao == Decimal("308.89")
        assert r.inss_13.valor_provisao == Decimal("231.67")


# ── Golden cases — SN Anexo IV (CPP fora do DAS) ────────────────────────────


class TestSNAnexoIV:
    """SN Anexo IV recolhe CPP separada — deve provisionar como LP (20%+RAT+Terceiros)."""

    def test_sn_anexo_iv_piso_20pct(self) -> None:
        """SN Anexo IV com RAT=0 e Terceiros=0: provisiona igual ao piso LP."""
        aliq = aliquota_patronal_regime("simples_nacional", "IV")
        r = calcular_provisoes(
            Decimal("10000.00"),
            "simples_nacional",
            aliquota_inss_patronal=aliq,
        )
        # 20% × 1111,11 = 222,22 — mesmo que LP default
        assert r.inss_ferias.valor_provisao == Decimal("222.22")
        assert r.inss_13.valor_provisao == Decimal("166.67")

    def test_sn_anexo_iv_com_rat_terceiros(self) -> None:
        """SN Anexo IV com RAT 2% + Terceiros 5,8%."""
        aliq = aliquota_patronal_regime(
            "simples_nacional",
            "IV",
            rat_sat=Decimal("0.02"),
            aliquota_terceiros=Decimal("0.058"),
        )
        r = calcular_provisoes(
            Decimal("10000.00"),
            "simples_nacional",
            aliquota_inss_patronal=aliq,
        )
        assert r.inss_ferias.valor_provisao == Decimal("308.89")
        assert r.inss_13.valor_provisao == Decimal("231.67")
        # FGTS inalterado
        assert r.fgts_ferias.valor_provisao == Decimal("88.89")


# ── Golden cases — SN Anexos I/II/III/V (CPP desonerada = 0%) ───────────────


class TestSNAnexoDesoneracao:
    """SN Anexos I, II, III, V: CPP dentro do DAS → NÃO provisionar separado.

    Provisionar 20% seria DUPLA CONTAGEM (CPP já está no DAS).
    golden: inss_ferias == 0, inss_13 == 0.
    FGTS ainda incide normalmente.
    """

    def test_sn_anexo_iii_inss_zero(self) -> None:
        """Caso canônico: consultório (Anexo III) não recolhe CPP separada."""
        aliq = aliquota_patronal_regime("simples_nacional", "III")
        r = calcular_provisoes(
            Decimal("10000.00"),
            "simples_nacional",
            aliquota_inss_patronal=aliq,
        )
        assert r.inss_ferias.valor_provisao == Decimal("0.00")
        assert r.inss_ferias.aliquota == Decimal("0")
        assert r.inss_13.valor_provisao == Decimal("0.00")
        # FGTS inalterado — não é dispensado para SN
        assert r.fgts_ferias.valor_provisao == Decimal("88.89")
        assert r.fgts_13.valor_provisao == Decimal("66.67")
        # Férias e 13º inalterados
        assert r.ferias.valor_provisao == Decimal("1111.11")
        assert r.decimo_terceiro.valor_provisao == Decimal("833.33")

    def test_sn_anexo_i_inss_zero(self) -> None:
        aliq = aliquota_patronal_regime("simples_nacional", "I")
        r = calcular_provisoes(Decimal("5000.00"), "simples_nacional", aliquota_inss_patronal=aliq)
        assert r.inss_ferias.valor_provisao == Decimal("0.00")
        assert r.inss_13.valor_provisao == Decimal("0.00")

    def test_sn_anexo_ii_inss_zero(self) -> None:
        aliq = aliquota_patronal_regime("simples_nacional", "II")
        r = calcular_provisoes(Decimal("5000.00"), "simples_nacional", aliquota_inss_patronal=aliq)
        assert r.inss_ferias.valor_provisao == Decimal("0.00")
        assert r.inss_13.valor_provisao == Decimal("0.00")

    def test_sn_anexo_v_inss_zero(self) -> None:
        aliq = aliquota_patronal_regime("simples_nacional", "V")
        r = calcular_provisoes(Decimal("5000.00"), "simples_nacional", aliquota_inss_patronal=aliq)
        assert r.inss_ferias.valor_provisao == Decimal("0.00")
        assert r.inss_13.valor_provisao == Decimal("0.00")

    def test_sn_sem_anexo_inss_zero(self) -> None:
        """SN sem anexo informado → default conservador = 0 (evita dupla contagem)."""
        aliq = aliquota_patronal_regime("simples_nacional", None)
        r = calcular_provisoes(Decimal("10000.00"), "simples_nacional", aliquota_inss_patronal=aliq)
        assert r.inss_ferias.valor_provisao == Decimal("0.00")


# ── Simples Nacional / MEI — INSS zero (regime-level, sem aliquota_patronal_regime) ──
# Testa via calcular_provisoes com aliquota=0 explícito (path mais direto).


class TestSimplesNacional:
    def test_sn_inss_zero(self) -> None:
        r = calcular_provisoes(
            Decimal("10000.00"),
            "simples_nacional",
            aliquota_inss_patronal=Decimal("0"),
        )
        # Férias e 13º iguais ao LP
        assert r.ferias.valor_provisao == Decimal("1111.11")
        assert r.decimo_terceiro.valor_provisao == Decimal("833.33")
        # INSS = 0
        assert r.inss_ferias.valor_provisao == Decimal("0.00")
        assert r.inss_ferias.aliquota == Decimal("0")
        assert r.inss_13.valor_provisao == Decimal("0.00")
        # FGTS ainda incide (FGTS não é dispensado para SN)
        assert r.fgts_ferias.valor_provisao == Decimal("88.89")
        assert r.fgts_13.valor_provisao == Decimal("66.67")

    def test_mei_inss_zero(self) -> None:
        r = calcular_provisoes(
            Decimal("5000.00"),
            "mei",
            aliquota_inss_patronal=Decimal("0"),
        )
        assert r.inss_ferias.valor_provisao == Decimal("0.00")
        assert r.inss_13.valor_provisao == Decimal("0.00")
        # 5000/12 = 416,67 (ROUND_HALF_EVEN)
        assert r.decimo_terceiro.valor_provisao == Decimal("416.67")


# ── Estrutura / borda ───────────────────────────────────────────────────────


class TestEstrutura:
    def test_retorna_6_linhas(self) -> None:
        r = calcular_provisoes(Decimal("1000"), "lucro_presumido")
        linhas = r.as_lista()
        assert len(linhas) == 6
        tipos = {lin.tipo for lin in linhas}
        assert tipos == {
            "ferias",
            "13_salario",
            "inss_ferias",
            "inss_13",
            "fgts_ferias",
            "fgts_13",
        }

    def test_folha_zero(self) -> None:
        r = calcular_provisoes(Decimal("0"), "lucro_presumido")
        for linha in r.as_lista():
            assert linha.valor_provisao == Decimal("0.00")

    def test_folha_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="não pode ser negativa"):
            calcular_provisoes(Decimal("-1"), "lucro_presumido")

    def test_aliquota_inss_zero_explicitamente(self) -> None:
        """Passar aliquota_inss_patronal=0 zera INSS em qualquer regime."""
        r = calcular_provisoes(
            Decimal("10000.00"),
            "lucro_presumido",
            aliquota_inss_patronal=Decimal("0"),
        )
        assert r.inss_ferias.valor_provisao == Decimal("0.00")
        assert r.inss_13.valor_provisao == Decimal("0.00")


# ── Determinismo ────────────────────────────────────────────────────────────


class TestDeterminismo:
    def test_mesmo_input_mesmo_resultado(self) -> None:
        r1 = calcular_provisoes(Decimal("7500.50"), "lucro_presumido")
        r2 = calcular_provisoes(Decimal("7500.50"), "lucro_presumido")
        assert r1 == r2

    def test_mesmo_input_com_278_determinismo(self) -> None:
        aliq = Decimal("0.278")
        r1 = calcular_provisoes(Decimal("7500.50"), "lucro_presumido", aliquota_inss_patronal=aliq)
        r2 = calcular_provisoes(Decimal("7500.50"), "lucro_presumido", aliquota_inss_patronal=aliq)
        assert r1 == r2


# ── Aliquota persistida coerente (Fase 2 PR10) ───────────────────────────────


class TestAliquotaPersistidaSeisCasas:
    """Alíquotas persistidas em ``provisao_mensal.aliquota`` (NUMERIC(8,6)).

    Regra de reconciliação: base_calculo × aliquota ≈ valor_provisao com
    erro ≤ R$ 0,01.

    * Linha 13_salario: aliquota = 1/12 ≈ 0.083333 (folha/12 = base_13).
    * Linha ferias:     aliquota = 1/12 × 4/3 ≈ 0.111111 (inclui 1/3 constitucional).
      Antes do PR3: aliquota era 1/12 → base × 0.083333 ≠ ferias_total (off by 1/3).
    """

    def test_aliquota_ferias_seis_casas(self) -> None:
        r = calcular_provisoes(Decimal("10000.00"), "lucro_presumido")
        # FIX PR3: aliquota corrigida para 1/12 × 4/3 = 4/36 ≈ 0.111111
        # Garante base × aliquota ≈ ferias_total (férias + 1/3 constitucional).
        assert r.ferias.aliquota == Decimal("0.111111")
        # Garante que NÃO é mais o valor anterior (1/12 sem o terço).
        assert r.ferias.aliquota != Decimal("0.083333")

    def test_aliquota_13_seis_casas(self) -> None:
        r = calcular_provisoes(Decimal("10000.00"), "lucro_presumido")
        assert r.decimo_terceiro.aliquota == Decimal("0.083333")

    def test_base_x_aliquota_ferias_reconcilia(self) -> None:
        """Reconciliação: ferias.base × ferias.aliquota ≈ ferias.valor_provisao."""
        r = calcular_provisoes(Decimal("10000.00"), "lucro_presumido")
        # ferias: base 10000 × 0.111111 = 1111.11 → valor persistido 1111.11
        produto_ferias = r.ferias.base_calculo * r.ferias.aliquota
        diferenca_ferias = (produto_ferias - r.ferias.valor_provisao).copy_abs()
        assert diferenca_ferias <= Decimal("0.01")

    def test_base_x_aliquota_13_reconcilia(self) -> None:
        """Reconciliação: 13º.base × 13º.aliquota ≈ 13º.valor_provisao."""
        r = calcular_provisoes(Decimal("10000.00"), "lucro_presumido")
        # 13º: base 10000 × 0.083333 = 833.33 → valor persistido 833.33
        produto = r.decimo_terceiro.base_calculo * r.decimo_terceiro.aliquota
        diferenca = (produto - r.decimo_terceiro.valor_provisao).copy_abs()
        assert diferenca <= Decimal("0.01")

    def test_versao_bumped(self) -> None:
        """Bump v07→v08 sinaliza parametrização de alíquota patronal (FA5-M8)."""
        assert ALGORITMO_VERSAO == "prov-2026.08"
