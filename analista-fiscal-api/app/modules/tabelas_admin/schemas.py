"""Schemas Pydantic v2 do painel admin de tabelas tributárias (Sprint 19.5 PR1).

7 schemas de entrada (1 por tipo) + 1 schema de saída (log de auditoria).

Convenções aplicadas em **todos** os inputs:

  * ``ConfigDict(extra='forbid', str_strip_whitespace=True)`` — payload rígido.
    Campo desconhecido → 422 antes de chegar no service (defesa em
    profundidade contra typo do admin postando JSON).
  * ``valid_from: date`` — primeiro dia do mês ou ano (validado no validador
    puro, não aqui — Pydantic só garante que é data válida).
  * ``fonte_norma: str`` com ``min_length=10`` — citação obrigatória §8.5.
    Mensagem típica: "Portaria MPS/MF 1/2026, DOU 2026-01-15 seção 1 pág 42"
    (52 chars).
  * ``idempotency_key: UUID | None`` — opcional. Se ausente, o service
    computa ``uuid5(NS_TABELA_ADMIN, "{tipo}|{valid_from}|sha256(payload)")``
    automaticamente; passar valor explícito permite que o admin gere a chave
    do lado dele (útil para retry seguro em rede instável).
  * Alíquotas como ``Decimal`` com ``ge=0, le=1`` — rejeita "7,5" (exigiria
    string parse com vírgula). Admin envia "0.075", "0.14", etc.

Schemas de saída usam ``from_attributes=True`` para serializar diretamente
do modelo SQLAlchemy ``VigenciaTabelaLog``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ── Tipos de tabela aceitos pelo painel admin ───────────────────────────────
#
# Espelho do CHECK constraint em ``vigencia_tabela_log.tipo_tabela`` (migration
# 0042). Centralizado aqui para que o router/service não dupliquem a string.

TIPOS_TABELA_SUPORTADOS: Final[tuple[str, ...]] = (
    "inss",
    "irrf",
    "fgts",
    "simples_nacional",
    "presuncao_lp",
    "icms_uf",
    "cbs_ibs",
)


# ── Field aliases reutilizáveis ─────────────────────────────────────────────


FonteNorma = Annotated[str, Field(min_length=10, max_length=2000)]
"""Citação obrigatória §8.5 — referência completa da norma publicada."""

AliquotaDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), max_digits=7, decimal_places=4),
]
"""Alíquota em [0, 1] (formato decimal, NÃO percentual)."""

ValorMoeda = Annotated[
    Decimal,
    Field(ge=Decimal("0"), max_digits=14, decimal_places=2),
]
"""Valor monetário em R$ — NUMERIC(14,2) no DB."""


_CONFIG_INPUT = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _BaseInput(BaseModel):
    """Campos comuns a toda postagem de vigência."""

    model_config = _CONFIG_INPUT

    valid_from: date
    fonte_norma: FonteNorma
    idempotency_key: UUID | None = None


# ── INSS ────────────────────────────────────────────────────────────────────


class FaixaInssIn(BaseModel):
    model_config = _CONFIG_INPUT

    tipo: Literal["empregado", "contribuinte_individual"]
    faixa: Annotated[int, Field(ge=1, le=4)]
    valor_ate: ValorMoeda
    aliquota: AliquotaDecimal


class VigenciaInssIn(_BaseInput):
    """Tabela INSS — empregado (4 faixas progressivas) + contribuinte individual
    (1 faixa plana até o teto). Uma POST cobre ambos os tipos da mesma Portaria.
    """

    faixas: Annotated[list[FaixaInssIn], Field(min_length=1, max_length=10)]


# ── IRRF ────────────────────────────────────────────────────────────────────


class FaixaIrrfIn(BaseModel):
    model_config = _CONFIG_INPUT

    faixa: Annotated[int, Field(ge=1, le=5)]
    base_ate: ValorMoeda
    aliquota: AliquotaDecimal
    parcela_deduzir: ValorMoeda


class VigenciaIrrfIn(_BaseInput):
    """Tabela IRRF mensal — 5 faixas + dedução fixa por dependente.

    ``deducao_dependente`` é top-level porque vale para a vigência inteira;
    o service propaga em todas as 5 linhas inseridas.
    """

    deducao_dependente: ValorMoeda
    faixas: Annotated[list[FaixaIrrfIn], Field(min_length=5, max_length=5)]


# ── FGTS ────────────────────────────────────────────────────────────────────


class AliquotaFgtsIn(BaseModel):
    model_config = _CONFIG_INPUT

    vinculo: Literal["clt", "jovem_aprendiz", "domestico"]
    aliquota: AliquotaDecimal


class VigenciaFgtsIn(_BaseInput):
    """Tabela FGTS por vínculo (CLT 8%, jovem aprendiz 2%, doméstico 8%).

    Lei 8.036/1990 art. 15 — mudança raríssima. Schema simétrico para o
    caso (improvável) de Lei reajustar.
    """

    aliquotas: Annotated[
        list[AliquotaFgtsIn], Field(min_length=1, max_length=3)
    ]


# ── Simples Nacional ────────────────────────────────────────────────────────


class FaixaSimplesIn(BaseModel):
    model_config = _CONFIG_INPUT

    faixa: Annotated[int, Field(ge=1, le=6)]
    rbt12_ate: ValorMoeda
    aliquota_nominal: AliquotaDecimal
    parcela_deduzir: ValorMoeda


class VigenciaSimplesNacionalIn(_BaseInput):
    """Tabela Simples Nacional — um POST por anexo (Resolução CGSN pode mudar
    só 1 anexo). 6 faixas progressivas por anexo (LC 123/2006).
    """

    anexo: Literal["I", "II", "III", "IV", "V"]
    faixas: Annotated[list[FaixaSimplesIn], Field(min_length=6, max_length=6)]


# ── Presunção Lucro Presumido ───────────────────────────────────────────────


class PresuncaoLpIn(BaseModel):
    model_config = _CONFIG_INPUT

    grupo_atividade: Annotated[str, Field(min_length=2, max_length=60)]
    cnae_pattern: Annotated[str, Field(min_length=2, max_length=20)] | None = (
        None
    )
    percentual_irpj: AliquotaDecimal
    percentual_csll: AliquotaDecimal
    limite_receita_anual: ValorMoeda | None = None
    prioridade: Annotated[int, Field(ge=0, le=999)] = 50


class VigenciaPresuncaoLpIn(_BaseInput):
    """Presunções de IRPJ/CSLL por atividade — Lei 9.249/1995 art. 15 §1º + 20.

    Pode postar muitas linhas em uma única vigência (atualização do quadro
    completo). Match por ``cnae_pattern`` com ``prioridade`` como desempate.
    """

    presuncoes: Annotated[
        list[PresuncaoLpIn], Field(min_length=1, max_length=200)
    ]


# ── ICMS por UF ─────────────────────────────────────────────────────────────


class AliquotaIcmsUfIn(BaseModel):
    model_config = _CONFIG_INPUT

    uf: Annotated[str, Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")]
    aliquota_interna: AliquotaDecimal
    aliquota_fecp: AliquotaDecimal = Decimal("0")
    # Sprint 19.6 PR1 (#33) — dia do mês seguinte de vencimento ICMS.
    # Default 10 = Convênio ICMS 92/2006. Range 1-28 garante validade
    # em qualquer mês (fevereiro inclusive). Para empresas Simples
    # Nacional vence o DAS (dia 20) e este campo é irrelevante.
    dia_vencimento_padrao: Annotated[int, Field(ge=1, le=28)] = 10


class VigenciaIcmsUfIn(_BaseInput):
    """Alíquotas internas ICMS por UF. Pode postar 1 UF (mudança local) ou
    todas as 27 (atualização geral).
    """

    aliquotas: Annotated[
        list[AliquotaIcmsUfIn], Field(min_length=1, max_length=27)
    ]


# ── CBS / IBS (Reforma Tributária) ──────────────────────────────────────────


class AliquotaCbsIbsIn(BaseModel):
    model_config = _CONFIG_INPUT

    fase: Annotated[str, Field(min_length=3, max_length=30)]
    regime: Annotated[str, Field(min_length=2, max_length=20)] | None = None
    cnae_pattern: Annotated[str, Field(min_length=2, max_length=20)] | None = (
        None
    )
    classificacao_lc214: (
        Literal["geral", "reducao_60", "reducao_30", "regime_diferenciado"]
        | None
    ) = None
    aliquota_cbs: AliquotaDecimal
    aliquota_ibs: AliquotaDecimal
    observacao: Annotated[str, Field(max_length=2000)] | None = None


class VigenciaCbsIbsIn(_BaseInput):
    """Alíquotas CBS/IBS — Reforma Tributária (LC 214/2025 + PLP 68/2024).

    O modelo ``AliquotaCbsIbs`` tem ``algoritmo_versao`` próprio (não SCD da
    norma — é versão do algoritmo de cálculo CBS/IBS). Top-level neste
    schema porque é constante para toda a vigência postada.
    """

    algoritmo_versao: Annotated[str, Field(min_length=3, max_length=50)]
    aliquotas: Annotated[
        list[AliquotaCbsIbsIn], Field(min_length=1, max_length=200)
    ]


# ── Saída ───────────────────────────────────────────────────────────────────


class VigenciaTabelaLogOut(BaseModel):
    """Log de auditoria devolvido em todo POST aceito (e nos GET historico)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tipo_tabela: str
    valid_from: date
    fonte_norma: str
    idempotency_key: UUID
    registros_criados: int
    criado_em: datetime
    usuario_admin_id: UUID | None = None


