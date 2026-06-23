"""Testes unitários do gerador de calendário fiscal — função pura, sem banco."""
from __future__ import annotations

from datetime import date

import pytest

from app.modules.agenda.gerar_calendario import (
    ItemCalendario,
    gerar_calendario_anual,
)

# ── Simples Nacional ──────────────────────────────────────────────────────────


def test_simples_nacional_tem_12_pgdas_d() -> None:
    itens = gerar_calendario_anual("simples_nacional", 2026)
    pgdas = [i for i in itens if i.tipo_obrigacao == "pgdas_d"]
    assert len(pgdas) == 12


def test_simples_nacional_tem_defis() -> None:
    itens = gerar_calendario_anual("simples_nacional", 2026)
    defis = [i for i in itens if i.tipo_obrigacao == "defis"]
    assert len(defis) == 1
    assert defis[0].data_vencimento == date(2027, 3, 31)


def test_simples_nacional_pgdas_janeiro_vence_em_fevereiro() -> None:
    """PGDAS-D de jan/2026 vence em 20/fev/2026."""
    itens = gerar_calendario_anual("simples_nacional", 2026)
    jan = next(i for i in itens if i.tipo_obrigacao == "pgdas_d" and "jan" in i.titulo)
    assert jan.data_vencimento == date(2026, 2, 20)


def test_simples_nacional_pgdas_dezembro_vence_em_janeiro_seguinte() -> None:
    """PGDAS-D de dez/2026 vence em 20/jan/2027."""
    itens = gerar_calendario_anual("simples_nacional", 2026)
    dez = next(i for i in itens if i.tipo_obrigacao == "pgdas_d" and "dez" in i.titulo)
    assert dez.data_vencimento == date(2027, 1, 20)


def test_simples_nacional_ordenado_por_data() -> None:
    itens = gerar_calendario_anual("simples_nacional", 2026)
    datas = [i.data_vencimento for i in itens]
    assert datas == sorted(datas)


def test_simples_nacional_todos_tem_regime_correto() -> None:
    itens = gerar_calendario_anual("simples_nacional", 2026)
    assert all(i.regime == "simples_nacional" for i in itens)


def test_simples_nacional_sem_funcionarios_sem_fgts() -> None:
    itens = gerar_calendario_anual("simples_nacional", 2026, tem_funcionarios=False)
    assert not any(i.tipo_obrigacao == "fgts" for i in itens)


def test_simples_nacional_com_funcionarios_tem_12_fgts() -> None:
    """FGTS: 12 recolhimentos mensais, dia 20 do mês seguinte (Lei 14.438/2022)."""
    itens = gerar_calendario_anual("simples_nacional", 2026, tem_funcionarios=True)
    fgts = [i for i in itens if i.tipo_obrigacao == "fgts"]
    assert len(fgts) == 12


def test_simples_nacional_fgts_janeiro_vence_dia_20_fevereiro() -> None:
    """FGTS jan/2026 nominal = 20/02/2026 (sexta — dia útil); mantém 20/02.

    Lei 14.438/2022 + FGTS Digital: vencimento = dia 20 do mês seguinte.
    20/fev/2026 é sexta-feira, portanto não há antecipação.
    (Substitui o golden anterior que esperava 09/02 com base no dia 7 revogado.)
    """
    itens = gerar_calendario_anual("simples_nacional", 2026, tem_funcionarios=True)
    fgts_jan = next(i for i in itens if i.tipo_obrigacao == "fgts" and "jan" in i.titulo)
    assert fgts_jan.data_vencimento == date(2026, 2, 20)


def test_simples_nacional_com_funcionarios_tem_12_esocial() -> None:
    itens = gerar_calendario_anual("simples_nacional", 2026, tem_funcionarios=True)
    esocial = [i for i in itens if i.tipo_obrigacao == "esocial_s1200"]
    assert len(esocial) == 12


