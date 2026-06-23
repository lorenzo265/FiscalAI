"""Builders de payloads válidos para testes da Sprint 19.5 PR1.

Cada builder devolve um schema Pydantic já válido (todos os validadores
passam). Os testes que querem caso inválido sobrescrevem campos específicos
via parâmetros nomeados.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.modules.tabelas_admin.schemas import (
    AliquotaCbsIbsIn,
    AliquotaFgtsIn,
    AliquotaIcmsUfIn,
    FaixaInssIn,
    FaixaIrrfIn,
    FaixaSimplesIn,
    PresuncaoLpIn,
    VigenciaCbsIbsIn,
    VigenciaFgtsIn,
    VigenciaIcmsUfIn,
    VigenciaInssIn,
    VigenciaIrrfIn,
    VigenciaPresuncaoLpIn,
    VigenciaSimplesNacionalIn,
)

FONTE_PADRAO = "Portaria MPS/MF 1/2026, DOU 2026-01-15 seção 1 página 42"


def faixas_inss_2026() -> list[FaixaInssIn]:
    """4 faixas empregado + 1 faixa contribuinte individual — válido em 2026.

    Valores oficiais da Portaria Interministerial MPS/MF nº 13 de 09/01/2026
    (SM 2026 = R$ 1.621,00; teto = R$ 8.475,55). Antes eram estimativas
    ilustrativas; alinhados aos oficiais ao postar a tabela INSS 2026.
    """
    return [
        FaixaInssIn(
            tipo="empregado",
            faixa=1,
            valor_ate=Decimal("1621.00"),
            aliquota=Decimal("0.075"),
        ),
        FaixaInssIn(
            tipo="empregado",
            faixa=2,
            valor_ate=Decimal("2902.84"),
            aliquota=Decimal("0.09"),
        ),
        FaixaInssIn(
            tipo="empregado",
            faixa=3,
            valor_ate=Decimal("4354.27"),
            aliquota=Decimal("0.12"),
        ),
        FaixaInssIn(
            tipo="empregado",
            faixa=4,
            valor_ate=Decimal("8475.55"),
            aliquota=Decimal("0.14"),
        ),
        FaixaInssIn(
            tipo="contribuinte_individual",
            faixa=1,
            valor_ate=Decimal("8475.55"),
            aliquota=Decimal("0.11"),
        ),
    ]


def vigencia_inss_valida(**over: Any) -> VigenciaInssIn:
    base: dict[str, Any] = {
        "valid_from": date(2026, 1, 15),
        "fonte_norma": FONTE_PADRAO,
        "faixas": faixas_inss_2026(),
    }
    base.update(over)
    return VigenciaInssIn(**base)


def faixas_irrf_2026() -> list[FaixaIrrfIn]:
    """5 faixas IRRF 2026 — primeira isenta cobrindo R$ 2.428,80 (acima 1 SM)."""
    return [
        FaixaIrrfIn(
            faixa=1,
            base_ate=Decimal("2428.80"),
            aliquota=Decimal("0"),
            parcela_deduzir=Decimal("0"),
        ),
        FaixaIrrfIn(
            faixa=2,
            base_ate=Decimal("2826.65"),
            aliquota=Decimal("0.075"),
            parcela_deduzir=Decimal("182.16"),
        ),
        FaixaIrrfIn(
            faixa=3,
            base_ate=Decimal("3751.05"),
            aliquota=Decimal("0.15"),
            parcela_deduzir=Decimal("394.16"),
        ),
        FaixaIrrfIn(
            faixa=4,
            base_ate=Decimal("4664.68"),
            aliquota=Decimal("0.225"),
            parcela_deduzir=Decimal("675.49"),
        ),
        FaixaIrrfIn(
            faixa=5,
            base_ate=Decimal("999999999.99"),
            aliquota=Decimal("0.275"),
            parcela_deduzir=Decimal("908.73"),
        ),
    ]


def vigencia_irrf_valida(**over: Any) -> VigenciaIrrfIn:
    base: dict[str, Any] = {
        "valid_from": date(2026, 1, 15),
        "fonte_norma": FONTE_PADRAO,
        "deducao_dependente": Decimal("189.59"),
        "faixas": faixas_irrf_2026(),
    }
    base.update(over)
    return VigenciaIrrfIn(**base)


def vigencia_fgts_valida(**over: Any) -> VigenciaFgtsIn:
    base: dict[str, Any] = {
        "valid_from": date(2026, 1, 1),
        "fonte_norma": "Lei 8.036/1990 art. 15 — alíquotas vigentes",
        "aliquotas": [
            AliquotaFgtsIn(vinculo="clt", aliquota=Decimal("0.08")),
            AliquotaFgtsIn(
                vinculo="jovem_aprendiz", aliquota=Decimal("0.02")
            ),
            AliquotaFgtsIn(vinculo="domestico", aliquota=Decimal("0.08")),
        ],
    }
    base.update(over)
    return VigenciaFgtsIn(**base)


def faixas_simples_anexo_iii() -> list[FaixaSimplesIn]:
    """6 faixas progressivas do Anexo III (serviços — caso canônico)."""
    return [
        FaixaSimplesIn(
            faixa=1,
            rbt12_ate=Decimal("180000.00"),
            aliquota_nominal=Decimal("0.06"),
            parcela_deduzir=Decimal("0"),
        ),
        FaixaSimplesIn(
            faixa=2,
            rbt12_ate=Decimal("360000.00"),
            aliquota_nominal=Decimal("0.112"),
            parcela_deduzir=Decimal("9360"),
        ),
        FaixaSimplesIn(
            faixa=3,
            rbt12_ate=Decimal("720000.00"),
            aliquota_nominal=Decimal("0.135"),
            parcela_deduzir=Decimal("17640"),
        ),
        FaixaSimplesIn(
            faixa=4,
            rbt12_ate=Decimal("1800000.00"),
            aliquota_nominal=Decimal("0.16"),
            parcela_deduzir=Decimal("35640"),
        ),
        FaixaSimplesIn(
            faixa=5,
            rbt12_ate=Decimal("3600000.00"),
            aliquota_nominal=Decimal("0.21"),
            parcela_deduzir=Decimal("125640"),
        ),
        FaixaSimplesIn(
            faixa=6,
            rbt12_ate=Decimal("4800000.00"),
            aliquota_nominal=Decimal("0.33"),
            parcela_deduzir=Decimal("648000"),
        ),
    ]


def vigencia_simples_valida(**over: Any) -> VigenciaSimplesNacionalIn:
    base: dict[str, Any] = {
        "valid_from": date(2026, 1, 1),
        "fonte_norma": "Resolução CGSN 142/2026 — Anexo III revisado",
        "anexo": "III",
        "faixas": faixas_simples_anexo_iii(),
    }
    base.update(over)
    return VigenciaSimplesNacionalIn(**base)


def vigencia_presuncao_valida(**over: Any) -> VigenciaPresuncaoLpIn:
    base: dict[str, Any] = {
        "valid_from": date(2026, 1, 1),
        "fonte_norma": "Lei 9.249/1995 art. 15 §1º + art. 20 (vigência base)",
        "presuncoes": [
            PresuncaoLpIn(
                grupo_atividade="Comércio em geral",
                cnae_pattern="47",
                percentual_irpj=Decimal("0.08"),
                percentual_csll=Decimal("0.12"),
                prioridade=10,
            ),
            PresuncaoLpIn(
                grupo_atividade="Serviços em geral",
                cnae_pattern="62",
                percentual_irpj=Decimal("0.32"),
                percentual_csll=Decimal("0.32"),
                prioridade=50,
            ),
        ],
    }
    base.update(over)
    return VigenciaPresuncaoLpIn(**base)


def vigencia_icms_uf_valida(**over: Any) -> VigenciaIcmsUfIn:
    base: dict[str, Any] = {
        "valid_from": date(2026, 1, 1),
        "fonte_norma": "Lei estadual SP 6.374/1989 + RJ Lei 2.657/1996 (vigência atual)",
        "aliquotas": [
            AliquotaIcmsUfIn(
                uf="SP", aliquota_interna=Decimal("0.18"),
                aliquota_fecp=Decimal("0"),
            ),
            AliquotaIcmsUfIn(
                uf="RJ", aliquota_interna=Decimal("0.20"),
                aliquota_fecp=Decimal("0.02"),
            ),
        ],
    }
    base.update(over)
    return VigenciaIcmsUfIn(**base)


def vigencia_cbs_ibs_valida(**over: Any) -> VigenciaCbsIbsIn:
    base: dict[str, Any] = {
        "valid_from": date(2026, 1, 1),
        "fonte_norma": "LC 214/2025 art. 5º (fase teste informacional)",
        "algoritmo_versao": "cbs_ibs_v1",
        "aliquotas": [
            AliquotaCbsIbsIn(
                fase="teste_2026",
                regime=None,
                cnae_pattern=None,
                classificacao_lc214="geral",
                aliquota_cbs=Decimal("0.009"),
                aliquota_ibs=Decimal("0.001"),
                observacao=None,
            ),
        ],
    }
    base.update(over)
    return VigenciaCbsIbsIn(**base)


__all__ = [
    "FONTE_PADRAO",
    "faixas_inss_2026",
    "faixas_irrf_2026",
    "faixas_simples_anexo_iii",
    "vigencia_cbs_ibs_valida",
    "vigencia_fgts_valida",
    "vigencia_icms_uf_valida",
    "vigencia_inss_valida",
    "vigencia_irrf_valida",
    "vigencia_presuncao_valida",
    "vigencia_simples_valida",
]
