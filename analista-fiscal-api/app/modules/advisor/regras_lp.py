"""Regras determinísticas de Advisor específicas para Lucro Presumido (Sprint 20 PR3).

Camada 1 (determinística). Funções puras, zero I/O.

Regras cobertas:

  1. ``darf_lp_vencida``   — DARF LP em atraso (não paga após o vencimento).
                            Fonte: Lei 9.430/1996 art. 5º + art. 6º.
  2. ``irpj_adicional``    — Adicional de 10% do IRPJ ativado. Sugere revisar
                            distribuição de lucros para reduzir base na próxima
                            apuração.
                            Fonte: Lei 9.249/1995 art. 3º §1º.
  3. ``distribuicao_isenta``— Limite isento de distribuição ainda disponível
                            (> R$ 5.000). Nudge para o sócio retirar lucros
                            isentos antes do encerramento do exercício.
                            Fonte: RIR/2018 art. 238 + Lei 9.249/1995 art. 10.
  4. ``limite_receita_lp`` — Receita dos últimos 12 meses acima de 90 % do
                            teto anual do LP (R$ 78 M). Sinal de alerta para
                            planejamento de mudança de regime.
                            Fonte: RIR/2018 art. 587.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ALGORITMO_VERSAO = "advisor.regras_lp.v1"

_TETO_RECEITA_ANUAL_LP = Decimal("78_000_000.00")   # RIR/2018 art. 587
_LIMITE_ALERTA_TETO = Decimal("0.90")                # 90% do teto → alerta
_LIMIAR_DISTRIBUICAO = Decimal("5_000.00")           # R$ 5k → sugestão relevante


# ── DTOs de entrada (imutáveis, zero ORM) ────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DarfLpInfo:
    """Snapshot de uma guia de pagamento LP para avaliação de regras."""

    codigo_receita: str   # "2089" | "2372" | "8109" | "2172"
    denominacao: str
    data_vencimento: date
    status: str           # 'a_pagar' | 'pago' | 'cancelado'
    valor: Decimal
    periodo_apuracao: str  # ex: "2026-T1" ou "2026-01"


# ── Tipo unificado de saída ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SugestaoLp:
    """Sugestão LP — mesmo contrato de ``SugestaoCalculada`` do advisor SN."""

    codigo: str
    titulo: str
    descricao: str
    severidade: str             # 'informativa' | 'media' | 'alta'
    economia_anual_estimada: Decimal | None
    fonte_norma: str
    detalhes: dict[str, str] = field(default_factory=dict)
    algoritmo_versao: str = ALGORITMO_VERSAO


# ── Regra 1: DARF LP vencida ─────────────────────────────────────────────────


def checar_darf_lp_vencidas(
    guias: list[DarfLpInfo],
    hoje: date,
) -> list[SugestaoLp]:
    """Retorna uma sugestão consolidada por DARF vencida não paga.

    Considera vencida qualquer guia com ``status='a_pagar'`` e
    ``data_vencimento < hoje``. Cada DARF vencida vira uma entrada separada
    (IRPJ, CSLL, PIS, Cofins têm prazos e consequências distintos).
    """
    vencidas = [
        g for g in guias
        if g.status == "a_pagar" and g.data_vencimento < hoje
    ]
    if not vencidas:
        return []

    sugestoes: list[SugestaoLp] = []
    for g in sorted(vencidas, key=lambda x: x.data_vencimento):
        dias_atraso = (hoje - g.data_vencimento).days
        sugestoes.append(
            SugestaoLp(
                codigo=f"darf_lp_vencida_{g.codigo_receita}",
                titulo=f"DARF {g.denominacao} em atraso ({dias_atraso} dias)",
                descricao=(
                    f"A guia de {g.denominacao} referente a {g.periodo_apuracao} "
                    f"(R$ {g.valor:,.2f}) venceu em "
                    f"{g.data_vencimento.strftime('%d/%m/%Y')} e ainda não foi paga. "
                    f"Juros de mora (taxa SELIC) + multa de 0,33%/dia (máx. 20%) "
                    f"incidem sobre o valor original. "
                    f"Pague o mais rápido possível para evitar inscrição em "
                    f"dívida ativa e irregularidade de CND."
                ),
                severidade="alta",
                economia_anual_estimada=None,
                fonte_norma="Lei 9.430/1996 art. 5º e 6º; Decreto 4.524/2002",
                detalhes={
                    "codigo_receita": g.codigo_receita,
                    "vencimento": g.data_vencimento.isoformat(),
                    "dias_atraso": str(dias_atraso),
                    "valor_original": str(g.valor),
                },
            )
        )
    return sugestoes


# ── Regra 2: Adicional de 10% do IRPJ ────────────────────────────────────────


def checar_irpj_adicional(
    irpj_adicional: Decimal,
    base_total: Decimal,
    limite_adicional: Decimal,
    trimestre: int,
    ano: int,
) -> SugestaoLp | None:
    """Sugere revisão da distribuição de lucros quando o adicional de 10% é ativado.

    Retorna ``None`` quando ``irpj_adicional == 0``.
    """
    if irpj_adicional <= Decimal("0"):
        return None

    excedente = (base_total - limite_adicional).quantize(Decimal("0.01"))
    economia_potencial = irpj_adicional  # o adicional economizado se evitar o excedente

    return SugestaoLp(
        codigo="irpj_adicional_ativado",
        titulo=f"Adicional de 10% do IRPJ ativado — T{trimestre}/{ano}",
        descricao=(
            f"A base de cálculo do IRPJ (R$ {base_total:,.2f}) superou o limite "
            f"de R$ {limite_adicional:,.2f}, ativando o adicional de 10% sobre "
            f"R$ {excedente:,.2f} — custo extra de R$ {irpj_adicional:,.2f}. "
            f"Avalie a antecipação de distribuição de lucros isentos (art. 10 "
            f"Lei 9.249/1995) antes do encerramento do próximo trimestre, reduzindo "
            f"a base presumida através de uma estrutura de receita mais adequada."
        ),
        severidade="media",
        economia_anual_estimada=economia_potencial * 4,  # proxy anual (4 trimestres)
        fonte_norma="Lei 9.249/1995 art. 3º §1º; RIR/2018 art. 625",
        detalhes={
            "irpj_adicional": str(irpj_adicional),
            "base_total": str(base_total),
            "limite_adicional": str(limite_adicional),
            "excedente": str(excedente),
            "trimestre": f"T{trimestre}/{ano}",
        },
    )


# ── Regra 3: Distribuição isenta disponível ───────────────────────────────────


def checar_distribuicao_isenta_potencial(
    limite_isento: Decimal,
    total_distribuido: Decimal,
    *,
    limiar_relevante: Decimal = _LIMIAR_DISTRIBUICAO,
) -> SugestaoLp | None:
    """Sugere distribuição de lucros isentos quando há margem relevante disponível.

    Retorna ``None`` quando:
      * ``limite_isento <= 0`` (empresa não apurou lucro presumido suficiente).
      * Margem disponível (limite − distribuído) é menor que ``limiar_relevante``.
    """
    if limite_isento <= Decimal("0"):
        return None

    disponivel = (limite_isento - total_distribuido).quantize(Decimal("0.01"))
    if disponivel < limiar_relevante:
        return None

    return SugestaoLp(
        codigo="distribuicao_isenta_disponivel",
        titulo=f"Distribua R$ {disponivel:,.2f} de lucros isentos de IR",
        descricao=(
            f"Com base no lucro presumido apurado, o sócio pode retirar até "
            f"R$ {disponivel:,.2f} adicionais com isenção total de IR na fonte "
            f"(art. 10 Lei 9.249/1995 + art. 238 RIR/2018). "
            f"Já foram distribuídos R$ {total_distribuido:,.2f} de um limite de "
            f"R$ {limite_isento:,.2f}. Consulte seu contador para formalizar "
            f"o ato de distribuição antes do encerramento do exercício."
        ),
        severidade="informativa",
        economia_anual_estimada=None,
        fonte_norma="Lei 9.249/1995 art. 10; RIR/2018 art. 238",
        detalhes={
            "limite_isento": str(limite_isento),
            "total_distribuido": str(total_distribuido),
            "disponivel": str(disponivel),
        },
    )


# ── Regra 4: Alerta de teto de receita LP ────────────────────────────────────


def checar_limite_receita_lp(
    receita_ultimos_12m: Decimal,
    *,
    teto: Decimal = _TETO_RECEITA_ANUAL_LP,
    limiar_percentual: Decimal = _LIMITE_ALERTA_TETO,
) -> SugestaoLp | None:
    """Alerta quando receita se aproxima do teto anual do Lucro Presumido (R$ 78 M).

    Retorna ``None`` quando receita < 90% do teto.
    """
    limiar = (teto * limiar_percentual).quantize(Decimal("0.01"))
    if receita_ultimos_12m < limiar:
        return None

    percentual_uso = (receita_ultimos_12m / teto * 100).quantize(Decimal("0.1"))
    margem = (teto - receita_ultimos_12m).quantize(Decimal("0.01"))

    return SugestaoLp(
        codigo="limite_receita_lp_proximo",
        titulo=f"Receita em {percentual_uso}% do teto do Lucro Presumido",
        descricao=(
            f"Nos últimos 12 meses a receita bruta foi de R$ {receita_ultimos_12m:,.2f}, "
            f"equivalente a {percentual_uso}% do limite anual de R$ {teto:,.2f} do "
            f"Lucro Presumido. Restam apenas R$ {margem:,.2f}. "
            f"Ao ultrapassar o teto, a empresa fica obrigada a optar pelo "
            f"Lucro Real a partir do mês seguinte (RIR/2018 art. 587). "
            f"Planeje a transição de regime com antecedência."
        ),
        severidade="alta" if percentual_uso >= Decimal("95") else "media",
        economia_anual_estimada=None,
        fonte_norma="RIR/2018 art. 587; Lei 9.718/1998 art. 14",
        detalhes={
            "receita_12m": str(receita_ultimos_12m),
            "teto": str(teto),
            "percentual_uso": str(percentual_uso),
            "margem_restante": str(margem),
        },
    )
