"""Snapshots tipados de `apuracao_fiscal.output_jsonb`.

Discriminator Pydantic v2 que substitui o acesso por string
(`out.get("irpj_total", "0")`) em consumidores (`relatorios/service.py`,
`relatorios/repo.py`).

§8.3 — O snapshot é o registro versionado do cálculo no momento. Mudanças
no algoritmo (`ALGORITMO_VERSAO` bump) podem introduzir campos novos; o
schema usa `extra='ignore'` para tolerar isso sem quebrar leitura
retroativa.

Como usar:

    from app.modules.fiscal.snapshots import (
        ApuracaoSnapshot,
        parse_apuracao_output,
    )

    snap: ApuracaoSnapshot = parse_apuracao_output(ap.tipo, ap.output_jsonb)
    # snap.valor_devido — sempre presente, normalizado por tipo
    # snap.base_calculo — Decimal | None

Tipos cobertos hoje (todos os outputs das Sprints 2, 11):
  * Simples Nacional DAS (sn.das.v4 — proporcionalização RBT12 empresa nova)
  * Lucro Presumido — IRPJ (lp.irpj.trimestral.v2)
  * Lucro Presumido — CSLL (lp.csll.trimestral.v1)
  * Lucro Presumido — PIS/COFINS cumulativo (lp.pis_cofins.cumulativo.v1)
  * ICMS mensal (icms.mensal.v1)
  * ISS (legado pré-snapshot — fallback no input_jsonb.valor)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.shared.types import JsonObject

# ─────────────────────────────────────────────────────────────────────────────
# Schema comum
# ─────────────────────────────────────────────────────────────────────────────


class _BaseSnapshot(BaseModel):
    """Configuração comum a todos os snapshots.

    `extra='ignore'` — campos novos em versões futuras do algoritmo não
    quebram o parse retroativo.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    @property
    def valor_devido(self) -> Decimal:  # pragma: no cover — abstract-ish
        raise NotImplementedError

    @property
    def base_calculo(self) -> Decimal | None:  # pragma: no cover
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Simples Nacional — DAS
# ─────────────────────────────────────────────────────────────────────────────


class DasSnapshot(_BaseSnapshot):
    tipo: Literal["das"] = "das"
    valor: Decimal
    aliquota_efetiva: Decimal | None = None
    receita_mes: Decimal | None = None
    rbt12: Decimal | None = None
    anexo_efetivo: str | None = None
    # v4: preenchido apenas quando RBT12 foi proporcionalizado (empresa nova)
    rbt12_proporcionalizado: Decimal | None = None

    @property
    def valor_devido(self) -> Decimal:
        return self.valor


# ─────────────────────────────────────────────────────────────────────────────
# Lucro Presumido — IRPJ trimestral
# ─────────────────────────────────────────────────────────────────────────────


class IrpjLpSnapshot(_BaseSnapshot):
    tipo: Literal["irpj"] = "irpj"
    irpj_total: Decimal              # bruto antes da dedução de IRRF
    irpj_devido: Decimal | None = None  # líquido após IRRF (v2+)
    irrf_consumido: Decimal | None = None
    irrf_saldo_credor: Decimal | None = None
    base_total: Decimal | None = None
    base_presumida: Decimal | None = None
    receita_bruta_trimestre: Decimal | None = None
    meses_periodo: int | None = None
    # Campos adicionais usados pela ECF (Sprint 16 PR2) — todos opcionais
    # para preservar compat retro com snapshots antigos pré-extensão.
    percentual_presuncao: Decimal | None = None
    ganhos_capital: Decimal | None = None
    receitas_aplicacoes: Decimal | None = None
    outras_adicoes: Decimal | None = None
    limite_adicional: Decimal | None = None
    irpj_normal: Decimal | None = None
    irpj_adicional: Decimal | None = None
    irrf_a_compensar: Decimal | None = None

    @property
    def valor_devido(self) -> Decimal:
        # Para DRE: usar irpj_total (despesa accrued no período).
        # Para DRE-aux-LP/caixa: usar irpj_devido (cash outflow real).
        return self.irpj_total

    @property
    def valor_caixa(self) -> Decimal:
        """Saída efetiva de caixa (líquido de IRRF compensado)."""
        return self.irpj_devido if self.irpj_devido is not None else self.irpj_total

    @property
    def base_calculo(self) -> Decimal | None:
        return self.base_total


# ─────────────────────────────────────────────────────────────────────────────
# Lucro Presumido — CSLL trimestral
# ─────────────────────────────────────────────────────────────────────────────


