"""Gerador de calendário fiscal por regime — função pura sem I/O.

Regras por regime:
  Simples Nacional (CGSN 140/2018):
    - PGDAS-D + DAS: até dia 20 do mês seguinte à competência
    - DEFIS: 31/março do ano seguinte
    - FGTS: dia 20 do mês seguinte (quando tem_funcionarios=True)
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
    - FGTS: dia 20 do mês seguinte (quando tem_funcionarios=True) — Lei 14.438/2022
    - GPS/INSS: dia 20 do mês seguinte (quando tem_funcionarios=True)
    - eSocial S-1200: dia 15 do mês seguinte (quando tem_funcionarios=True)

Dia útil — FGTS vs. demais obrigações:
  ``_dia_vencimento`` posterga para o próximo dia útil quando cai em sábado,
  domingo ou feriado nacional (IN RFB 1.300/2012 art. 26). Os feriados são
  passados pelo caller (chamada à BrasilAPI ``/feriados/v1/{ano}`` cacheada).

  FGTS (Lei 14.438/2022 + FGTS Digital, competências desde mar/2024): vence no
  dia 20 do mês seguinte. Quando o dia 20 cai em sábado, domingo ou feriado,
  o recolhimento é ANTECIPADO para o dia útil IMEDIATAMENTE ANTERIOR — ao
  contrário das demais obrigações, que são postergadas.
"""
from __future__ import annotations

import calendar
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta


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
    feriados: Iterable[date] | None = None,
) -> list[ItemCalendario]:
    """Gera todos os itens de calendário fiscal para um ano e regime.

    Args:
        regime: 'simples_nacional', 'lucro_presumido', 'mei'
        ano: Ano de competência (ex: 2026)
        tem_funcionarios: True inclui FGTS, eSocial S-1200 e GPS/INSS (LP).
        parcelar_irpj: True gera 3 datas por trimestre (art. 5º Lei 9.430/1996).
                       False (padrão) gera apenas a 1ª data (pagamento único).
        feriados: Conjunto de feriados nacionais a postergar para próximo dia
                  útil (IN RFB 1.300/2012 art. 26). Quando None, só sábado/domingo
                  são postergados.

    Returns:
        Lista de ItemCalendario ordenada por data_vencimento.
    """
    feriados_set = frozenset(feriados) if feriados else frozenset()
    if regime == "mei":
        return _calendario_mei(ano, feriados_set)
    if regime == "simples_nacional":
        return _calendario_simples_nacional(ano, tem_funcionarios, feriados_set)
    if regime == "lucro_presumido":
        return _calendario_lucro_presumido(ano, tem_funcionarios, parcelar_irpj, feriados_set)
    raise ValueError(f"Regime não suportado para calendário: {regime!r}")


def _calendario_mei(ano: int, feriados: frozenset[date]) -> list[ItemCalendario]:
    items: list[ItemCalendario] = []

    for mes in range(1, 13):
        # DAS-MEI vence dia 20 do mês SEGUINTE à competência (LC 123/2006, art. 18-A, §3º)
        mes_venc = mes + 1 if mes < 12 else 1
        ano_venc = ano if mes < 12 else ano + 1
        venc = _dia_vencimento(ano_venc, mes_venc, 20, feriados)
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
        data_vencimento=_proximo_dia_util(date(ano + 1, 5, 31), feriados),
        regime="mei",
        tipo_obrigacao="dasn_simei",
    ))

    return sorted(items, key=lambda i: i.data_vencimento)


def _calendario_simples_nacional(
    ano: int,
    tem_funcionarios: bool = False,
    feriados: frozenset[date] = frozenset(),
) -> list[ItemCalendario]:
    items: list[ItemCalendario] = []

    for mes in range(1, 13):
        # PGDAS-D e DAS vencem dia 20 do mês seguinte
        mes_seguinte = mes + 1 if mes < 12 else 1
        ano_seguinte = ano if mes < 12 else ano + 1
        venc = _dia_vencimento(ano_seguinte, mes_seguinte, 20, feriados)

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
        data_vencimento=_proximo_dia_util(date(ano + 1, 3, 31), feriados),
        regime="simples_nacional",
        tipo_obrigacao="defis",
    ))

    if tem_funcionarios:
        items.extend(_obrigacoes_trabalhistas(ano, "simples_nacional", incluir_gps=False, feriados=feriados))

    return sorted(items, key=lambda i: i.data_vencimento)


def _calendario_lucro_presumido(
    ano: int,
    tem_funcionarios: bool = False,
    parcelar_irpj: bool = False,
    feriados: frozenset[date] = frozenset(),
) -> list[ItemCalendario]:
    items: list[ItemCalendario] = []

    # PIS/Cofins: dia 25 do mês seguinte
    for mes in range(1, 13):
        mes_venc = mes + 1 if mes < 12 else 1
        ano_venc = ano if mes < 12 else ano + 1
        venc = _dia_vencimento(ano_venc, mes_venc, 25, feriados)
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
            venc = _proximo_dia_util(date(ano_venc, mes_venc, ultimo_dia), feriados)
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
        venc = _dia_vencimento(ano_venc, mes_venc, 15, feriados)
        items.append(ItemCalendario(
            titulo=f"DCTFWeb {_mes_nome(mes)}/{ano}",
            descricao=f"Declaração de Débitos e Créditos Tributários Federais Web — {_mes_nome(mes)}/{ano}",
            data_vencimento=venc,
            regime="lucro_presumido",
            tipo_obrigacao="dctf_web",
        ))

    if tem_funcionarios:
        items.extend(_obrigacoes_trabalhistas(ano, "lucro_presumido", incluir_gps=True, feriados=feriados))
        # DIRF — obrigação anual, vence 31/jan do ano seguinte (IN RFB 2.219/2024)
        items.append(ItemCalendario(
            titulo=f"DIRF {ano}",
            descricao=(
                f"Declaração do Imposto sobre a Renda Retido na Fonte "
                f"— ano-calendário {ano}"
            ),
            data_vencimento=_proximo_dia_util(date(ano + 1, 1, 31), feriados),
            regime="lucro_presumido",
            tipo_obrigacao="dirf",
        ))

    return sorted(items, key=lambda i: i.data_vencimento)