def test_simples_nacional_sem_gps_inss() -> None:
    """SN recolhe INSS patronal dentro do DAS — GPS não aparece no calendário."""
    itens = gerar_calendario_anual("simples_nacional", 2026, tem_funcionarios=True)
    assert not any(i.tipo_obrigacao == "gps_inss" for i in itens)


# ── MEI ───────────────────────────────────────────────────────────────────────


def test_mei_tem_12_das() -> None:
    itens = gerar_calendario_anual("mei", 2026)
    das = [i for i in itens if i.tipo_obrigacao == "das_mei"]
    assert len(das) == 12


def test_mei_das_janeiro_vence_em_20_fevereiro() -> None:
    """DAS-MEI de jan/2026 vence em 20/fev/2026 — mês SEGUINTE (LC 123/2006, art. 18-A, §3º)."""
    itens = gerar_calendario_anual("mei", 2026)
    jan = next(i for i in itens if i.tipo_obrigacao == "das_mei" and "jan" in i.titulo)
    assert jan.data_vencimento == date(2026, 2, 20)


def test_mei_das_dezembro_vence_em_20_janeiro_seguinte() -> None:
    """DAS-MEI de dez/2026 vence em 20/jan/2027."""
    itens = gerar_calendario_anual("mei", 2026)
    dez = next(i for i in itens if i.tipo_obrigacao == "das_mei" and "dez" in i.titulo)
    assert dez.data_vencimento == date(2027, 1, 20)


def test_mei_tem_dasn_simei() -> None:
    itens = gerar_calendario_anual("mei", 2026)
    dasn = [i for i in itens if i.tipo_obrigacao == "dasn_simei"]
    assert len(dasn) == 1
    assert dasn[0].data_vencimento == date(2027, 5, 31)


def test_mei_ordenado_por_data() -> None:
    itens = gerar_calendario_anual("mei", 2026)
    datas = [i.data_vencimento for i in itens]
    assert datas == sorted(datas)


# ── Lucro Presumido ──────────────────────────────────────────────────────────


def test_lucro_presumido_tem_4_irpj_trimestrais() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026)
    irpj = [i for i in itens if i.tipo_obrigacao == "irpj_csll_trimestral"]
    assert len(irpj) == 4


def test_lucro_presumido_tem_12_pis_cofins() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026)
    pis = [i for i in itens if i.tipo_obrigacao == "pis_cofins"]
    assert len(pis) == 12


def test_lucro_presumido_tem_12_dctf_web() -> None:
    """DCTFWeb substituiu DCTF para todas as empresas com eSocial (IN RFB 2.005/2021)."""
    itens = gerar_calendario_anual("lucro_presumido", 2026)
    dctf_web = [i for i in itens if i.tipo_obrigacao == "dctf_web"]
    assert len(dctf_web) == 12


def test_lucro_presumido_nao_tem_dctf_antigo() -> None:
    """tipo_obrigacao='dctf' não deve aparecer — foi substituído por 'dctf_web'."""
    itens = gerar_calendario_anual("lucro_presumido", 2026)
    assert not any(i.tipo_obrigacao == "dctf" for i in itens)


def test_lucro_presumido_irpj_1_trim_vence_em_abril() -> None:
    """IRPJ do 1º trimestre (jan-mar) vence no último dia de abril."""
    itens = gerar_calendario_anual("lucro_presumido", 2026)
    trim1 = next(i for i in itens if "1º trim" in i.titulo)
    # Último dia de abril/2026 = 30/04/2026
    assert trim1.data_vencimento == date(2026, 4, 30)


def test_lucro_presumido_irpj_4_trim_vence_em_janeiro_seguinte() -> None:
    """IRPJ do 4º trim/2026 nominal = 31/01/2027 (domingo); posterga p/ 01/02/2027 (segunda)."""
    itens = gerar_calendario_anual("lucro_presumido", 2026)
    trim4 = next(i for i in itens if "4º trim" in i.titulo)
    assert trim4.data_vencimento == date(2027, 2, 1)


