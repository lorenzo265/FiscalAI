"""Skeleton de payloads eSocial (Sprint 10 PR3).

Camada 1 (determinística). Funções puras, zero I/O.

Produz dicionários JSON-safe que reproduzem a estrutura dos eventos eSocial
(leiaute S-1.3 / 2025+). O XML real (com assinatura digital ICP-Brasil e
envio à API eSocial) fica para sprint futura — por ora persistimos o dict
em ``evento_esocial.payload`` (JSONB) e ``status='preparado'``.

Eventos cobertos:

  * S-1200 — Remuneração Trabalhador RGPS         ← Holerite mensal
  * S-1210 — Pagamentos de Rendimentos do Trabalho ← Holerite ou EventoFolha
  * S-2200 — Cadastramento Inicial / Admissão     ← Funcionario
  * S-2299 — Desligamento                          ← EventoFolha (rescisão)
  * S-2400 — Cadastro Beneficiário                 ← Socio (uso adaptado para
                                                    sócio com pró-labore)

Cada gerador retorna:
  {
    "tipo": "<S-XXXX>",
    "versao_leiaute": "S-1.3",
    "ide_evento": { ... },              # identificação do evento
    "ide_empregador": { "tpInsc": 1, "nrInsc": "<CNPJ>" },
    "<bloco_especifico>": { ... },      # campos próprios do evento
    "algoritmo_versao": "esocial.skeleton.v1",
  }

Estes dicionários têm correspondência direta 1:1 com os campos XML do
leiaute oficial — quando implementarmos a geração XML, o mapeamento será
mecânico (cada chave vira tag).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.shared.types import JsonObject

ALGORITMO_VERSAO = "esocial.skeleton.v1"
_VERSAO_LEIAUTE = "S-1.3"

# Payload de evento eSocial — dict aninhado que mapeia 1:1 para tags XML do
# leiaute oficial (S-1.3). Tipagem detalhada exigiria TypedDicts por evento
# com dezenas de campos opcionais; ``JsonObject`` documenta a intenção sem
# duplicar o leiaute.
ESocialPayload = JsonObject


# ── Dataclasses de entrada (input neutro, sem dep ORM) ────────────────────


@dataclass(frozen=True, slots=True)
class EmpregadorInput:
    cnpj: str  # 14 dígitos
    razao_social: str


@dataclass(frozen=True, slots=True)
class TrabalhadorInput:
    cpf: str
    nome: str
    data_nascimento: date | None = None


@dataclass(frozen=True, slots=True)
class HoleriteInput:
    competencia: date  # dia 1
    salario_bruto: Decimal
    inss_empregado: Decimal
    irrf: Decimal
    fgts_empregador: Decimal
    valor_liquido: Decimal


@dataclass(frozen=True, slots=True)
class AdmissaoInput:
    data_admissao: date
    cargo: str | None
    salario_base: Decimal
    vinculo: str  # 'clt' | 'prazo_determinado' | 'intermitente'


@dataclass(frozen=True, slots=True)
class DesligamentoInput:
    data_desligamento: date
    motivo: str  # 'sem_justa_causa' | 'com_justa_causa' | ...
    valor_bruto_verbas: Decimal
    saldo_fgts: Decimal


@dataclass(frozen=True, slots=True)
class PagamentoInput:
    data_pagamento: date
    valor_liquido: Decimal
    periodo_referencia: date | None = None


# ── Helpers ───────────────────────────────────────────────────────────────


_MAPA_VINCULO_ESOCIAL = {
    "clt": "10",                  # Trabalhador urbano por tempo indeterminado
    "prazo_determinado": "20",    # Trabalhador urbano por prazo determinado
    "intermitente": "11",         # Trabalhador intermitente
}

_MAPA_MOTIVO_RESCISAO = {
    # Tabela 19 do eSocial (códigos sumarizados)
    "sem_justa_causa": "02",            # Rescisão sem justa causa por iniciativa do empregador
    "com_justa_causa": "03",            # Rescisão com justa causa por iniciativa do empregador
    "pedido_demissao": "07",            # Rescisão por pedido de demissão
    "mutuo_acordo": "37",               # Rescisão por acordo entre as partes (Lei 13.467/2017)
    "termino_determinado": "08",        # Término de contrato a termo
}


def _cmp_yyyymm(d: date) -> str:
    return d.strftime("%Y-%m")


def _ide_evento(periodo: date | None) -> ESocialPayload:
    return {
        "indRetif": 1,  # 1 = original
        "tpAmb": 2,     # 2 = produção restrita (sandbox)
        "procEmi": 1,   # 1 = aplicativo do empregador
        "verProc": ALGORITMO_VERSAO,
        "perApur": _cmp_yyyymm(periodo) if periodo else None,
    }


def _ide_empregador(emp: EmpregadorInput) -> ESocialPayload:
    return {"tpInsc": 1, "nrInsc": emp.cnpj}


# ── Geradores por evento ──────────────────────────────────────────────────


def gerar_s1200_remuneracao(
    empregador: EmpregadorInput,
    trabalhador: TrabalhadorInput,
    holerite: HoleriteInput,
) -> ESocialPayload:
    """S-1200 — Remuneração do Trabalhador (vinculado ao RGPS)."""
    return {
        "tipo": "S-1200",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": _ide_evento(holerite.competencia),
        "ide_empregador": _ide_empregador(empregador),
        "ide_trabalhador": {
            "cpfTrab": trabalhador.cpf,
            "nmTrab": trabalhador.nome,
        },
        "dm_dev": [
            {
                "ide_dm_dev": "001",  # identificador do demonstrativo
                "info_per_apur": {
                    "ide_estab_lot": [
                        {
                            "tpInsc": 1,
                            "nrInsc": empregador.cnpj,
                            "codLotacao": "01",
                            "det_verbas": [
                                {
                                    "cod_rubr": "1001",
                                    "ide_tab_rubr": "PADRAO",
                                    "qtd_rubr": 0,
                                    "fator_rubr": 0,
                                    "vr_unit": 0,
                                    "vr_rubr": str(holerite.salario_bruto),
                                },
                                {
                                    "cod_rubr": "2001",
                                    "ide_tab_rubr": "PADRAO",
                                    "vr_rubr": str(holerite.inss_empregado),
                                },
                                {
                                    "cod_rubr": "2002",
                                    "ide_tab_rubr": "PADRAO",
                                    "vr_rubr": str(holerite.irrf),
                                },
                            ],
                        }
                    ],
                },
            }
        ],
        "algoritmo_versao": ALGORITMO_VERSAO,
    }


def gerar_s1210_pagamento(
    empregador: EmpregadorInput,
    trabalhador: TrabalhadorInput,
    pagamento: PagamentoInput,
) -> ESocialPayload:
    """S-1210 — Pagamentos de Rendimentos do Trabalho."""
    return {
        "tipo": "S-1210",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": _ide_evento(pagamento.periodo_referencia),
        "ide_empregador": _ide_empregador(empregador),
        "ide_benef": {
            "cpfBenef": trabalhador.cpf,
            "nmBenef": trabalhador.nome,
        },
        "dt_pgto": pagamento.data_pagamento.isoformat(),
        "info_pgto": {
            "perRef": (
                _cmp_yyyymm(pagamento.periodo_referencia)
                if pagamento.periodo_referencia
                else None
            ),
            "vrLiq": str(pagamento.valor_liquido),
        },
        "algoritmo_versao": ALGORITMO_VERSAO,
    }


def gerar_s2200_admissao(
    empregador: EmpregadorInput,
    trabalhador: TrabalhadorInput,
    admissao: AdmissaoInput,
) -> ESocialPayload:
    """S-2200 — Cadastramento Inicial do Vínculo e Admissão."""
    cod_categ_esocial = _MAPA_VINCULO_ESOCIAL.get(admissao.vinculo, "10")
    return {
        "tipo": "S-2200",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": _ide_evento(None),
        "ide_empregador": _ide_empregador(empregador),
        "trabalhador": {
            "cpfTrab": trabalhador.cpf,
            "nmTrab": trabalhador.nome,
            "dtNascto": (
                trabalhador.data_nascimento.isoformat()
                if trabalhador.data_nascimento
                else None
            ),
        },
        "vinculo": {
            "matricula": None,  # gerada pela empresa
            "tpRegTrab": 1,
            "tpRegPrev": 1,
            "info_celetista": {
                "dtAdm": admissao.data_admissao.isoformat(),
                "tpAdmissao": 1,
                "indPrimEmpr": "N",
                "codCateg": int(cod_categ_esocial),
            },
            "info_contrato": {
                "nmCargo": admissao.cargo,
                "vrSalFx": str(admissao.salario_base),
                "undSalFixo": 5,  # 5 = mensal
            },
        },
        "algoritmo_versao": ALGORITMO_VERSAO,
    }


def gerar_s2299_desligamento(
    empregador: EmpregadorInput,
    trabalhador: TrabalhadorInput,
    desligamento: DesligamentoInput,
) -> ESocialPayload:
    """S-2299 — Desligamento do Trabalhador."""
    mtv = _MAPA_MOTIVO_RESCISAO.get(desligamento.motivo, "02")
    return {
        "tipo": "S-2299",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": _ide_evento(None),
        "ide_empregador": _ide_empregador(empregador),
        "ide_vinculo": {"cpfTrab": trabalhador.cpf},
        "info_deslig": {
            "mtvDeslig": mtv,
            "dtDeslig": desligamento.data_desligamento.isoformat(),
            "indPagtoAPI": "S",
            "vlrBrutoVerbas": str(desligamento.valor_bruto_verbas),
            "vlrSaldoFGTS": str(desligamento.saldo_fgts),
        },
        "algoritmo_versao": ALGORITMO_VERSAO,
    }


def gerar_s2400_beneficiario(
    empregador: EmpregadorInput,
    beneficiario: TrabalhadorInput,
    *,
    data_inicio: date,
    valor_referencia: Decimal,
) -> ESocialPayload:
    """S-2400 — Cadastro de Beneficiário.

    Uso adaptado para sócio com pró-labore: o sócio é beneficiário regular
    de pagamentos da PJ (rendimentos do trabalho — categoria 701).
    """
    return {
        "tipo": "S-2400",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": _ide_evento(None),
        "ide_empregador": _ide_empregador(empregador),
        "ide_beneficiario": {
            "cpfBenef": beneficiario.cpf,
            "nmBenef": beneficiario.nome,
            "dtNascto": (
                beneficiario.data_nascimento.isoformat()
                if beneficiario.data_nascimento
                else None
            ),
        },
        "info_benef": {
            "dtInicio": data_inicio.isoformat(),
            "codCateg": 701,  # contribuinte individual — sócio
            "vrReferencia": str(valor_referencia),
        },
        "algoritmo_versao": ALGORITMO_VERSAO,
    }