def _obrigacoes_trabalhistas(
    ano: int,
    regime: str,
    incluir_gps: bool,
    feriados: frozenset[date] = frozenset(),
) -> list[ItemCalendario]:
    """FGTS (dia 20, antecipado), eSocial S-1200 (dia 15) e GPS/INSS (dia 20, LP apenas)."""
    items: list[ItemCalendario] = []

    for mes in range(1, 13):
        mes_venc = mes + 1 if mes < 12 else 1
        ano_venc = ano if mes < 12 else ano + 1

        # FGTS — dia 20 do mês seguinte (Lei 14.438/2022 + FGTS Digital, competências desde mar/2024).
        # Em dia não-útil (sábado/domingo/feriado), ANTECIPA para o dia útil imediatamente anterior
        # (comportamento oposto à postergação das demais obrigações tributárias).
        items.append(ItemCalendario(
            titulo=f"FGTS {_mes_nome(mes)}/{ano}",
            descricao=f"Recolhimento do FGTS referente à folha de {_mes_nome(mes)}/{ano}",
            data_vencimento=_fgts_vencimento(ano_venc, mes_venc, feriados),
            regime=regime,
            tipo_obrigacao="fgts",
        ))

        # eSocial S-1200 — dia 15 do mês seguinte (folha de remunerações)
        items.append(ItemCalendario(
            titulo=f"eSocial S-1200 {_mes_nome(mes)}/{ano}",
            descricao=f"Remunerações dos trabalhadores via eSocial — {_mes_nome(mes)}/{ano}",
            data_vencimento=_dia_vencimento(ano_venc, mes_venc, 15, feriados),
            regime=regime,
            tipo_obrigacao="esocial_s1200",
        ))

        # GPS/INSS — dia 20 (LP); SN inclui INSS patronal dentro do DAS
        if incluir_gps:
            items.append(ItemCalendario(
                titulo=f"GPS/INSS {_mes_nome(mes)}/{ano}",
                descricao=f"Recolhimento INSS patronal via GPS referente a {_mes_nome(mes)}/{ano}",
                data_vencimento=_dia_vencimento(ano_venc, mes_venc, 20, feriados),
                regime=regime,
                tipo_obrigacao="gps_inss",
            ))

    return items


def _fgts_vencimento(
    ano: int,
    mes: int,
    feriados: frozenset[date] = frozenset(),
) -> date:
    """Retorna a data de recolhimento do FGTS (dia 20 do mês dado).

    Regra específica do FGTS Digital (Lei 14.438/2022): quando o dia 20 cai em
    sábado, domingo ou feriado, o recolhimento é ANTECIPADO para o dia útil
    imediatamente anterior — ao contrário das demais obrigações, que são
    postergadas (cf. ``_dia_vencimento``).
    """
    ultimo = calendar.monthrange(ano, mes)[1]
    candidato = date(ano, mes, min(20, ultimo))
    return _dia_util_anterior(candidato, feriados)


def _dia_util_anterior(d: date, feriados: frozenset[date]) -> date:
    """Antecipa ``d`` enquanto cair em sábado/domingo/feriado (retrocede 1 dia de cada vez)."""
    while d.weekday() >= 5 or d in feriados:
        d -= timedelta(days=1)
    return d


def _dia_vencimento(
    ano: int,
    mes: int,
    dia: int,
    feriados: frozenset[date] = frozenset(),
) -> date:
    """Retorna a data de vencimento ajustada para o próximo dia útil.

    Aplica IN RFB 1.300/2012 art. 26: vencimento em sábado, domingo ou feriado
    é postergado para o próximo dia útil. O argumento ``feriados`` é o conjunto
    de feriados nacionais (passado pelo caller — agenda obtém via BrasilAPI).

    Ajustes:
      * ``min(dia, ultimo)``: se o dia não existe no mês (ex.: 31/fev), usa o
        último dia do mês como base, depois posterga se cair em não-útil.
    """
    ultimo = calendar.monthrange(ano, mes)[1]
    candidato = date(ano, mes, min(dia, ultimo))
    return _proximo_dia_util(candidato, feriados)


def _proximo_dia_util(d: date, feriados: frozenset[date]) -> date:
    """Posterga ``d`` enquanto cair em sábado/domingo/feriado."""
    while d.weekday() >= 5 or d in feriados:
        d += timedelta(days=1)
    return d


def _mes_nome(mes: int) -> str:
    nomes = [
        "jan", "fev", "mar", "abr", "mai", "jun",
        "jul", "ago", "set", "out", "nov", "dez",
    ]
    return nomes[mes - 1]
