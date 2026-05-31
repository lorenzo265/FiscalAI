"""Schemas Pydantic — pessoal/folha (Sprint 10 PR1)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Vinculo(StrEnum):
    CLT = "clt"
    PRAZO_DETERMINADO = "prazo_determinado"
    INTERMITENTE = "intermitente"


class StatusFolha(StrEnum):
    ABERTA = "aberta"
    FECHADA = "fechada"


# ── Funcionário ─────────────────────────────────────────────────────────────


class FuncionarioIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: Annotated[str, Field(min_length=3, max_length=255)]
    cpf: Annotated[str, Field(min_length=11, max_length=11, pattern=r"^\d{11}$")]
    cargo: Annotated[str | None, Field(default=None, max_length=120)]
    vinculo: Vinculo = Vinculo.CLT
    data_admissao: date
    salario_base: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    dependentes_irrf: Annotated[int, Field(ge=0, default=0)]


class FuncionarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    nome: str
    cpf: str
    cargo: str | None
    vinculo: Vinculo
    data_admissao: date
    data_demissao: date | None
    salario_base: Decimal
    dependentes_irrf: int
    ativo: bool


# ── Folha ───────────────────────────────────────────────────────────────────


class FecharFolhaOut(BaseModel):
    """Resultado de fechar a folha mensal."""

    folha_id: UUID
    competencia: date
    status: StatusFolha
    qtd_funcionarios: int
    total_proventos: Decimal
    total_inss_empregado: Decimal
    total_irrf: Decimal
    total_fgts_empregador: Decimal
    total_descontos: Decimal
    total_liquido: Decimal
    algoritmo_versao: str
    fechada_em: datetime | None


class FolhaMensalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    competencia: date
    status: StatusFolha
    qtd_funcionarios: int
    total_proventos: Decimal
    total_inss_empregado: Decimal
    total_irrf: Decimal
    total_fgts_empregador: Decimal
    total_descontos: Decimal
    total_liquido: Decimal
    algoritmo_versao: str | None
    fechada_em: datetime | None
    criado_em: datetime


# ── Holerite ────────────────────────────────────────────────────────────────


class HoleriteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    folha_mensal_id: UUID
    funcionario_id: UUID
    competencia: date
    salario_base: Decimal
    salario_bruto: Decimal
    inss_empregado: Decimal
    inss_aliquota_efetiva: Decimal
    dependentes_irrf: int
    deducao_dependentes_irrf: Decimal
    base_irrf: Decimal
    irrf: Decimal
    irrf_faixa: int
    fgts_empregador: Decimal
    fgts_aliquota: Decimal
    valor_liquido: Decimal
    algoritmo_versao: str


# ── Eventos pontuais (Sprint 10 PR2) ────────────────────────────────────────


class TipoEventoFolha(StrEnum):
    DECIMO_TERCEIRO_PRIMEIRA = "13_primeira"
    DECIMO_TERCEIRO_SEGUNDA = "13_segunda"
    FERIAS = "ferias"
    RESCISAO = "rescisao"


class RescisaoTipoIn(StrEnum):
    SEM_JUSTA_CAUSA = "sem_justa_causa"
    COM_JUSTA_CAUSA = "com_justa_causa"
    PEDIDO_DEMISSAO = "pedido_demissao"
    MUTUO_ACORDO = "mutuo_acordo"
    TERMINO_DETERMINADO = "termino_determinado"


class DecimoTerceiroIn(BaseModel):
    """Pagamento de 13º (1ª ou 2ª parcela).

    Para parcela=2: ``primeira_parcela_paga`` é o valor efetivamente adiantado
    (default = base/2 se omitido). ``avos`` reflete meses trabalhados no ano
    com a regra dos 15 dias (responsabilidade do frontend/contador derivar
    a partir de admissão/demissão — service não infere para evitar erro
    silencioso de fronteira).
    """

    model_config = ConfigDict(extra="forbid")

    ano_referencia: Annotated[int, Field(ge=2000, le=2100)]
    parcela: Annotated[int, Field(ge=1, le=2)]
    avos: Annotated[int, Field(ge=1, le=12)]
    primeira_parcela_paga: Decimal | None = None


class FeriasIn(BaseModel):
    """Pagamento de férias com 1/3 + abono pecuniário opcional (até 10 dias)."""

    model_config = ConfigDict(extra="forbid")

    periodo_inicio: date
    dias_gozados: Annotated[int, Field(ge=1, le=30)]
    dias_vendidos: Annotated[int, Field(ge=0, le=10, default=0)]


class RescisaoIn(BaseModel):
    """Rescisão trabalhista — 5 modalidades.

    Avos e dias são entradas do contador, calculados antes a partir das
    datas reais (regra dos 15 dias para 13º; período aquisitivo para férias).
    """

    model_config = ConfigDict(extra="forbid")

    tipo: RescisaoTipoIn
    data_demissao: date
    dias_trabalhados_mes_demissao: Annotated[int, Field(ge=0, le=31)]
    avos_13o: Annotated[int, Field(ge=0, le=12)]
    avos_ferias_proporcionais: Annotated[int, Field(ge=0, le=12)]
    ferias_vencidas_dias: Annotated[int, Field(ge=0, le=30, default=0)]
    saldo_fgts_acumulado: Annotated[Decimal, Field(ge=0, decimal_places=2)]


class EventoFolhaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    funcionario_id: UUID
    tipo: TipoEventoFolha
    data_evento: date
    ano_referencia: int | None
    periodo_inicio: date | None
    periodo_fim: date | None
    valor_bruto: Decimal
    inss_empregado: Decimal
    irrf: Decimal
    fgts_empregador: Decimal
    multa_fgts: Decimal
    valor_liquido: Decimal
    detalhes: dict[str, object]
    algoritmo_versao: str
    criado_em: datetime


# ── Sócio / Pró-labore / Distribuição (Sprint 10 PR3) ───────────────────────


class BaseCalculoIn(StrEnum):
    PRESUNCAO_LP = "presuncao_lp"
    SIMPLES_DENTRO_DAS = "simples_dentro_das"
    LUCRO_CONTABIL = "lucro_contabil"
    MEI = "mei"


class TipoEventoESocialIn(StrEnum):
    S_1200 = "S-1200"
    S_1210 = "S-1210"
    S_2200 = "S-2200"
    S_2299 = "S-2299"
    # Sprint 19.6 PR1 (#14): S-2400 substituído por S-2300 (TSVE — evento
    # canônico do leiaute pra registrar sócio com pró-labore).
    S_2300 = "S-2300"


class SocioIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: Annotated[str, Field(min_length=3, max_length=255)]
    cpf: Annotated[str, Field(min_length=11, max_length=11, pattern=r"^\d{11}$")]
    percentual_participacao: Annotated[
        Decimal, Field(ge=0, le=100, decimal_places=4, default=Decimal("0"))
    ]
    data_entrada: date
    dependentes_irrf: Annotated[int, Field(ge=0, default=0)]


class SocioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    nome: str
    cpf: str
    percentual_participacao: Decimal
    data_entrada: date
    data_saida: date | None
    dependentes_irrf: int
    ativo: bool


class ProlaboreIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    competencia: date  # dia 1 (validado no service)
    valor_bruto: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    aliquota_inss: Annotated[
        Decimal, Field(ge=0, le=1, decimal_places=4, default=Decimal("0.1100"))
    ]


class ProlaboreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    socio_id: UUID
    competencia: date
    valor_bruto: Decimal
    base_inss: Decimal
    aliquota_inss: Decimal
    inss_socio: Decimal
    base_irrf: Decimal
    irrf: Decimal
    irrf_faixa: int
    valor_liquido: Decimal
    algoritmo_versao: str


class DistribuicaoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_distribuicao: date
    valor: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    # Sprint 19.7 PR1 (#15): quando None, service calcula automaticamente
    # via `DistribuicaoService._apurar_limite_isento_automatico` a partir
    # da receita do período + presunção SCD (LP) ou anexo (SN) - impostos
    # pagos. Admin pode override passando valor explícito.
    limite_isento_apurado: (
        Annotated[Decimal, Field(ge=0, decimal_places=2)] | None
    ) = None
    base_calculo_referencia: BaseCalculoIn


class DistribuicaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    socio_id: UUID
    data_distribuicao: date
    valor: Decimal
    limite_isento_apurado: Decimal
    valor_isento: Decimal
    valor_tributavel: Decimal
    irrf_retido: Decimal
    base_calculo_referencia: str
    algoritmo_versao: str


class EsocialGerarIn(BaseModel):
    """Solicitação de geração de evento eSocial — referência polimórfica.

    ``referencia_id`` aponta para:
      * S-1200 → holerite.id
      * S-1210 → holerite.id (pagamento gera-se a partir da folha) OU evento_folha.id
      * S-2200 → funcionario.id
      * S-2299 → evento_folha.id (rescisão)
      * S-2400 → socio.id
    """

    model_config = ConfigDict(extra="forbid")

    tipo_evento: TipoEventoESocialIn
    referencia_id: UUID
    data_pagamento: date | None = None  # obrigatório só para S-1210


class EventoESocialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    tipo_evento: TipoEventoESocialIn
    referencia_tipo: str
    referencia_id: UUID
    periodo_apuracao: date | None
    payload: dict[str, object]
    status: str
    protocolo: str | None
    algoritmo_versao: str
    criado_em: datetime
    transmitido_em: datetime | None
    processado_em: datetime | None
