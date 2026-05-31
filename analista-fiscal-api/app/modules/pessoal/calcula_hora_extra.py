"""Cálculo de hora extra, adicional noturno e desconto por falta.

Sprint 19.8 PR1 (#12). Camada 1 (determinística). Funções puras, zero I/O,
golden-tested. Resolve a pendência "vínculo intermitente + horas
trabalhadas variáveis" — Sprint 10 PR1 só calculava salário fixo mensal.

**Regras CLT cobertas:**

  * **Hora extra** — Art. 7º XVI CF/88: mínimo de 50% sobre hora normal.
    Hora normal = ``salario_mensal / (jornada_semanal × 4.5)`` (220h/mês
    pra jornada 44h/semana). Adicionais maiores (100% domingo/feriado)
    via parâmetro ``percentual_adicional``.

  * **Adicional noturno** — Art. 73 CLT: 20% sobre hora normal das 22h às
    5h. A hora noturna é reduzida (52min30s = 1h noturna), mas isso é
    aplicação prática controversa — usamos a forma mais simples (sem
    redução horária; admin que ajustar se necessário).

  * **Desconto de falta** — Falta injustificada desconta ``salario_diário
    × dias_faltados``. Salário diário = ``salario_mensal / 30`` (regra
    geral CLT independente do mês ter 28/29/30/31 dias).

**Fora de escopo (out-of-scope §8.11):**

  * Persistência em ``evento_folha`` com novos tipos (``hora_extra``,
    ``adicional_noturno``, ``falta``) — exigiria migration do CHECK
    constraint. Entra em sprint dedicada quando primeiro cliente do
    perfil aparecer no piloto.
  * Integração na folha mensal ``calcula_holerite`` — admin chama o
    cálculo standalone e inclui o valor manualmente nos eventos.
  * Trabalho intermitente Lei 13.467/2017 (CLT art. 452-A) com
    convocação prévia — requer modelo de jornada variável; sprint
    futura.

**Pré-condições verificadas:**

  * salário base > 0
  * jornada semanal entre 12 e 44 (CLT máximo)
  * horas trabalhadas > 0
  * percentual adicional entre 0.5 (50%) e 2.0 (200%)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Final

ALGORITMO_VERSAO: Final = "hora_extra.v1"

_ZERO = Decimal("0")
_DIAS_MES_REGRA_GERAL = Decimal("30")
# Súmula 431 TST — base de cálculo trabalhista usa fator 5 (semanas/mês):
# 44h × 5 = 220h/mês; 40h × 5 = 200h/mês; etc.
_SEMANAS_MES = Decimal("5")
_QUANTIZE = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class ResultadoHoraExtra:
    """Valor + memória de cálculo (auditável)."""

    valor: Decimal
    salario_hora_normal: Decimal
    horas_calculadas: Decimal
    percentual_adicional: Decimal
    algoritmo_versao: str = ALGORITMO_VERSAO


@dataclass(frozen=True, slots=True)
class ResultadoFalta:
    valor_desconto: Decimal
    salario_diario: Decimal
    dias_faltados: int
    algoritmo_versao: str = ALGORITMO_VERSAO


def _validar_salario(salario_mensal: Decimal) -> None:
    if salario_mensal <= _ZERO:
        raise ValueError(
            f"salario_mensal deve ser > 0, recebeu {salario_mensal}"
        )


def _validar_jornada(jornada_semanal_horas: Decimal) -> None:
    if jornada_semanal_horas < Decimal("12") or jornada_semanal_horas > Decimal("44"):
        raise ValueError(
            f"jornada_semanal_horas fora do intervalo CLT [12, 44]: "
            f"{jornada_semanal_horas}"
        )


def calcular_salario_hora(
    salario_mensal: Decimal,
    jornada_semanal_horas: Decimal,
) -> Decimal:
    """Salário-hora normal (CLT § padrão 220h/mês para jornada 44h/sem).

    Fórmula: ``salario_mensal / (jornada_semanal × 4.5)``.
    Resultado com 4 casas pra preservar precisão antes de multiplicar
    por horas extras.
    """
    _validar_salario(salario_mensal)
    _validar_jornada(jornada_semanal_horas)
    horas_mes = jornada_semanal_horas * _SEMANAS_MES
    return (salario_mensal / horas_mes).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_EVEN
    )


def calcular_hora_extra(
    *,
    salario_mensal: Decimal,
    jornada_semanal_horas: Decimal,
    horas_extras: Decimal,
    percentual_adicional: Decimal = Decimal("0.5"),
) -> ResultadoHoraExtra:
    """Valor a pagar de hora extra (sem reflexos em DSR/13º/férias).

    Default ``percentual_adicional=0.5`` (50% CLT mínimo). Para domingo
    /feriado, passar ``1.0`` (100%).
    """
    if horas_extras <= _ZERO:
        raise ValueError(
            f"horas_extras deve ser > 0, recebeu {horas_extras}"
        )
    if percentual_adicional < Decimal("0.5") or percentual_adicional > Decimal("2.0"):
        raise ValueError(
            f"percentual_adicional fora de [0.5, 2.0]: {percentual_adicional}"
        )
    hora_normal = calcular_salario_hora(salario_mensal, jornada_semanal_horas)
    valor_hora_extra = hora_normal * (Decimal("1") + percentual_adicional)
    total = (valor_hora_extra * horas_extras).quantize(
        _QUANTIZE, rounding=ROUND_HALF_EVEN
    )
    return ResultadoHoraExtra(
        valor=total,
        salario_hora_normal=hora_normal,
        horas_calculadas=horas_extras,
        percentual_adicional=percentual_adicional,
    )


def calcular_adicional_noturno(
    *,
    salario_mensal: Decimal,
    jornada_semanal_horas: Decimal,
    horas_noturnas: Decimal,
    percentual: Decimal = Decimal("0.20"),
) -> ResultadoHoraExtra:
    """Valor do adicional noturno (CLT art. 73 — 20% sobre hora normal).

    Algumas categorias têm percentual maior via CCT (até 35-50%) — admin
    informa explicitamente. Função pura — adicional noturno não inclui o
    salário base normal (esse já vem na folha mensal); aqui retorna **só
    o adicional** (a diferença entre hora noturna e hora diurna).
    """
    if horas_noturnas <= _ZERO:
        raise ValueError(
            f"horas_noturnas deve ser > 0, recebeu {horas_noturnas}"
        )
    if percentual <= _ZERO or percentual > Decimal("1.0"):
        raise ValueError(f"percentual fora de (0, 1.0]: {percentual}")
    hora_normal = calcular_salario_hora(salario_mensal, jornada_semanal_horas)
    valor = (hora_normal * percentual * horas_noturnas).quantize(
        _QUANTIZE, rounding=ROUND_HALF_EVEN
    )
    return ResultadoHoraExtra(
        valor=valor,
        salario_hora_normal=hora_normal,
        horas_calculadas=horas_noturnas,
        percentual_adicional=percentual,
    )


def calcular_desconto_falta(
    *,
    salario_mensal: Decimal,
    dias_faltados: int,
) -> ResultadoFalta:
    """Desconto por falta injustificada (CLT regra geral 30 dias/mês).

    Considera apenas o dia faltado; descontos de DSR proporcionais a
    faltas (art. 6º Lei 605/49) ficam para sprint dedicada — admin
    informa diretamente quantos dias descontar.
    """
    _validar_salario(salario_mensal)
    if dias_faltados <= 0 or dias_faltados > 30:
        raise ValueError(
            f"dias_faltados fora de [1, 30]: {dias_faltados}"
        )
    salario_diario = (salario_mensal / _DIAS_MES_REGRA_GERAL).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_EVEN
    )
    desconto = (salario_diario * Decimal(dias_faltados)).quantize(
        _QUANTIZE, rounding=ROUND_HALF_EVEN
    )
    return ResultadoFalta(
        valor_desconto=desconto,
        salario_diario=salario_diario,
        dias_faltados=dias_faltados,
    )