class CsllLpSnapshot(_BaseSnapshot):
    tipo: Literal["csll"] = "csll"
    csll: Decimal
    base_total: Decimal | None = None
    base_presumida: Decimal | None = None
    receita_bruta_trimestre: Decimal | None = None
    # Campos adicionais usados pela ECF (Sprint 16 PR2).
    percentual_presuncao: Decimal | None = None
    outras_adicoes: Decimal | None = None

    @property
    def valor_devido(self) -> Decimal:
        return self.csll

    @property
    def base_calculo(self) -> Decimal | None:
        return self.base_total


# ─────────────────────────────────────────────────────────────────────────────
# Lucro Presumido — PIS / COFINS cumulativo mensal
# ─────────────────────────────────────────────────────────────────────────────


class PisCofinsSnapshot(_BaseSnapshot):
    tipo: Literal["pis", "cofins"]
    tributo: Decimal
    base_calculo_: Decimal | None = Field(default=None, alias="base_calculo")
    aliquota: Decimal | None = None
    receita_bruta: Decimal | None = None
    exclusoes: Decimal | None = None

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    @property
    def valor_devido(self) -> Decimal:
        return self.tributo

    @property
    def base_calculo(self) -> Decimal | None:
        return self.base_calculo_


# ─────────────────────────────────────────────────────────────────────────────
# ICMS mensal
# ─────────────────────────────────────────────────────────────────────────────


class IcmsSnapshot(_BaseSnapshot):
    tipo: Literal["icms"] = "icms"
    icms_a_recolher: Decimal
    saldo_credor_a_transportar: Decimal | None = None
    debito: Decimal | None = None
    credito: Decimal | None = None
    uf: str | None = None

    @property
    def valor_devido(self) -> Decimal:
        return self.icms_a_recolher

    @property
    def base_calculo(self) -> Decimal | None:
        # ICMS não tem "base" agregada num mês — não pré-computado.
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ISS (legado — output_jsonb antigo não tem schema; fallback para input)
# ─────────────────────────────────────────────────────────────────────────────


class IssSnapshot(_BaseSnapshot):
    tipo: Literal["iss"] = "iss"
    iss: Decimal | None = None
    valor: Decimal | None = None  # fallback se output não tem `iss`

    @property
    def valor_devido(self) -> Decimal:
        if self.iss is not None:
            return self.iss
        if self.valor is not None:
            return self.valor
        return Decimal("0")


# ─────────────────────────────────────────────────────────────────────────────
# Fallback genérico — tipos novos ainda sem schema
# ─────────────────────────────────────────────────────────────────────────────


class _GenericSnapshot(_BaseSnapshot):
    """Fallback para `tipo` não modelado — devolve zero sem quebrar leitura."""

    tipo: str

    @property
    def valor_devido(self) -> Decimal:
        return Decimal("0")


# ─────────────────────────────────────────────────────────────────────────────
# Discriminated union
# ─────────────────────────────────────────────────────────────────────────────


# UP040 suprimido abaixo: alias consumido em runtime por TypeAdapter; `type`
# (PEP 695) embrulha em TypeAliasType e mudaria a parsing da union do Pydantic.
ApuracaoSnapshot: TypeAlias = Annotated[  # noqa: UP040
    DasSnapshot | IrpjLpSnapshot | CsllLpSnapshot | PisCofinsSnapshot | IcmsSnapshot | IssSnapshot,
    Field(discriminator="tipo"),
]


_ADAPTER: TypeAdapter[ApuracaoSnapshot] = TypeAdapter(ApuracaoSnapshot)


def parse_apuracao_output(
    tipo: str,
    output_jsonb: JsonObject,
    *,
    input_jsonb: JsonObject | None = None,
) -> _BaseSnapshot:
    """Faz parse do `output_jsonb` de `apuracao_fiscal` em snapshot tipado.

    Args:
        tipo: valor de `apuracao_fiscal.tipo` ('das'|'irpj'|...).
        output_jsonb: payload congelado do cálculo.
        input_jsonb: usado como fallback para ISS legado (output sem `iss`).

    Returns:
        Snapshot tipado. Para `tipo` não modelado, retorna `_GenericSnapshot`
        com `valor_devido=0` em vez de levantar — relatórios não quebram em
        tributos exóticos.
    """
    payload = {**output_jsonb, "tipo": tipo}
    if tipo == "iss" and "iss" not in payload and input_jsonb is not None:
        # Apurações ISS antigas não preencheram output — usar input.valor.
        payload["valor"] = input_jsonb.get("valor", "0")

    try:
        return _ADAPTER.validate_python(payload)
    except Exception:
        # Tipo desconhecido OU payload inválido: fallback genérico para não
        # bloquear a geração de relatórios. O zero é defensivo — o caller
        # deve logar `relatorios.snapshot.tipo_desconhecido` no consumidor.
        return _GenericSnapshot(tipo=tipo)