# ── Vigente snapshot (devolvido em GET /vigente?em=...) ─────────────────────


class VigenciaSnapshotOut(BaseModel):
    """Snapshot da vigência ativa em uma data — devolvido pelo GET vigente.

    Estrutura genérica: a chave de domínio (anexo, faixa, vinculo, uf,
    grupo_atividade etc.) sai dentro de ``registros`` como ``dict``. UI
    consome para pré-visualizar antes de postar nova versão.
    """

    model_config = ConfigDict(from_attributes=False)

    tipo_tabela: str
    em: date
    registros: list[dict[str, str | int | None]]


__all__ = [
    "TIPOS_TABELA_SUPORTADOS",
    "AliquotaCbsIbsIn",
    "AliquotaFgtsIn",
    "AliquotaIcmsUfIn",
    "FaixaInssIn",
    "FaixaIrrfIn",
    "FaixaSimplesIn",
    "PresuncaoLpIn",
    "VigenciaCbsIbsIn",
    "VigenciaFgtsIn",
    "VigenciaIcmsUfIn",
    "VigenciaInssIn",
    "VigenciaIrrfIn",
    "VigenciaPresuncaoLpIn",
    "VigenciaSimplesNacionalIn",
    "VigenciaSnapshotOut",
    "VigenciaTabelaLogOut",
]
