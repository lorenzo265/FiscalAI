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
  * S-2300 — TSVE (Trabalhador sem Vínculo de Emprego) — Início ← Socio
             com pró-labore (categoria 723 — contribuinte individual:
             empresário/sócio de PJ). Sprint 19.6 PR1 (#14) substituiu
             o uso adaptado de S-2400 (Cadastro Beneficiário Ente
             Público/RPPS) pelo evento canônico — S-2300 é o evento
             oficial pra registrar início de prestação de serviços de
             sócios/dirigentes/autônomos sem vínculo CLT.

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

# Sprint 19.7 PR2 (#13): adiciona S-2205/2206/2230/2298/3000 (transmissão real).
ALGORITMO_VERSAO = "esocial.skeleton.v3"
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


# Sprint 19.7 PR2 (#13) — inputs dos eventos S-2205/2206/2230/2298/3000.


@dataclass(frozen=True, slots=True)
class AlteracaoCadastralInput:
    """S-2205 — alteração de dados cadastrais do trabalhador."""

    data_alteracao: date
    novo_nome: str | None = None
    nova_data_nascimento: date | None = None
    novo_estado_civil: str | None = None  # 'solteiro'|'casado'|...


@dataclass(frozen=True, slots=True)
class AlteracaoContratoInput:
    """S-2206 — alteração contratual (cargo, salário, jornada)."""

    data_alteracao: date
    novo_cargo: str | None = None
    novo_salario: Decimal | None = None
    nova_jornada_semanal_horas: Decimal | None = None
    motivo_alteracao: str = "promocao"  # 'promocao'|'reajuste'|'transferencia'


@dataclass(frozen=True, slots=True)
class AfastamentoInput:
    """S-2230 — início ou término de afastamento temporário."""

    data_inicio: date
    motivo: str  # 'doenca'|'acidente_trabalho'|'maternidade'|'servico_militar'|...
    data_fim: date | None = None  # None = afastamento ainda ativo


@dataclass(frozen=True, slots=True)
class ReintegracaoInput:
    """S-2298 — reintegração de trabalhador desligado."""

    data_efetiva_retorno: date
    data_efeitos_financeiros: date
    tipo_reintegracao: str = "reint_judicial"  # 'reint_anistia'|'reint_administrativa'|...
    numero_processo: str | None = None


@dataclass(frozen=True, slots=True)
class ExclusaoInput:
    """S-3000 — exclusão de evento previamente transmitido."""

    tipo_evento_excluido: str  # 'S-1200', 'S-2299', etc.
    nrRecibo_evento_excluido: str  # número do recibo do evento original


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

# Tabela 18 — motivos de afastamento (subset coberto na Sprint 19.7 PR2).
_MAPA_MOTIVO_AFASTAMENTO = {
    "doenca": "01",                # Acidente / doença não relacionada ao trabalho
    "acidente_trabalho": "03",     # Acidente / doença do trabalho
    "maternidade": "17",           # Licença maternidade
    "servico_militar": "07",       # Serviço militar
    "licenca_remunerada": "16",    # Licença remunerada (estatutário)
    "afastamento_sem_pgto": "15",  # Afastamento/licença sem remuneração
    "suspensao_disciplinar": "14",
}

# Tabela 28 — motivos de reintegração.
_MAPA_TIPO_REINTEGRACAO = {
    "reint_judicial": "1",         # Reintegração por decisão judicial
    "reint_anistia": "2",          # Reintegração por anistia legal
    "reint_administrativa": "3",   # Reintegração por decisão administrativa
}

# Tabela 5 — estado civil (subset).
_MAPA_ESTADO_CIVIL = {
    "solteiro": 1,
    "casado": 2,
    "divorciado": 3,
    "separado": 4,
    "viuvo": 5,
    "uniao_estavel": 6,
}

# Tabela 22 — motivos de alteração contratual.
_MAPA_MOTIVO_ALT_CONTRATO = {
    "promocao": "1",
    "reajuste": "2",
    "transferencia": "3",
    "outras": "9",
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


def gerar_s2300_inicio_tsve(
    empregador: EmpregadorInput,
    trabalhador: TrabalhadorInput,
    *,
    data_inicio: date,
    valor_referencia: Decimal,
    cad_inicial: bool = True,
    natureza_atividade_urbana: bool = True,
) -> ESocialPayload:
    """S-2300 — Início de TSVE (Trabalhador sem Vínculo de Emprego).

    Sprint 19.6 PR1 (#14): substitui ``gerar_s2400_beneficiario`` (uso
    adaptado de S-2400/RPPS que o eSocial rejeitaria em prod). S-2300 é
    o evento canônico do leiaute pra registrar início de prestação de
    serviços de **sócio recebendo pró-labore** — categoria 723
    (contribuinte individual: empresário, sócio e membro de conselho).

    Campos do leiaute S-2300 (v S-1.3):

      * ``trabSemVinc.cpfTrab/nmTrab/dtNascto`` — identificação do TSVE.
      * ``infoTSVInicio.cadIni`` — "S"=cadastramento inicial, "N"=início
        de novo período de prestação de serviços.
      * ``infoTSVInicio.dtInicio`` — data de início (entrada do sócio
        na PJ).
      * ``infoTSVInicio.tpRegPrev`` — regime previdenciário (1=RGPS).
      * ``infoTSVInicio.codCateg`` — 723 = sócio empresário CI.
      * ``infoTSVInicio.natAtividade`` — 1=urbana, 2=rural.

    ``valor_referencia`` (último pró-labore) é preservado em
    ``observacao`` — não há campo nativo no S-2300 pra valor de
    referência. Em apurações futuras (S-1200), o valor real do mês
    será fonte de verdade.
    """
    return {
        "tipo": "S-2300",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": _ide_evento(None),
        "ide_empregador": _ide_empregador(empregador),
        "trabSemVinc": {
            "cpfTrab": trabalhador.cpf,
            "nmTrab": trabalhador.nome,
            "dtNascto": (
                trabalhador.data_nascimento.isoformat()
                if trabalhador.data_nascimento
                else None
            ),
        },
        "infoTSVInicio": {
            "cadIni": "S" if cad_inicial else "N",
            "dtInicio": data_inicio.isoformat(),
            "tpRegPrev": 1,  # RGPS
            "codCateg": 723,  # contribuinte individual: empresário/sócio PJ
            "natAtividade": 1 if natureza_atividade_urbana else 2,
        },
        "observacao": f"vrReferencia={valor_referencia}",
        "algoritmo_versao": ALGORITMO_VERSAO,
    }


# ── Sprint 19.7 PR2 (#13) — Eventos S-2205/2206/2230/2298/3000 ───────────


def gerar_s2205_alteracao_cadastral(
    empregador: EmpregadorInput,
    trabalhador: TrabalhadorInput,
    alteracao: AlteracaoCadastralInput,
) -> ESocialPayload:
    """S-2205 — Alteração de Dados Cadastrais do Trabalhador.

    Eventos cabíveis: troca de nome (casamento/retificação), correção de
    data de nascimento (erro cadastral), mudança de estado civil. Aceita
    parciais — apenas os campos passados entram no bloco ``alteracao``.
    """
    nova_pessoa: ESocialPayload = {}
    if alteracao.novo_nome is not None:
        nova_pessoa["nmTrab"] = alteracao.novo_nome
    if alteracao.nova_data_nascimento is not None:
        nova_pessoa["dtNascto"] = alteracao.nova_data_nascimento.isoformat()
    if alteracao.novo_estado_civil is not None:
        cod = _MAPA_ESTADO_CIVIL.get(alteracao.novo_estado_civil)
        if cod is not None:
            nova_pessoa["estCiv"] = cod

    return {
        "tipo": "S-2205",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": _ide_evento(None),
        "ide_empregador": _ide_empregador(empregador),
        "ide_trabalhador": {"cpfTrab": trabalhador.cpf},
        "alteracao": {
            "dtAlteracao": alteracao.data_alteracao.isoformat(),
            "dadosTrabalhador": nova_pessoa,
        },
        "algoritmo_versao": ALGORITMO_VERSAO,
    }


def gerar_s2206_alteracao_contrato(
    empregador: EmpregadorInput,
    trabalhador: TrabalhadorInput,
    alteracao: AlteracaoContratoInput,
) -> ESocialPayload:
    """S-2206 — Alteração de Contrato de Trabalho (cargo, salário, jornada)."""
    info_contrato: ESocialPayload = {}
    if alteracao.novo_cargo is not None:
        info_contrato["nmCargo"] = alteracao.novo_cargo
    if alteracao.novo_salario is not None:
        info_contrato["vrSalFx"] = str(alteracao.novo_salario)
        info_contrato["undSalFixo"] = 5  # mensal
    if alteracao.nova_jornada_semanal_horas is not None:
        info_contrato["qtdHrsSem"] = str(alteracao.nova_jornada_semanal_horas)

    return {
        "tipo": "S-2206",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": _ide_evento(None),
        "ide_empregador": _ide_empregador(empregador),
        "ide_vinculo": {"cpfTrab": trabalhador.cpf},
        "alt_contratual": {
            "dtAlteracao": alteracao.data_alteracao.isoformat(),
            "tpAltContratual": _MAPA_MOTIVO_ALT_CONTRATO.get(
                alteracao.motivo_alteracao, "9"
            ),
            "infoContrato": info_contrato,
        },
        "algoritmo_versao": ALGORITMO_VERSAO,
    }


def gerar_s2230_afastamento(
    empregador: EmpregadorInput,
    trabalhador: TrabalhadorInput,
    afastamento: AfastamentoInput,
) -> ESocialPayload:
    """S-2230 — Afastamento Temporário.

    Quando ``afastamento.data_fim`` é ``None``, emite apenas o bloco
    ``infoAfastamento`` (início). Quando preenchido, anexa ``fimAfastamento``
    no mesmo evento (S-2230 de término).
    """
    cod_motivo = _MAPA_MOTIVO_AFASTAMENTO.get(afastamento.motivo, "99")
    info: ESocialPayload = {
        "dtIniAfast": afastamento.data_inicio.isoformat(),
        "codMotAfast": cod_motivo,
    }
    if afastamento.data_fim is not None:
        info["fimAfastamento"] = {
            "dtTermAfast": afastamento.data_fim.isoformat(),
        }
    return {
        "tipo": "S-2230",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": _ide_evento(None),
        "ide_empregador": _ide_empregador(empregador),
        "ide_vinculo": {"cpfTrab": trabalhador.cpf},
        "infoAfastamento": info,
        "algoritmo_versao": ALGORITMO_VERSAO,
    }


def gerar_s2298_reintegracao(
    empregador: EmpregadorInput,
    trabalhador: TrabalhadorInput,
    reintegracao: ReintegracaoInput,
) -> ESocialPayload:
    """S-2298 — Reintegração de Trabalhador Desligado."""
    info: ESocialPayload = {
        "tpReint": _MAPA_TIPO_REINTEGRACAO.get(
            reintegracao.tipo_reintegracao, "1"
        ),
        "nrProcJud": reintegracao.numero_processo,
        "dtEfeitos": reintegracao.data_efeitos_financeiros.isoformat(),
        "dtEfetRetorno": reintegracao.data_efetiva_retorno.isoformat(),
    }
    return {
        "tipo": "S-2298",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": _ide_evento(None),
        "ide_empregador": _ide_empregador(empregador),
        "ide_vinculo": {"cpfTrab": trabalhador.cpf},
        "infoReintegr": info,
        "algoritmo_versao": ALGORITMO_VERSAO,
    }


def gerar_s3000_exclusao(
    empregador: EmpregadorInput,
    exclusao: ExclusaoInput,
) -> ESocialPayload:
    """S-3000 — Exclusão de Evento previamente transmitido.

    Cancela evento por chave (tipo + nrRecibo). Não substitui — quem
    quiser regenerar tem que enviar evento novo (S-1200 com indRetif=1,
    por exemplo) depois do S-3000.
    """
    return {
        "tipo": "S-3000",
        "versao_leiaute": _VERSAO_LEIAUTE,
        "ide_evento": _ide_evento(None),
        "ide_empregador": _ide_empregador(empregador),
        "infoExclusao": {
            "tpEvento": exclusao.tipo_evento_excluido,
            "nrRecEvt": exclusao.nrRecibo_evento_excluido,
        },
        "algoritmo_versao": ALGORITMO_VERSAO,
    }
