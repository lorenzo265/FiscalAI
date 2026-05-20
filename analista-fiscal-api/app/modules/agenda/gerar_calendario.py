"""Gerador de calendário fiscal por regime — função pura sem I/O.

Regras por regime:
  Simples Nacional (CGSN 140/2018):
    - PGDAS-D + DAS: até dia 20 do mês seguinte à competência
    - DEFIS: 31/março do ano seguinte
    - FGTS: dia 7 do mês seguinte (quando tem_funcionarios=True)
    - eSocial S-1200: dia 15 do mês seguinte (quando tem_funcionarios=True)

  MEI:
    - DAS-MEI: dia 20 do mês seguinte
    - DASN-SIMEI: 31/maio do ano seguinte

  Lucro Presumido (Lei 9.718/1998 + IN RFB 1.700/2017 + IN RFB 2.005/2021):
    - DARF IRPJ/CSLL trimestral (parcelar_irpj=False): vence no último dia do
      1º mês após o trimestre (1ª parcela / pagamento único).
      Parcelamento em 3x (art. 5º Lei 9.430/1996): cada cota vence no último dia
      dos 3 meses seguintes ao trimestre. Usar parcelar_irpj=True para gerar as 3 datas.
    - DCTFWeb: até o 15º dia do 2º mês seguinte ao fato gerador (IN RFB 2.005/2021)
      Substituiu a DCTF para todas as empresas obrigadas ao eSocial desde 2023.
    - PIS/Cofins: dia 25 do mês seguinte
    - FGTS: dia 7 do mês seguinte (quando tem_funcionarios=True)
    - GPS/INSS: dia 20 do mês seguinte (quando tem_funcionarios=True)
    - eSocial S-1200: dia 15 do mês seguinte (quando tem_funcionarios=True)

Observação: "dia útil" é simplificado (sem calendário de feriados nesta versão).
A versão com feriados requer integração com API de feriados — Sprint 6.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ItemCalendario:
    titulo: str
    descricao: str
    data_vencimento: date
    regime: str
    tipo_obrigacao: str


def gerar_calendario_anual(
    regime: str,
    ano: int,
    tem_funcionarios: bool = False,
    parcelar_irpj: bool = False,
) -> list[ItemCalendario]:
    """Gera todos os itens de calendário fiscal para um ano e regime.

    Args:
        regime: 'simples_nacional', 'lucro_presumido', 'mei'
        ano: Ano de competência (ex: 2026)
        tem_funcionarios: True inclui FGTS, eSocial S-1200 e GPS/INSS (LP).
        parcelar_irpj: True gera 3 datas por trimestre (art. 5º Lei 9.430/1996).
                       False (padrão) gera apenas a 1ª data (pagamento único).

    Returns:
        Lista de ItemCalendario ordenada por data_vencimento.
    """
    if regime == "mei":
        return _calendario_mei(ano)
    if regime == "simples_nacional":
        return _calendario_simples_nacional(ano, tem_funcionarios)
    if regime == "lucro_presumido":
        return _calendario_lucro_presumido(ano, tem_funcionarios, parcelar_irpj)
    raise ValueError(f"Regime não suportado para calendário: {regime!r}")


def _calendario_mei(ano: int) -> list[ItemCalendario]:
    items: list[ItemCalendario] = []

    for mes in range(1, 13):
        # DAS-MEI vence dia 20 do mês SEGUINTE à competência (LC 123/2006, art. 18-A, §3º)
        mes_venc = mes + 1 if mes < 12 else 1
        ano_venc = ano if mes < 12 else ano + 1
        venc = _dia_vencimento(ano_venc, mes_venc, 20)
        items.append(ItemCalendario(
            titulo=f"DAS-MEI {_mes_nome(mes)}/{ano}",
            descricao=f"Pagamento do DAS-MEI referente a {_mes_nome(mes)}/{ano}",
            data_vencimento=venc,
            regime="mei",
            tipo_obrigacao="das_mei",
        ))

    # DASN-SIMEI até 31/maio do ano seguinte
    items.append(ItemCalendario(
        titulo=f"DASN-SIMEI {ano}",
        descricao=f"Declaração Anual do Simples Nacional para MEI — ano-base {ano}",
        data_vencimento=date(ano + 1, 5, 31),
        regime="mei",
        tipo_obrigacao="dasn_simei",
    ))

    return sorted(items, key=lambda i: i.data_vencimento)


def _calendario_simples_nacional(ano: int, tem_funcionarios: bool = False) -> list[ItemCalendario]:
    items: list[ItemCalendario] = []

    for mes in range(1, 13):
        # PGDAS-D e DAS vencem dia 20 do mês seguinte
        mes_seguinte = mes + 1 if mes < 12 else 1
        ano_seguinte = ano if mes < 12 else ano + 1
        venc = _dia_vencimento(ano_seguinte, mes_seguinte, 20)

        items.append(ItemCalendario(
            titulo=f"PGDAS-D {_mes_nome(mes)}/{ano}",
            descricao=f"Transmissão do PGDAS-D e pagamento do DAS referentes a {_mes_nome(mes)}/{ano}",
            data_vencimento=venc,
            regime="simples_nacional",
            tipo_obrigacao="pgdas_d",
        ))

    # DEFIS — 31/março do ano seguinte
    items.append(ItemCalendario(
        titulo=f"DEFIS {ano}",
        descricao=f"Declaração de Informações Socioeconômicas e Fiscais — ano-base {ano}",
        data_vencimento=date(ano + 1, 3, 31),
        regime="simples_nacional",
        tipo_obrigacao="defis",
    ))

    if tem_funcionarios:
        items.extend(_obrigacoes_trabalhistas(ano, "simples_nacional", incluir_gps=False))

    return sorted(items, key=lambda i: i.data_vencimento)


def _calendario_lucro_presumido(
    ano: int,
    tem_funcionarios: bool = False,
    parcelar_irpj: bool = False,
) -> list[ItemCalendario]:
    items: list[ItemCalendario] = []

    # PIS/Cofins: dia 25 do mês seguinte
    for mes in range(1, 13):
        mes_venc = mes + 1 if mes < 12 else 1
        ano_venc = ano if mes < 12 else ano + 1
        venc = _dia_vencimento(ano_venc, mes_venc, 25)
        items.append(ItemCalendario(
            titulo=f"PIS/Cofins {_mes_nome(mes)}/{ano}",
            descricao=f"DARF PIS e Cofins cumulativo referente a {_mes_nome(mes)}/{ano}",
            data_vencimento=venc,
            regime="lucro_presumido",
            tipo_obrigacao="pis_cofins",
        ))

    # IRPJ + CSLL trimestral (art. 5º Lei 9.430/1996)
    # Pagamento único: último dia do 1º mês após o trimestre.
    # Parcelamento em 3x: último dia de cada um dos 3 meses seguintes ao trimestre.
    trimestres = [
        (3, "1º trim"),   # jan-mar
        (6, "2º trim"),   # abr-jun
        (9, "3º trim"),   # jul-set
        (12, "4º trim"),  # out-dez
    ]
    num_parcelas = 3 if parcelar_irpj else 1
    for mes_fim_trim, rotulo in trimestres:
        for parcela in range(1, num_parcelas + 1):
            offset = mes_fim_trim + parcela
            mes_venc = offset if offset <= 12 else offset - 12
            ano_venc = ano if offset <= 12 else ano + 1
            ultimo_dia = calendar.monthrange(ano_venc, mes_venc)[1]
            venc = date(ano_venc, mes_venc, ultimo_dia)
            if parcelar_irpj:
                titulo = f"IRPJ/CSLL {rotulo}/{ano} — {parcela}ª parcela"
                descricao = (
                    f"DARF IRPJ e CSLL — {rotulo}/{ano}, "
                    f"{parcela}ª cota (parcelamento em 3x, art. 5º Lei 9.430/1996)"
                )
            else:
                titulo = f"IRPJ/CSLL {rotulo}/{ano}"
                descricao = f"DARF IRPJ e CSLL trimestral — {rotulo} do ano {ano}"
            items.append(ItemCalendario(
                titulo=titulo,
                descricao=descricao,
                data_vencimento=venc,
                regime="lucro_presumido",
                tipo_obrigacao="irpj_csll_trimestral",
            ))

    # DCTFWeb mensal: dia 15 do 2º mês após o fato gerador (IN RFB 2.005/2021)
    # Substituiu a DCTF para todas as empresas obrigadas ao eSocial (universal desde 2023)
    for mes in range(1, 13):
        mes_venc = mes + 2 if mes <= 10 else (mes + 2) - 12
        ano_venc = ano if mes <= 10 else ano + 1
        venc = _dia_vencimento(ano_venc, mes_venc, 15)
        items.append(ItemCalendario(
            titulo=f"DCTFWeb {_mes_nome(mes)}/{ano}",
            descricao=f"Declaração de Débitos e Créditos Tributários Federais Web — {_mes_nome(mes)}/{ano}",
            data_vencimento=venc,
            regime="lucro_presumido",
            tipo_obrigacao="dctf_web",
        ))

    if tem_funcionarios:
        items.extend(_obrigacoes_trabalhistas(ano, "lucro_presumido", incluir_gps=True))
        # DIRF — obrigação anual, vence 31/jan do ano seguinte (IN RFB 2.219/2024)
        items.append(ItemCalendario(
            titulo=f"DIRF {ano}",
            descricao=(
                f"Declaração do Imposto sobre a Renda Retido na Fonte "
                f"— ano-calendário {ano}"
            ),
            data_vencimento=date(ano + 1, 1, 31),
            regime="lucro_presumido",
            tipo_obrigacao="dirf",
        ))

    return sorted(items, key=lambda i: i.data_vencimento)


def _obrigacoes_trabalhistas(
    ano: int,
    regime: str,
    incluir_gps: bool,
) -> list[ItemCalendario]:
    """FGTS (dia 7), eSocial S-1200 (dia 15) e GPS/INSS (dia 20, LP apenas)."""
    items: list[ItemCalendario] = []

    for mes in range(1, 13):
        mes_venc = mes + 1 if mes < 12 else 1
        ano_venc = ano if mes < 12 else ano + 1

        # FGTS — dia 7 do mês seguinte (Lei 8.036/1990, art. 15, §5º)
        items.append(ItemCalendario(
            titulo=f"FGTS {_mes_nome(mes)}/{ano}",
            descricao=f"Recolhimento do FGTS referente à folha de {_mes_nome(mes)}/{ano}",
            data_vencimento=_dia_vencimento(ano_venc, mes_venc, 7),
            regime=regime,
            tipo_obrigacao="fgts",
        ))

        # eSocial S-1200 — dia 15 do mês seguinte (folha de remunerações)
        items.append(ItemCalendario(
            titulo=f"eSocial S-1200 {_mes_nome(mes)}/{ano}",
            descricao=f"Remunerações dos trabalhadores via eSocial — {_mes_nome(mes)}/{ano}",
            data_vencimento=_dia_vencimento(ano_venc, mes_venc, 15),
            regime=regime,
            tipo_obrigacao="esocial_s1200",
        ))

        # GPS/INSS — dia 20 (LP); SN inclui INSS patronal dentro do DAS
        if incluir_gps:
            items.append(ItemCalendario(
                titulo=f"GPS/INSS {_mes_nome(mes)}/{ano}",
                descricao=f"Recolhimento INSS patronal via GPS referente a {_mes_nome(mes)}/{ano}",
                data_vencimento=_dia_vencimento(ano_venc, mes_venc, 20),
                regime=regime,
                tipo_obrigacao="gps_inss",
            ))

    return items


def _dia_vencimento(ano: int, mes: int, dia: int) -> date:
    """Retorna a data de vencimento, ajustando para o último dia do mês se necessário."""
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(dia, ultimo))


def _mes_nome(mes: int) -> str:
    nomes = [
        "jan", "fev", "mar", "abr", "mai", "jun",
        "jul", "ago", "set", "out", "nov", "dez",
    ]
    return nomes[mes - 1]
