"""Escalas de seed (Sprint 19 PR3).

3 presets pré-definidos + um construtor livre. Toda métrica final do seed
(tenants, empresas, NF, lançamentos) deriva daqui.

Por que presets:
  * ``smoke`` é rápido o suficiente para CI e fixture de ``tests/perf/`` —
    o objetivo é só validar que o pipeline de seed e os endpoints funcionam.
  * ``moderate`` cabe num desktop dev (~5min).
  * ``full`` é o alvo declarado no PlanoBackend §11 Sprint 19 (1k empresas
    pagantes ≈ 1k tenants × 1 empresa cada na prática; aqui inflamos a 1k×5
    para stress real).

Multiplicadores:
  total_empresas = TENANTS × EMPRESAS_POR_TENANT
  total_documentos = total_empresas × MESES_HISTORICO × NF_POR_MES
  total_lancamentos = total_empresas × MESES_HISTORICO × LANC_POR_MES
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SeedCardinality:
    """Configuração de escala do seed. Tudo deriva destes números."""

    nome: str
    tenants: int
    empresas_por_tenant: int
    meses_historico: int
    nf_por_mes: int
    lanc_por_mes: int

    @property
    def total_empresas(self) -> int:
        return self.tenants * self.empresas_por_tenant

    @property
    def total_documentos(self) -> int:
        return self.total_empresas * self.meses_historico * self.nf_por_mes

    @property
    def total_lancamentos(self) -> int:
        return self.total_empresas * self.meses_historico * self.lanc_por_mes


SMOKE = SeedCardinality(
    nome="smoke",
    tenants=5,
    empresas_por_tenant=2,
    meses_historico=3,
    nf_por_mes=5,
    lanc_por_mes=10,
)
"""Smoke test — ~10 empresas, ~150 NF, ~300 lançamentos. CI-friendly (<30s)."""

MODERATE = SeedCardinality(
    nome="moderate",
    tenants=50,
    empresas_por_tenant=3,
    meses_historico=12,
    nf_por_mes=20,
    lanc_por_mes=50,
)
"""Moderate — ~150 empresas, ~36k NF, ~90k lançamentos. Desktop dev (~5min)."""

FULL = SeedCardinality(
    nome="full",
    tenants=1000,
    empresas_por_tenant=5,
    meses_historico=12,
    nf_por_mes=50,
    lanc_por_mes=200,
)
"""Full scale — ~5k empresas, ~3M NF, ~12M lançamentos. Stress test (~horas)."""


PRESETS: dict[str, SeedCardinality] = {
    "smoke": SMOKE,
    "moderate": MODERATE,
    "full": FULL,
}


def resolver_preset(nome: str) -> SeedCardinality:
    """Resolve preset por nome. Levanta ``ValueError`` se desconhecido."""
    preset = PRESETS.get(nome.lower())
    if preset is None:
        validos = ", ".join(sorted(PRESETS))
        raise ValueError(f"preset '{nome}' desconhecido — disponíveis: {validos}")
    return preset