def test_lucro_presumido_sem_funcionarios_sem_fgts_gps_dirf() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=False)
    assert not any(i.tipo_obrigacao in {"fgts", "gps_inss", "esocial_s1200", "dirf"} for i in itens)


def test_lucro_presumido_com_funcionarios_tem_dirf() -> None:
    """DIRF nominal 31/jan/2027 (domingo); posterga p/ 01/02 (segunda)."""
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=True)
    dirf = [i for i in itens if i.tipo_obrigacao == "dirf"]
    assert len(dirf) == 1
    assert dirf[0].data_vencimento == date(2027, 2, 1)


def test_lucro_presumido_sem_funcionarios_sem_fgts_e_gps() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=False)
    assert not any(i.tipo_obrigacao in {"fgts", "gps_inss", "esocial_s1200"} for i in itens)


def test_lucro_presumido_com_funcionarios_tem_12_fgts() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=True)
    fgts = [i for i in itens if i.tipo_obrigacao == "fgts"]
    assert len(fgts) == 12


def test_lucro_presumido_fgts_janeiro_vence_dia_20_fevereiro() -> None:
    """FGTS jan/2026 nominal = 20/02/2026 (sexta — dia útil); mantém 20/02.

    Lei 14.438/2022 + FGTS Digital: vencimento = dia 20 do mês seguinte.
    20/fev/2026 é sexta-feira, portanto não há antecipação.
    (Substitui o golden anterior que esperava 09/02 com base no dia 7 revogado.)
    """
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=True)
    fgts_jan = next(i for i in itens if i.tipo_obrigacao == "fgts" and "jan" in i.titulo)
    assert fgts_jan.data_vencimento == date(2026, 2, 20)


def test_lucro_presumido_com_funcionarios_tem_12_gps_inss() -> None:
    """GPS/INSS: 12 recolhimentos, dia 20 do mês seguinte."""
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=True)
    gps = [i for i in itens if i.tipo_obrigacao == "gps_inss"]
    assert len(gps) == 12


def test_lucro_presumido_gps_janeiro_vence_dia_20_fevereiro() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=True)
    gps_jan = next(i for i in itens if i.tipo_obrigacao == "gps_inss" and "jan" in i.titulo)
    assert gps_jan.data_vencimento == date(2026, 2, 20)


def test_lucro_presumido_com_funcionarios_tem_12_esocial() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=True)
    esocial = [i for i in itens if i.tipo_obrigacao == "esocial_s1200"]
    assert len(esocial) == 12


def test_lucro_presumido_parcelamento_irpj_gera_12_itens() -> None:
    """parcelar_irpj=True: 3 parcelas × 4 trimestres = 12 itens de IRPJ/CSLL."""
    itens = gerar_calendario_anual("lucro_presumido", 2026, parcelar_irpj=True)
    irpj = [i for i in itens if i.tipo_obrigacao == "irpj_csll_trimestral"]
    assert len(irpj) == 12


def test_lucro_presumido_parcelamento_irpj_1trim_parcelas_corretas() -> None:
    """1º trim/2026 com parcelamento; 31/05/2026 é domingo → posterga p/ 01/06."""
    itens = gerar_calendario_anual("lucro_presumido", 2026, parcelar_irpj=True)
    parcelas_1t = [i for i in itens if "1º trim" in i.titulo and "irpj" in i.tipo_obrigacao]
    datas = sorted(i.data_vencimento for i in parcelas_1t)
    assert datas[0] == date(2026, 4, 30)  # 1ª parcela — 30/04 (quinta) ok
    assert datas[1] == date(2026, 6, 1)   # 2ª parcela nominal 31/05 (dom) → 01/06
    assert datas[2] == date(2026, 6, 30)  # 3ª parcela — 30/06 (terça) ok


