"""Cálculo de rescisão trabalhista — 5 modalidades CLT.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * CLT art. 477          — direitos da rescisão.
  * CLT art. 482          — justa causa do empregado.
  * CLT art. 484-A        — distrato por mútuo acordo (Lei 13.467/2017).
  * CLT art. 487          — aviso prévio.
  * CLT art. 479          — término de contrato a prazo determinado.
  * Lei 12.506/2011 art. 1º — aviso proporcional ao tempo de serviço:
    30 dias + 3 dias por ano completo de serviço, limitado a 90 dias.
  * Lei 8.036/1990 art. 18 §1º + §2º — multa rescisória FGTS (40% sem
    justa causa); art. 484-A §1º II — 20% no mútuo acordo.
  * STJ Súmula 89          — aviso prévio indenizado: NÃO incide INSS.
  * STJ Súmula 207         — férias indenizadas + 1/3: NÃO incidem INSS.
  * Lei 7.713/1988 art. 6º V — férias indenizadas + 1/3 + abono pec.: ISENTOS IRRF.
  * IN RFB 1.500/2014 art. 7º — aviso indenizado: ISENTO IRRF.
  * Lei 8.134/1990 art. 16 — IRRF do 13º: cálculo SEPARADO (exclusivo na fonte).
  * IN RFB 971/2009 art. 58 — FGTS incide sobre aviso indenizado.

Modalidades suportadas:

  ┌─────────────────────────┬──────────┬───────┬───────┬───────────┬─────────┐
  │ Tipo                    │ Saldo    │ Aviso │ 13º P │ Férias P  │ Multa   │
  ├─────────────────────────┼──────────┼───────┼───────┼───────────┼─────────┤
  │ sem_justa_causa         │ ✓        │ 100%  │ ✓     │ ✓         │ 40%     │
  │ com_justa_causa         │ ✓        │ —     │ —     │ —         │ —       │
  │ pedido_demissao         │ ✓        │ —     │ ✓     │ ✓         │ —       │
  │ mutuo_acordo (484-A)    │ ✓        │ 50%   │ ✓     │ ✓         │ 20%     │
  │ termino_determinado     │ ✓        │ —     │ ✓     │ ✓         │ —       │
  └─────────────────────────┴──────────┴───────┴───────┴───────────┴─────────┘

  Férias vencidas + 1/3 são SEMPRE pagas se houver período aquisitivo vencido,
  independentemente do tipo.

Tributação por bloco:
  * Bloco salarial (saldo de salário) → INSS escalonado + IRRF mensal.
  * Bloco 13º proporcional             → INSS escalonado + IRRF separado.
  * Aviso indenizado                   → ISENTO INSS/IRRF, incide FGTS 8%.
  * Férias venc + prop + 1/3 indeniz.  → ISENTAS (INSS/IRRF/FGTS).

FGTS rescisório (empregador):
  fgts_rescisao = 0,08 × (saldo + 13º + aviso_indenizado)
  multa_fgts    = pct_tipo × (saldo_fgts_acumulado_antes + fgts_rescisao)

Quantização: ``ROUND_HALF_EVEN`` 2 casas em cada componente.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from enum import StrEnum

from app.modules.pessoal.calcula_inss import (
    FaixaInss,
    ResultadoInssEmpregado,
    calcular_inss_empregado,
)
from app.modules.pessoal.calcula_irrf import (
    FaixaIrrf,
    ResultadoIrrf,
    calcular_irrf_mensal,
)

getcontext().prec = 28

ALGORITMO_VERSAO = "rescisao.v1"

_CENTAVO = Decimal("0.01")
_TRINTA = Decimal("30")
_DOZE = Decimal("12")
_TRES = Decimal("3")
_OITO_PCT = Decimal("0.0800")
_ZERO = Decimal("0")
_AVISO_BASE_DIAS = 30
_AVISO_MAX_DIAS = 90
_AVISO_DIAS_POR_ANO = 3


class RescisaoTipo(StrEnum):
    SEM_JUSTA_CAUSA = "sem_justa_causa"
    COM_JUSTA_CAUSA = "com_justa_causa"
    PEDIDO_DEMISSAO = "pedido_demissao"
    MUTUO_ACORDO = "mutuo_acordo"
    TERMINO_DETERMINADO = "termino_determinado"


@dataclass(frozen=True, slots=True)
class _Incidencia:
    paga_aviso_pct: Decimal
    paga_13o_proporcional: bool
    paga_ferias_proporcionais: bool
    multa_fgts_pct: Decimal


_INCIDENCIAS: dict[RescisaoTipo, _Incidencia] = {
    RescisaoTipo.SEM_JUSTA_CAUSA: _Incidencia(
        Decimal("1"), True, True, Decimal("0.40"),
    ),
    RescisaoTipo.COM_JUSTA_CAUSA: _Incidencia(
        Decimal("0"), False, False, Decimal("0"),
    ),
    RescisaoTipo.PEDIDO_DEMISSAO: _Incidencia(
        Decimal("0"), True, True, Decimal("0"),
    ),
    RescisaoTipo.MUTUO_ACORDO: _Incidencia(
        Decimal("0.5"), True, True, Decimal("0.20"),
    ),
    RescisaoTipo.TERMINO_DETERMINADO: _Incidencia(
        Decimal("0"), True, True, Decimal("0"),
    ),
}


@dataclass(frozen=True, slots=True)
class VerbasRescisao:
    """Decomposição das verbas pagas (cada bloco em valor bruto)."""

    saldo_salario: Decimal
    aviso_indenizado: Decimal
    decimo_terceiro_proporcional: Decimal
    ferias_vencidas: Decimal  # já inclui 1/3
    ferias_proporcionais: Decimal  # já inclui 1/3
    valor_bruto_total: Decimal


@dataclass(frozen=True, slots=True)
class ResultadoRescisao:
    """Snapshot do cálculo persistido em ``evento_folha`` (tipo='rescisao')."""

    tipo: RescisaoTipo
    salario_base: Decimal
    anos_completos_servico: int
    aviso_dias_devidos: int  # 30 + 3×anos, máx 90
    aviso_dias_indenizados: int
    verbas: VerbasRescisao
    inss_saldo: ResultadoInssEmpregado
    irrf_saldo: ResultadoIrrf
    inss_13o: ResultadoInssEmpregado | None  # None se 13º não é pago
    irrf_13o: ResultadoIrrf | None
    fgts_rescisao: Decimal  # 8% sobre saldo+13º+aviso indenizado
    saldo_fgts_acumulado: Decimal  # input ecoado para auditoria
    multa_fgts: Decimal  # pct × (acumulado + fgts_rescisao)
    multa_fgts_pct: Decimal
    valor_liquido_a_pagar: Decimal  # bruto − inss_total − irrf_total
    algoritmo_versao: str = ALGORITMO_VERSAO


def aviso_previo_dias(anos_completos_servico: int) -> int:
    """Calcula dias de aviso prévio devidos pelo empregador.

    Lei 12.506/2011 art. 1º: 30 dias + 3 por ano completo, máx 90.
    """
    if anos_completos_servico < 0:
        raise ValueError(
            f"anos_completos_servico não pode ser negativo: {anos_completos_servico}"
        )
    return min(
        _AVISO_BASE_DIAS + _AVISO_DIAS_POR_ANO * anos_completos_servico,
        _AVISO_MAX_DIAS,
    )


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def calcular_rescisao(
    tipo: RescisaoTipo,
    salario: Decimal,
    anos_completos_servico: int,
    dias_trabalhados_mes_demissao: int,
    avos_13o: int,
    avos_ferias_proporcionais: int,
    ferias_vencidas_dias: int,
    saldo_fgts_acumulado: Decimal,
    faixas_inss: list[FaixaInss],
    faixas_irrf: list[FaixaIrrf],
    dependentes: int,
) -> ResultadoRescisao:
    """Calcula uma rescisão trabalhista completa.

    Args:
        tipo: modalidade (5 opções suportadas).
        salario: salário mensal usado de base.
        anos_completos_servico: para aviso proporcional (Lei 12.506/2011).
        dias_trabalhados_mes_demissao: 0..31 — base do saldo de salário.
        avos_13o: 0..12 — meses trabalhados no ano da rescisão (regra 15d
                  aplicada antes pelo service).
        avos_ferias_proporcionais: 0..12 — meses no período aquisitivo atual.
        ferias_vencidas_dias: 0..30 — dias de férias vencidas pendentes
                              (período aquisitivo já completo e não gozado).
                              Vencidas são SEMPRE pagas, qualquer tipo.
        saldo_fgts_acumulado: saldo do FGTS antes da rescisão — base da multa.
        faixas_inss: 4 faixas vigentes na data da rescisão.
        faixas_irrf: 5 faixas vigentes.
        dependentes: número de dependentes IRRF.

    Returns:
        ResultadoRescisao.

    Raises:
        ValueError: parâmetros inválidos.
    """
    if salario < _ZERO:
        raise ValueError(f"salario não pode ser negativo: {salario}")
    if dias_trabalhados_mes_demissao < 0 or dias_trabalhados_mes_demissao > 31:
        raise ValueError(
            f"dias_trabalhados_mes_demissao deve estar entre 0 e 31 "
            f"(recebido {dias_trabalhados_mes_demissao})"
        )
    if avos_13o < 0 or avos_13o > 12:
        raise ValueError(f"avos_13o deve estar entre 0 e 12 (recebido {avos_13o})")
    if avos_ferias_proporcionais < 0 or avos_ferias_proporcionais > 12:
        raise ValueError(
            f"avos_ferias_proporcionais deve estar entre 0 e 12 "
            f"(recebido {avos_ferias_proporcionais})"
        )
    if ferias_vencidas_dias < 0 or ferias_vencidas_dias > 30:
        raise ValueError(
            f"ferias_vencidas_dias deve estar entre 0 e 30 "
            f"(recebido {ferias_vencidas_dias})"
        )
    if saldo_fgts_acumulado < _ZERO:
        raise ValueError(
            f"saldo_fgts_acumulado não pode ser negativo: {saldo_fgts_acumulado}"
        )

    inc = _INCIDENCIAS[tipo]
    aviso_dias_devidos = aviso_previo_dias(anos_completos_servico)
    aviso_dias_indenizados = int(Decimal(aviso_dias_devidos) * inc.paga_aviso_pct)

    # ── Verbas ──────────────────────────────────────────────────────────
    saldo = _quantizar(salario * Decimal(dias_trabalhados_mes_demissao) / _TRINTA)
    aviso_indenizado = _quantizar(salario * Decimal(aviso_dias_indenizados) / _TRINTA)

    if inc.paga_13o_proporcional and avos_13o > 0:
        bruto_13 = _quantizar(salario * Decimal(avos_13o) / _DOZE)
    else:
        bruto_13 = _ZERO

    if ferias_vencidas_dias > 0:
        remun_venc = salario * Decimal(ferias_vencidas_dias) / _TRINTA
        ferias_venc_total = _quantizar(remun_venc + remun_venc / _TRES)
    else:
        ferias_venc_total = _ZERO

    if inc.paga_ferias_proporcionais and avos_ferias_proporcionais > 0:
        remun_prop = salario * Decimal(avos_ferias_proporcionais) / _DOZE
        ferias_prop_total = _quantizar(remun_prop + remun_prop / _TRES)
    else:
        ferias_prop_total = _ZERO

    bruto_total = (
        saldo + aviso_indenizado + bruto_13 + ferias_venc_total + ferias_prop_total
    )

    # ── Tributação por bloco ────────────────────────────────────────────
    inss_saldo = calcular_inss_empregado(saldo, faixas_inss)
    irrf_saldo = calcular_irrf_mensal(saldo, inss_saldo.inss, dependentes, faixas_irrf)

    if bruto_13 > _ZERO:
        inss_13: ResultadoInssEmpregado | None = calcular_inss_empregado(
            bruto_13, faixas_inss
        )
        assert inss_13 is not None  # narrow for mypy
        irrf_13: ResultadoIrrf | None = calcular_irrf_mensal(
            bruto_13, inss_13.inss, dependentes, faixas_irrf
        )
    else:
        inss_13 = None
        irrf_13 = None

    inss_total = inss_saldo.inss + (inss_13.inss if inss_13 else _ZERO)
    irrf_total = irrf_saldo.irrf + (irrf_13.irrf if irrf_13 else _ZERO)

    # ── FGTS rescisório + multa ─────────────────────────────────────────
    base_fgts = saldo + bruto_13 + aviso_indenizado
    fgts_rescisao = _quantizar(base_fgts * _OITO_PCT)
    multa_base = saldo_fgts_acumulado + fgts_rescisao
    multa_fgts = _quantizar(multa_base * inc.multa_fgts_pct)

    valor_liquido = _quantizar(bruto_total - inss_total - irrf_total)

    return ResultadoRescisao(
        tipo=tipo,
        salario_base=salario,
        anos_completos_servico=anos_completos_servico,
        aviso_dias_devidos=aviso_dias_devidos,
        aviso_dias_indenizados=aviso_dias_indenizados,
        verbas=VerbasRescisao(
            saldo_salario=saldo,
            aviso_indenizado=aviso_indenizado,
            decimo_terceiro_proporcional=bruto_13,
            ferias_vencidas=ferias_venc_total,
            ferias_proporcionais=ferias_prop_total,
            valor_bruto_total=bruto_total,
        ),
        inss_saldo=inss_saldo,
        irrf_saldo=irrf_saldo,
        inss_13o=inss_13,
        irrf_13o=irrf_13,
        fgts_rescisao=fgts_rescisao,
        saldo_fgts_acumulado=saldo_fgts_acumulado,
        multa_fgts=multa_fgts,
        multa_fgts_pct=inc.multa_fgts_pct,
        valor_liquido_a_pagar=valor_liquido,
    )
