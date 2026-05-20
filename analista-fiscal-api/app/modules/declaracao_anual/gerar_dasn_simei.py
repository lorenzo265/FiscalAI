"""Gerador puro do payload DASN-SIMEI (MEI, declaração anual simplificada).

Conteúdo:
* CNPJ
* Ano-calendário
* Receita bruta anual (consolidada das DAS-MEI mensais, ou informada direto)
* Indicador de empregado contratado
* (Opcional) decomposição por atividade — comércio/indústria vs serviços

Limite legal MEI: R$81.000/ano (LC 123/2006 art. 18-A).
Limite MEI Caminhoneiro: R$251.600/ano (LC 188/2021).

Funções puras — golden test friendly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.shared.types import JsonObject

GERADOR_VERSAO = "dasn-simei-2026.05"

_LIMITE_MEI = Decimal("81000.00")
_LIMITE_MEI_CAMINHONEIRO = Decimal("251600.00")


@dataclass(frozen=True, slots=True)
class DadosDasnSimei:
    """Entradas brutas para gerar DASN-SIMEI."""

    receita_comercio_industria: Decimal = Decimal("0")
    receita_servicos: Decimal = Decimal("0")
    teve_empregado: bool = False
    eh_caminhoneiro: bool = False


@dataclass(frozen=True, slots=True)
class ResultadoDasnSimei:
    payload: JsonObject
    receita_bruta_anual: Decimal
    excedeu_limite_mei: bool
    algoritmo_versao: str = GERADOR_VERSAO


def gerar_dasn_simei(
    cnpj: str,
    ano_base: int,
    dados: DadosDasnSimei,
) -> ResultadoDasnSimei:
    """Monta o payload Integra Contador da DASN-SIMEI.

    Args:
        cnpj: CNPJ do MEI (14 dígitos).
        ano_base: Exercício a declarar.
        dados: Receitas + flags do ano.

    Returns:
        ResultadoDasnSimei com payload + flag indicando se o MEI estourou o
        limite (caso em que provavelmente foi desenquadrado e deve transitar
        para SN — chamador decide o que fazer).

    Raises:
        ValueError: receitas negativas.
    """
    if dados.receita_comercio_industria < 0 or dados.receita_servicos < 0:
        raise ValueError("Receitas DASN-SIMEI não podem ser negativas")

    receita_bruta_anual = dados.receita_comercio_industria + dados.receita_servicos
    limite = _LIMITE_MEI_CAMINHONEIRO if dados.eh_caminhoneiro else _LIMITE_MEI
    excedeu = receita_bruta_anual > limite

    payload: JsonObject = {
        "anoCalendario": ano_base,
        "identificacao": {
            "cnpj": cnpj,
            "atividadeMeiCaminhoneiro": dados.eh_caminhoneiro,
        },
        "receitas": {
            "receitaComercioIndustria": _decstr(dados.receita_comercio_industria),
            "receitaServicos": _decstr(dados.receita_servicos),
            "receitaBrutaAnual": _decstr(receita_bruta_anual),
            "limiteAplicavel": _decstr(limite),
            "excedeuLimite": excedeu,
        },
        "informacoesAuxiliares": {
            "teveEmpregadoNoAno": dados.teve_empregado,
        },
        "algoritmoVersao": GERADOR_VERSAO,
    }

    return ResultadoDasnSimei(
        payload=payload,
        receita_bruta_anual=receita_bruta_anual,
        excedeu_limite_mei=excedeu,
    )


def _decstr(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.01')):.2f}"