def test_lucro_presumido_sem_parcelamento_4_itens_irpj() -> None:
    """parcelar_irpj=False (padrão): 1 item por trimestre = 4 ao total."""
    itens = gerar_calendario_anual("lucro_presumido", 2026, parcelar_irpj=False)
    irpj = [i for i in itens if i.tipo_obrigacao == "irpj_csll_trimestral"]
    assert len(irpj) == 4


def test_lucro_presumido_ordenado_por_data() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026)
    datas = [i.data_vencimento for i in itens]
    assert datas == sorted(datas)


def test_lucro_presumido_com_funcionarios_ordenado_por_data() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=True)
    datas = [i.data_vencimento for i in itens]
    assert datas == sorted(datas)


# ── Regime inválido ───────────────────────────────────────────────────────────


def test_regime_invalido_levanta_value_error() -> None:
    with pytest.raises(ValueError, match="Regime não suportado"):
        gerar_calendario_anual("lucro_real", 2026)


# ── Invariantes ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("regime", ["mei", "simples_nacional", "lucro_presumido"])
def test_todos_itens_sao_item_calendario(regime: str) -> None:
    itens = gerar_calendario_anual(regime, 2026)
    assert all(isinstance(i, ItemCalendario) for i in itens)
    assert all(i.titulo for i in itens)
    assert all(i.tipo_obrigacao for i in itens)
    assert all(i.data_vencimento.year >= 2026 for i in itens)


@pytest.mark.parametrize("regime", ["mei", "simples_nacional", "lucro_presumido"])
def test_calendario_nao_vazio(regime: str) -> None:
    assert len(gerar_calendario_anual(regime, 2026)) > 0


# ── m1 da auditoria Sprints 4-6: postergação para dia útil ───────────────────


def test_das_mei_em_feriado_posterga() -> None:
    """DAS-MEI nominal 20/abril/2026 (segunda); se 20/abr fosse feriado, posterga."""
    feriados = {date(2026, 4, 20)}  # fictício
    itens = gerar_calendario_anual("mei", 2026, feriados=feriados)
    das_mar = next(i for i in itens if i.tipo_obrigacao == "das_mei" and "mar" in i.titulo)
    # Nominal: 20/04/2026 (segunda); com feriado → 21/04 (terça)
    assert das_mar.data_vencimento == date(2026, 4, 21)


def test_pgdas_em_feriado_de_tiradentes_posterga() -> None:
    """21/04 (Tiradentes) é feriado nacional permanente — DAS de março/2026."""
    feriados = {date(2026, 4, 21)}  # Tiradentes
    itens = gerar_calendario_anual("simples_nacional", 2026, feriados=feriados)
    pgdas_mar = next(i for i in itens if i.tipo_obrigacao == "pgdas_d" and "mar" in i.titulo)
    # Nominal: 20/04 (segunda) — ok. Mas se Tiradentes cair no domingo (21/04/2025),
    # e em 2026 cai em terça (21/04/2026), o PGDAS de mar/26 venceria 20/04 (seg)
    # e NÃO é afetado. Validação: vencimento != 21/04 quando 21 é feriado.
    assert pgdas_mar.data_vencimento != date(2026, 4, 21)


def test_dia_vencimento_sabado_posterga_para_segunda() -> None:
    """Unit do helper: 07/02/2026 é sábado → posterga p/ 09/02 (segunda)."""
    from app.modules.agenda.gerar_calendario import _dia_vencimento

    venc = _dia_vencimento(2026, 2, 7)
    assert venc == date(2026, 2, 9)


def test_dia_vencimento_domingo_posterga_para_segunda() -> None:
    """Unit do helper: 31/01/2027 é domingo → posterga p/ 01/02/2027 (segunda)."""
    from app.modules.agenda.gerar_calendario import _dia_vencimento

    venc = _dia_vencimento(2027, 1, 31)
    assert venc == date(2027, 2, 1)


