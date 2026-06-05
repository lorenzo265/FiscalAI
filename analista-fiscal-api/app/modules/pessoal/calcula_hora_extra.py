"""Cálculo de hora extra, adicional noturno e desconto por falta.

Sprint 19.8 PR1 (#12). Camada 1 (determinística). Funções puras, zero I/O,
golden-tested. Resolve a pendência "vínculo intermitente + horas
trabalhadas variáveis" — Sprint 10 PR1 só calculava salário fixo mensal.

FA8 m4 (2026-06-04): corrigido o adicional noturno para usar a hora noturna
reduzida (52min30s = 7/8 de hora real) conforme CLT art. 73 §1º. O adicional
de 20% incide sobre o valor-hora normal, mas o número de horas noturnas é
convertido para horas-reduzidas: ``horas_noturnas_reduzidas = horas ÷ (52,5/60)``.
Isso aumenta a base do adicional em ~14,3% — a empresa paga mais horas
"nominais" noturnas porque cada uma delas é mais curta. ALGORITMO_VERSAO
bumped para "hora_extra.v2".

FA8 m5 (2026-06-04): ``ResultadoHoraExtra`` agora documenta explicitamente que
o valor retornado é PARCIAL — não inclui o reflexo de hora extra habitual em
DSR (Lei 605/49 art. 7º + Súmula 172 TST). Ver docstring da classe e da função.

**Regras CLT cobertas:**

  * **Hora extra** — Art. 7º XVI CF/88: mínimo de 50% sobre hora normal.
    Hora normal = ``salario_mensal / (jornada_semanal × 4.5)`` (220h/mês
    pra jornada 44h/semana). Adicionais maiores (100% domingo/feriado)
    via parâmetro ``percentual_adicional``.

  * **Adicional noturno** — CLT art. 73 + §1º: 20% sobre hora normal das
    22h às 5h. A hora noturna urbana tem duração ficta de 52min30s (= 7/8
    de hora real). Isso significa que, por exemplo, 7 horas reais noturnas
    equivalem a 8 horas noturnas-reduzidas. O adicional de 20% é calculado
    sobre essas horas-noturnas-reduzidas, refletindo o benefício legal.
    Base legal: CLT art. 73 caput (adicional 20%) + §1º (hora noturna
    urbana = 52min30s). Súmula TST 65 (adicional incide sobre hora-noturna
    reduzida, não sobre a hora real).

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

ALGORITMO_VERSAO: Final = "hora_extra.v2"

_ZERO = Decimal("0")
_DIAS_MES_REGRA_GERAL = Decimal("30")
# Súmula 431 TST — base de cálculo trabalhista usa fator 5 (semanas/mês):
# 44h × 5 = 220h/mês; 40h × 5 = 200h/mês; etc.
_SEMANAS_MES = Decimal("5")
_QUANTIZE = Decimal("0.01")
# CLT art. 73 §1º — hora noturna urbana = 52min30s (52,5min).
# Fator de redução: 52,5/60 = 7/8. Para converter horas reais em
# horas-noturnas-reduzidas (para fins do adicional): dividir por (52,5/60),
# equivalente a multiplicar por 60/52,5 = 8/7.
# Exemplo: 7 horas reais noturnas = 7 × (60/52,5) = 8 horas-noturnas-reduzidas.
_FATOR_HORA_NOTURNA = Decimal("60") / Decimal("52.5")  # ≈ 1,142857...


@dataclass(frozen=True, slots=True)
class ResultadoHoraExtra:
    """Valor + memória de cálculo (auditável).

    **ATENÇÃO — valor PARCIAL (m5 FA8):**
    O campo ``valor`` representa apenas o adicional ou a hora extra apurada
    para o período, SEM incluir o reflexo sobre o DSR (Descanso Semanal
    Remunerado). Horas extras habituais geram reflexo no DSR conforme Lei
    605/49 art. 7º e Súmula 172 TST. O cálculo do reflexo de DSR exige o
    número de domingos/feriados do mês e habitualidade das HEs — escopo de
    sprint dedicada. O consumidor NÃO deve tratar este valor como verba
    final sem calcular separadamente o reflexo em DSR quando aplicável.

    Para o adicional noturno: ``horas_calculadas`` representa as horas
    noturnas reais (input); ``horas_noturnas_reduzidas`` representa as
    horas convertidas para horas-noturnas-reduzidas (CLT art. 73 §1º), que
    é a base efetiva do cálculo do adicional. Para hora extra comum,
    ``horas_noturnas_reduzidas`` é ``None``.
    """

    valor: Decimal
    salario_hora_normal: Decimal
    horas_calculadas: Decimal
    percentual_adicional: Decimal
    # Preenchido apenas para adicional noturno (m4 FA8).
    # horas_noturnas × _FATOR_HORA_NOTURNA (CLT art. 73 §1º).
    horas_noturnas_reduzidas: Decimal | None = None
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
    """Valor do adicional noturno (CLT art. 73 + §1º — 20% sobre hora normal).

    **Hora noturna reduzida (m4 FA8):** CLT art. 73 §1º estabelece que a
    hora noturna urbana tem duração ficta de 52min30s (7/8 de hora real).
    Isso significa que o empregado que trabalha, por exemplo, 7 horas reais
    entre 22h e 5h, recebe o adicional como se tivesse trabalhado
    ``7 × (60 / 52,5) = 8`` horas noturnas-reduzidas.

    Fórmula:
      ``horas_noturnas_reduzidas = horas_noturnas × (60 / 52,5)``
      ``adicional = hora_normal × percentual × horas_noturnas_reduzidas``

    Algumas categorias têm percentual maior via CCT (até 35-50%) — admin
    informa explicitamente. Função pura — retorna **só o adicional**
    (a diferença entre hora noturna e hora diurna); o salário base já vem
    na folha mensal.

    **ATENÇÃO — valor PARCIAL:** não inclui reflexo de DSR (Lei 605/49
    art. 7º + Súmula 172 TST). Ver docstring de ``ResultadoHoraExtra``.

    Args:
        salario_mensal: salário mensal base (> 0).
        jornada_semanal_horas: jornada contratual em [12, 44].
        horas_noturnas: horas *reais* trabalhadas entre 22h–5h (> 0).
        percentual: adicional noturno (default 20%; CCT pode aumentar).

    Returns:
        ResultadoHoraExtra com ``horas_noturnas_reduzidas`` preenchido.
    """
    if horas_noturnas <= _ZERO:
        raise ValueError(
            f"horas_noturnas deve ser > 0, recebeu {horas_noturnas}"
        )
    if percentual <= _ZERO or percentual > Decimal("1.0"):
        raise ValueError(f"percentual fora de (0, 1.0]: {percentual}")
    hora_normal = calcular_salario_hora(salario_mensal, jornada_semanal_horas)
    # Converter horas reais → horas-noturnas-reduzidas (CLT art. 73 §1º).
    horas_reduzidas = (horas_noturnas * _FATOR_HORA_NOTURNA).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_EVEN
    )
    valor = (hora_normal * percentual * horas_reduzidas).quantize(
        _QUANTIZE, rounding=ROUND_HALF_EVEN
    )
    return ResultadoHoraExtra(
        valor=valor,
        salario_hora_normal=hora_normal,
        horas_calculadas=horas_noturnas,
        percentual_adicional=percentual,
        horas_noturnas_reduzidas=horas_reduzidas,
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
