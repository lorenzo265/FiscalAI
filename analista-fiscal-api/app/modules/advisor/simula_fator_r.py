"""Simulação do Fator R — Anexo III vs Anexo V (Sprint 15 PR2).

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * LC 123/2006 art. 18-A (criação do Fator R).
  * Resolução CGSN 140/2018 art. 26 §1º — Fator R = folha_12m / receita_12m.
  * Quando Fator R >= 28%, atividade migra do Anexo V para o Anexo III
    (alíquotas significativamente menores em quase todas as faixas).

**Aplicabilidade:**

  Só serviços listados no art. 18-A §5º-A (LC 123) — fisioterapia, advocacia,
  arquitetura, engenharia, contabilidade, consultoria, marketing etc. Para
  empresas dessas atividades, o sistema declara ``anexo_simples='III'`` ou
  ``'V'`` e o ``resolver_anexo_fator_r`` (em ``fiscal.calcula_das``) escolhe
  o anexo efetivo a cada apuração.

**O que esta simulação responde:**

  "Vale a pena aumentar o pró-labore/folha para atingir Fator R 28% e
  migrar do Anexo V para o III?"

  Compara DAS mensal nos dois anexos com mesmas bases (RBT12 = receita_12m,
  receita_mes = receita média), calcula economia anualizada e identifica
  quanto de folha falta para cruzar o boundary 28%.

**Edge cases tratados:**

  * ``receita_12m == 0``  → ``SemDadosParaSugestao`` (sem base).
  * ``folha_12m == 0``     → Fator R = 0 (válido — empresa sem folha).
  * ``anexo != III/V``     → ``FatorRNaoAplicavel`` (sugestão não cabe).
  * Boundary exato 28,00% → resolve para Anexo III (conforme ``>=`` da norma).

Quantização: Decimal 28 dígitos; valor monetário 2 casas (HALF_EVEN),
fator_r e alíquotas 4 casas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

from app.modules.fiscal.calcula_das import FaixaDAS, calcular_das
from app.shared.exceptions import SemDadosParaSugestao

getcontext().prec = 28

ALGORITMO_VERSAO = "advisor.fator-r.v1"

_CENT = Decimal("0.01")
_PCT_DISPLAY = Decimal("0.0001")
_ZERO = Decimal("0")
_FATOR_R_LIMIAR = Decimal("0.28")  # CGSN 140/2018 art. 26 §1º
_OBSERVACAO_ESTIMATIVA = (
    "Estimativa preliminar (LC 123/2006 art. 18-A + Res. CGSN 140/2018 art. 26). "
    "Considera receita média mensal dos últimos 12m; meses futuros podem variar. "
    "Não considera encargos adicionais do aumento de pró-labore."
)


@dataclass(frozen=True, slots=True)
class SimulacaoFatorR:
    """Resultado da simulação Anexo III vs Anexo V."""

    fator_r_atual: Decimal  # 4 casas (0.2800 = 28,00%)
    fator_r_limiar: Decimal  # 0.2800 (constante CGSN 140/2018)
    folha_12m: Decimal  # input (2 casas)
    receita_12m: Decimal  # input (2 casas)
    folha_necessaria_28pct: Decimal  # 2 casas
    gap_folha_anual: Decimal  # 2 casas (0 se já está em fator >= 28%)
    receita_mes_referencia: Decimal  # média mensal (2 casas)
    das_anexo_iii_mensal: Decimal
    das_anexo_v_mensal: Decimal
    economia_mensal: Decimal  # das_v − das_iii (positivo = Anexo III vence)
    economia_anual_estimada: Decimal  # economia_mensal × 12
    anexo_atual_efetivo: str  # "III" ou "V" — onde a empresa está hoje
    anexo_recomendado: str  # "III" ou "V" — onde deveria estar
    deve_migrar: bool  # True se anexo atual ≠ recomendado e economia > R$ 0
    competencia_referencia: date
    fonte_norma: str = "LC 123/2006 art. 18-A; Res. CGSN 140/2018 art. 26"
    observacao_estimativa: str = _OBSERVACAO_ESTIMATIVA
    algoritmo_versao: str = ALGORITMO_VERSAO


def simular_fator_r(
    *,
    folha_12m: Decimal,
    receita_12m: Decimal,
    competencia: date,
    faixas_anexo_iii: list[FaixaDAS],
    faixas_anexo_v: list[FaixaDAS],
    uf: str | None = None,
) -> SimulacaoFatorR:
    """Compara DAS mensal nos Anexos III e V para a mesma base RBT12.

    Args:
        folha_12m: soma de holerites + pró-labore dos últimos 12 meses (BRL).
        receita_12m: RBT12 da empresa (BRL).
        competencia: data dentro do mês de referência (usada para metadado).
        faixas_anexo_iii: tabela SCD do Anexo III vigente em ``competencia``.
        faixas_anexo_v: tabela SCD do Anexo V vigente em ``competencia``.
        uf: UF da empresa (informativa; passada para ``calcular_das``).

    Returns:
        ``SimulacaoFatorR`` imutável com gap, economia anual e recomendação.

    Raises:
        SemDadosParaSugestao: ``receita_12m == 0`` (não há base para razão).
        ValueError: folha_12m negativa.
    """
    if folha_12m < _ZERO:
        raise ValueError(f"folha_12m não pode ser negativa: {folha_12m}")
    if receita_12m <= _ZERO:
        raise SemDadosParaSugestao(
            "Empresa sem receita nos últimos 12 meses — Fator R indefinido."
        )
    if not faixas_anexo_iii or not faixas_anexo_v:
        raise ValueError("faixas_anexo_iii e faixas_anexo_v não podem ser vazias")

    fator_r_bruto = folha_12m / receita_12m
    fator_r = fator_r_bruto.quantize(_PCT_DISPLAY, rounding=ROUND_HALF_EVEN)

    folha_necessaria_28 = (receita_12m * _FATOR_R_LIMIAR).quantize(
        _CENT, rounding=ROUND_HALF_EVEN
    )
    gap_folha = max(_ZERO, folha_necessaria_28 - folha_12m).quantize(
        _CENT, rounding=ROUND_HALF_EVEN
    )

    receita_mes_ref = (receita_12m / Decimal(12)).quantize(
        _CENT, rounding=ROUND_HALF_EVEN
    )

    das_iii = calcular_das(
        rbt12=receita_12m,
        receita_mes=receita_mes_ref,
        faixas=faixas_anexo_iii,
        anexo="III",
        anexo_efetivo="III",
        fator_r=fator_r,
        uf=uf,
    )
    das_v = calcular_das(
        rbt12=receita_12m,
        receita_mes=receita_mes_ref,
        faixas=faixas_anexo_v,
        anexo="V",
        anexo_efetivo="V",
        fator_r=fator_r,
        uf=uf,
    )

    economia_mensal = (das_v.valor - das_iii.valor).quantize(
        _CENT, rounding=ROUND_HALF_EVEN
    )
    economia_anual = (economia_mensal * Decimal(12)).quantize(
        _CENT, rounding=ROUND_HALF_EVEN
    )

    anexo_atual = "III" if fator_r >= _FATOR_R_LIMIAR else "V"
    anexo_recomendado = "III" if das_iii.valor < das_v.valor else "V"
    deve_migrar = (
        anexo_recomendado != anexo_atual and abs(economia_mensal) > _ZERO
    )

    return SimulacaoFatorR(
        fator_r_atual=fator_r,
        fator_r_limiar=_FATOR_R_LIMIAR,
        folha_12m=folha_12m.quantize(_CENT, rounding=ROUND_HALF_EVEN),
        receita_12m=receita_12m.quantize(_CENT, rounding=ROUND_HALF_EVEN),
        folha_necessaria_28pct=folha_necessaria_28,
        gap_folha_anual=gap_folha,
        receita_mes_referencia=receita_mes_ref,
        das_anexo_iii_mensal=das_iii.valor,
        das_anexo_v_mensal=das_v.valor,
        economia_mensal=economia_mensal,
        economia_anual_estimada=economia_anual,
        anexo_atual_efetivo=anexo_atual,
        anexo_recomendado=anexo_recomendado,
        deve_migrar=deve_migrar,
        competencia_referencia=competencia,
    )