def test_dia_vencimento_feriado_segunda_posterga_para_terca() -> None:
    """Feriado nacional na segunda → posterga p/ terça."""
    from app.modules.agenda.gerar_calendario import _dia_vencimento

    # 25/12/2028 é segunda (Natal) — fica feriado e posterga
    feriados = frozenset({date(2028, 12, 25)})
    venc = _dia_vencimento(2028, 12, 25, feriados)
    assert venc == date(2028, 12, 26)


def test_dia_vencimento_carnaval_arrasta_se_sucessivo() -> None:
    """Feriado na sexta → fim de semana adiante → posterga p/ segunda."""
    from app.modules.agenda.gerar_calendario import _dia_vencimento

    # Suponha 03/04/2026 (sexta) como feriado fictício; sáb 04, dom 05; resultado: 06/04
    feriados = frozenset({date(2026, 4, 3)})
    venc = _dia_vencimento(2026, 4, 3, feriados)
    assert venc == date(2026, 4, 6)


# ── FGTS dia 20 — goldens Lei 14.438/2022 ────────────────────────────────────
#
# Regra: FGTS vence dia 20 do mês seguinte. Em dia não-útil, ANTECIPA (retrocede)
# para o dia útil imediatamente anterior — ≠ postergação das demais obrigações.


def test_fgts_dia_20_dia_util_mantem_data() -> None:
    """FGTS mai/2026 → 20/jun/2026 (sábado): NÃO é este caso — veja abaixo.

    Este golden usa abr/2026 → 20/mai/2026 (terça-feira, dia útil): mantém 20/05.

    Cálculo: mai/2026 day 1 = sexta; mai 20 = sexta + 19 = 23 mod 7 = 2 = terça.
    Terça é dia útil → não há antecipação.
    """
    itens = gerar_calendario_anual("simples_nacional", 2026, tem_funcionarios=True)
    fgts_abr = next(i for i in itens if i.tipo_obrigacao == "fgts" and "abr" in i.titulo)
    # FGTS abr/2026 → 20/mai/2026 (terça) = dia útil → mantém
    assert fgts_abr.data_vencimento == date(2026, 5, 20)


def test_fgts_dia_20_sabado_antecipa_para_sexta() -> None:
    """FGTS mai/2026 → 20/jun/2026 (sábado) → ANTECIPA para 19/jun/2026 (sexta).

    Cálculo: jun/2026 day 1 = segunda; jun 20 = segunda + 19 = 19 mod 7 = 5 = sábado.
    Sábado não é dia útil → retrocede 1 dia → 19/jun/2026 (sexta).
    """
    itens = gerar_calendario_anual("simples_nacional", 2026, tem_funcionarios=True)
    fgts_mai = next(i for i in itens if i.tipo_obrigacao == "fgts" and "mai" in i.titulo)
    assert fgts_mai.data_vencimento == date(2026, 6, 19)


def test_fgts_dia_20_domingo_antecipa_para_sexta() -> None:
    """FGTS ago/2026 → 20/set/2026 (domingo) → ANTECIPA para 18/set/2026 (sexta).

    Cálculo: set/2026 day 1 = terça; set 20 = terça + 19 = 20 mod 7 = 6 = domingo.
    Domingo não é dia útil → retrocede 1 dia → 19/set/2026 (sábado, também não-útil)
    → retrocede mais 1 → 18/set/2026 (sexta). Dia útil.
    """
    itens = gerar_calendario_anual("simples_nacional", 2026, tem_funcionarios=True)
    fgts_ago = next(i for i in itens if i.tipo_obrigacao == "fgts" and "ago" in i.titulo)
    assert fgts_ago.data_vencimento == date(2026, 9, 18)


