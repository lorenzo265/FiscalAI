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
    """FGTS: 12 recolhimentos mensais, dia 7 do mês seguinte."""
    itens = gerar_calendario_anual("simples_nacional", 2026, tem_funcionarios=True)
    fgts = [i for i in itens if i.tipo_obrigacao == "fgts"]
    assert len(fgts) == 12


def test_simples_nacional_fgts_janeiro_vence_dia_7_fevereiro() -> None:
    itens = gerar_calendario_anual("simples_nacional", 2026, tem_funcionarios=True)
    fgts_jan = next(i for i in itens if i.tipo_obrigacao == "fgts" and "jan" in i.titulo)
    assert fgts_jan.data_vencimento == date(2026, 2, 7)


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
    """IRPJ do 4º trimestre (out-dez) vence no último dia de janeiro do ano seguinte."""
    itens = gerar_calendario_anual("lucro_presumido", 2026)
    trim4 = next(i for i in itens if "4º trim" in i.titulo)
    assert trim4.data_vencimento == date(2027, 1, 31)


def test_lucro_presumido_sem_funcionarios_sem_fgts_gps_dirf() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=False)
    assert not any(i.tipo_obrigacao in {"fgts", "gps_inss", "esocial_s1200", "dirf"} for i in itens)


def test_lucro_presumido_com_funcionarios_tem_dirf() -> None:
    """DIRF vence 31/jan do ano seguinte (IN RFB 2.219/2024)."""
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=True)
    dirf = [i for i in itens if i.tipo_obrigacao == "dirf"]
    assert len(dirf) == 1
    assert dirf[0].data_vencimento == date(2027, 1, 31)


def test_lucro_presumido_sem_funcionarios_sem_fgts_e_gps() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=False)
    assert not any(i.tipo_obrigacao in {"fgts", "gps_inss", "esocial_s1200"} for i in itens)


def test_lucro_presumido_com_funcionarios_tem_12_fgts() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=True)
    fgts = [i for i in itens if i.tipo_obrigacao == "fgts"]
    assert len(fgts) == 12


def test_lucro_presumido_fgts_janeiro_vence_dia_7_fevereiro() -> None:
    itens = gerar_calendario_anual("lucro_presumido", 2026, tem_funcionarios=True)
    fgts_jan = next(i for i in itens if i.tipo_obrigacao == "fgts" and "jan" in i.titulo)
    assert fgts_jan.data_vencimento == date(2026, 2, 7)


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
    """1º trim/2026: 1ª=30/abr, 2ª=29/mai, 3ª=30/jun."""
    itens = gerar_calendario_anual("lucro_presumido", 2026, parcelar_irpj=True)
    parcelas_1t = [i for i in itens if "1º trim" in i.titulo and "irpj" in i.tipo_obrigacao]
    datas = sorted(i.data_vencimento for i in parcelas_1t)
    assert datas[0] == date(2026, 4, 30)  # 1ª parcela — último dia de abril
    assert datas[1] == date(2026, 5, 31)  # 2ª parcela — último dia de maio
    assert datas[2] == date(2026, 6, 30)  # 3ª parcela — último dia de junho


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
