"""Gerador puro do payload DEFIS (Simples Nacional anual).

DEFIS exige consolidação anual + dados socioeconômicos. A consolidação vem
das 12 ApuracaoFiscal mensais do tipo='das'; os campos socioeconômicos
(sócios, lucro contábil, despesas, estoque, ganho de capital) são fornecidos
pelo usuário no momento da geração.

Princípios respeitados:
* Função pura — zero I/O, zero dependência de banco. Testável via golden.
* Determinística — mesmos inputs → mesmo payload.
* Decimal-safe — usa Decimal em todo cálculo monetário; serializa como string
  para preservar precisão no JSON enviado ao SERPRO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.shared.types import JsonObject

GERADOR_VERSAO = "defis-2026.05"


@dataclass(frozen=True, slots=True)
class SocioDefis:
    """Sócio identificado para o quadro societário do DEFIS."""

    cpf: str
    nome: str
    percentual_capital: Decimal
    rendimentos_isentos: Decimal = Decimal("0")
    rendimentos_tributaveis: Decimal = Decimal("0")
    pro_labore_anual: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class ApuracaoMensalSN:
    """Snapshot mensal extraído de ApuracaoFiscal.output_jsonb."""

    competencia: str  # "YYYY-MM"
    receita_mes: Decimal
    valor_das: Decimal
    anexo: str
    anexo_efetivo: str


@dataclass(frozen=True, slots=True)
class DadosSocioeconomicos:
    """Campos socioeconômicos não-derivados de apurações — usuário informa."""

    ganho_capital_anual: Decimal = Decimal("0")
    lucro_contabil_anual: Decimal = Decimal("0")
    estoque_inicial: Decimal = Decimal("0")
    estoque_final: Decimal = Decimal("0")
    saldo_caixa_inicial: Decimal = Decimal("0")
    saldo_caixa_final: Decimal = Decimal("0")
    despesa_total_anual: Decimal = Decimal("0")
    socios: tuple[SocioDefis, ...] = field(default_factory=tuple)
    isencao_iss_anual: Decimal = Decimal("0")
    teve_funcionario: bool = False


@dataclass(frozen=True, slots=True)
class ResultadoDefis:
    """Resultado consolidado do DEFIS — pronto para persistir."""

    payload: JsonObject
    receita_bruta_anual: Decimal
    total_das_anual: Decimal
    meses_apurados: int
    algoritmo_versao: str = GERADOR_VERSAO


# ── geração ──────────────────────────────────────────────────────────────────


def gerar_defis(
    cnpj: str,
    ano_base: int,
    apuracoes: tuple[ApuracaoMensalSN, ...],
    socioeconomicos: DadosSocioeconomicos,
) -> ResultadoDefis:
    """Constrói o payload Integra Contador da DEFIS.

    Args:
        cnpj: CNPJ do contribuinte (14 dígitos).
        ano_base: Exercício a declarar (apurações devem ser deste ano).
        apuracoes: Tupla com apurações mensais já calculadas. Não precisam ser
            12 — meses ausentes são tratados como receita zero (período
            inativo legítimo no SN), mas a tupla precisa cobrir somente meses
            do ``ano_base``.
        socioeconomicos: Dados informados manualmente pelo usuário.

    Returns:
        ResultadoDefis com payload JSON pronto + métricas agregadas.

    Raises:
        ValueError: se houver apuração de competência fora de ``ano_base`` ou
            soma dos percentuais dos sócios divergir de 100% em mais de 0,01%.
    """
    _validar_competencias(apuracoes, ano_base)
    _validar_quadro_societario(socioeconomicos.socios)

    receita_bruta_anual = sum(
        (a.receita_mes for a in apuracoes), start=Decimal("0")
    )
    total_das_anual = sum((a.valor_das for a in apuracoes), start=Decimal("0"))

    payload: JsonObject = {
        "anoCalendario": ano_base,
        "identificacao": {
            "cnpj": cnpj,
            "teveFuncionarioNoAno": socioeconomicos.teve_funcionario,
        },
        "informacoesEconomicas": {
            "ganhoCapital": _decstr(socioeconomicos.ganho_capital_anual),
            "lucroContabil": _decstr(socioeconomicos.lucro_contabil_anual),
            "estoqueInicial": _decstr(socioeconomicos.estoque_inicial),
            "estoqueFinal": _decstr(socioeconomicos.estoque_final),
            "saldoCaixaInicial": _decstr(socioeconomicos.saldo_caixa_inicial),
            "saldoCaixaFinal": _decstr(socioeconomicos.saldo_caixa_final),
            "totalDespesas": _decstr(socioeconomicos.despesa_total_anual),
            "totalReceitasIsencoesIss": _decstr(socioeconomicos.isencao_iss_anual),
        },
        "receitas": {
            "receitaBrutaAnual": _decstr(receita_bruta_anual),
            "totalDasAnual": _decstr(total_das_anual),
            "mesesApurados": len(apuracoes),
            "apuracoes": [_apuracao_para_payload(a) for a in apuracoes],
        },
        "socios": [_socio_para_payload(s) for s in socioeconomicos.socios],
        "algoritmoVersao": GERADOR_VERSAO,
    }

    return ResultadoDefis(
        payload=payload,
        receita_bruta_anual=receita_bruta_anual,
        total_das_anual=total_das_anual,
        meses_apurados=len(apuracoes),
    )


# ── helpers privados ─────────────────────────────────────────────────────────


def _validar_competencias(
    apuracoes: tuple[ApuracaoMensalSN, ...], ano_base: int
) -> None:
    for a in apuracoes:
        ano_str, mes_str = a.competencia.split("-")
        if int(ano_str) != ano_base:
            raise ValueError(
                f"Apuração de competência {a.competencia} fora do ano_base "
                f"{ano_base}"
            )
        mes = int(mes_str)
        if not 1 <= mes <= 12:
            raise ValueError(f"Mês inválido em competência {a.competencia}")


_TOLERANCIA_PCT = Decimal("0.01")


def _validar_quadro_societario(socios: tuple[SocioDefis, ...]) -> None:
    if not socios:
        # DEFIS aceita declaração sem sócios listados (empresário individual);
        # o SERPRO valida pelo CNPJ, então deixamos passar.
        return
    soma = sum((s.percentual_capital for s in socios), start=Decimal("0"))
    if (soma - Decimal("100")).copy_abs() > _TOLERANCIA_PCT:
        raise ValueError(
            f"Soma dos percentuais de capital dos sócios = {soma}; esperado 100"
        )


def _apuracao_para_payload(a: ApuracaoMensalSN) -> JsonObject:
    return {
        "competencia": a.competencia,
        "receitaMes": _decstr(a.receita_mes),
        "valorDas": _decstr(a.valor_das),
        "anexo": a.anexo,
        "anexoEfetivo": a.anexo_efetivo,
    }


def _socio_para_payload(s: SocioDefis) -> JsonObject:
    return {
        "cpf": s.cpf,
        "nome": s.nome,
        "percentualCapital": _decstr(s.percentual_capital),
        "rendimentosIsentos": _decstr(s.rendimentos_isentos),
        "rendimentosTributaveis": _decstr(s.rendimentos_tributaveis),
        "proLaboreAnual": _decstr(s.pro_labore_anual),
    }


def _decstr(v: Decimal) -> str:
    """Serializa Decimal preservando 2 casas — formato esperado pelo SERPRO."""
    quantizado = v.quantize(Decimal("0.01"))
    return f"{quantizado:.2f}"