def test_fgts_dia_20_feriado_antecipa_para_dia_util_anterior() -> None:
    """FGTS mar/2026 → 20/abr/2026 (segunda). Se 20/abr for feriado, antecipa p/ 17/abr (sexta).

    20/abr/2026 é segunda-feira. Marcamos como feriado fictício para exercitar a
    antecipação por feriado. O retrocesso passa pelo domingo (19/abr) e sábado (18/abr)
    e encontra 17/abr (sexta-feira, dia útil).
    """
    feriados = frozenset({date(2026, 4, 20)})
    itens = gerar_calendario_anual("simples_nacional", 2026, tem_funcionarios=True, feriados=feriados)
    fgts_mar = next(i for i in itens if i.tipo_obrigacao == "fgts" and "mar" in i.titulo)
    # 20/abr (seg, feriado) → 19/abr (dom) → 18/abr (sáb) → 17/abr (sex) ✓
    assert fgts_mar.data_vencimento == date(2026, 4, 17)


def test_fgts_antecipacao_nao_afeta_outras_obrigacoes() -> None:
    """Garantia de isolamento: GPS/INSS no mesmo mês POSTERGA (não antecipa).

    mar/2026 → 20/abr/2026 (segunda, feriado fictício).
    GPS/INSS: usa _dia_vencimento (posterga) → 21/abr/2026 (terça).
    FGTS: usa _fgts_vencimento (antecipa) → 17/abr/2026 (sexta).
    """
    feriados = frozenset({date(2026, 4, 20)})
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=True, feriados=feriados)
    fgts_mar = next(i for i in itens if i.tipo_obrigacao == "fgts" and "mar" in i.titulo)
    gps_mar = next(i for i in itens if i.tipo_obrigacao == "gps_inss" and "mar" in i.titulo)
    # FGTS antecipa; GPS posterga — comportamentos opostos no mesmo mês/feriado
    assert fgts_mar.data_vencimento == date(2026, 4, 17)
    assert gps_mar.data_vencimento == date(2026, 4, 21)


# ── Helpers _fgts_vencimento / _dia_util_anterior — testes unitários ─────────


def test_fgts_vencimento_dia_util() -> None:
    """_fgts_vencimento devolve 20 quando é dia útil."""
    from app.modules.agenda.gerar_calendario import _fgts_vencimento

    # 20/fev/2026 = sexta (dia útil)
    assert _fgts_vencimento(2026, 2) == date(2026, 2, 20)


def test_fgts_vencimento_sabado_retrocede_para_sexta() -> None:
    """_fgts_vencimento antecipa de sábado (20/jun) para sexta (19/jun)."""
    from app.modules.agenda.gerar_calendario import _fgts_vencimento

    assert _fgts_vencimento(2026, 6) == date(2026, 6, 19)


def test_fgts_vencimento_domingo_retrocede_para_sexta() -> None:
    """_fgts_vencimento antecipa de domingo (20/set) para sexta (18/set), saltando sábado."""
    from app.modules.agenda.gerar_calendario import _fgts_vencimento

    assert _fgts_vencimento(2026, 9) == date(2026, 9, 18)


def test_dia_util_anterior_feriado_na_segunda() -> None:
    """_dia_util_anterior: segunda feriada → retrocede até sexta anterior."""
    from app.modules.agenda.gerar_calendario import _dia_util_anterior

    # 20/abr/2026 = segunda; marcamos como feriado → retrocede
    feriados = frozenset({date(2026, 4, 20)})
    resultado = _dia_util_anterior(date(2026, 4, 20), feriados)
    # dom 19 → sáb 18 → sex 17 ✓
    assert resultado == date(2026, 4, 17)


def test_dia_util_anterior_dia_util_mantem() -> None:
    """_dia_util_anterior: dia já útil é devolvido sem alterar."""
    from app.modules.agenda.gerar_calendario import _dia_util_anterior

    assert _dia_util_anterior(date(2026, 2, 20), frozenset()) == date(2026, 2, 20)
