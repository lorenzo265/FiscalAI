"""Detecção determinística de anomalias em apurações fiscais (Sprint 15 PR1).

Camada 1 (determinística). Função pura, zero I/O.

**Método:**

  Dado uma série temporal ordenada por competência ``[(competencia, valor)]``
  com o último ponto sendo o "alvo" (a competência mais recente que queremos
  classificar), decide se o valor-alvo é anômalo em relação aos N-1 valores
  históricos.

  * N ≥ 6  → **Z-score** sobre o histórico (desvio padrão amostral). Mais
             sensível, captura sazonalidade ruidosa.
  * 3 ≤ N < 6 → **IQR** (Tukey). Robusto a outliers únicos no histórico,
                ideal para empresas com poucos meses de operação.
  * N < 3   → nada a fazer; caller deve pular ou levantar
              ``HistoricoInsuficienteParaAnomalia`` se for exigida análise.

**Thresholds (decisões #2/#3 do plano da Sprint 15):**

  Z-score:
    * abs(z) >= 3       -> **alta**
    * 2 <= abs(z) < 3   -> **media**
    * 1.5 <= abs(z) < 2 -> **baixa**
    * abs(z) < 1.5      -> sem anomalia (``None``)

  IQR (Tukey):
    * Fora de [Q1 − 3.0×IQR, Q3 + 3.0×IQR]   → **alta**
    * Fora de [Q1 − 1.5×IQR, Q3 + 1.5×IQR]   → **media**
    * Caso contrário                          → sem anomalia

**Edge cases tratados:**

  * Histórico **constante** (desvio = 0): se valor-alvo bate com o histórico,
    sem anomalia; se difere e |delta| > ``_LIMIAR_RUIDO_BRL`` (R$ 100,00),
    emite severidade **alta** sintética (caso "saiu do zero").
  * Histórico **vazio** ou com 1-2 pontos: retorna ``None`` (caller decide).
  * Valor negativo: ``ValueError`` (CHECK constraint do DB exige ≥ 0).
  * Esperado = 0 e observado > 0: ``delta_percentual`` capada em ±999,9999.

Quantização: somatórios com 28 dígitos; z_score arredondado a 3 casas
(``HALF_EVEN``), delta_percentual a 4 casas, valores monetários a 2 casas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from enum import StrEnum

getcontext().prec = 28

ALGORITMO_VERSAO = "advisor.anomalia.v1"

_CENTAVO = Decimal("0.01")
_Z_DISPLAY = Decimal("0.001")
_PCT_DISPLAY = Decimal("0.0001")
_ZERO = Decimal("0")
_LIMIAR_RUIDO_BRL = Decimal("100.00")
_DELTA_CAP = Decimal("999.9999")
_MIN_AMOSTRA_ZSCORE = 6
_MIN_AMOSTRA_IQR = 3

_Z_ALTA = Decimal("3.0")
_Z_MEDIA = Decimal("2.0")
_Z_BAIXA = Decimal("1.5")
_IQR_ALTA = Decimal("3.0")
_IQR_MEDIA = Decimal("1.5")


class TipoTributoAnomalia(StrEnum):
    """Tipos de apuração monitorados — espelha CHECK de ``anomalia_fiscal``."""

    DAS = "das"
    IRPJ = "irpj"
    CSLL = "csll"
    PIS = "pis"
    COFINS = "cofins"
    ISS = "iss"
    ICMS = "icms"


class SeveridadeAnomalia(StrEnum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"


class MetodoDeteccao(StrEnum):
    ZSCORE = "zscore"
    IQR = "iqr"


@dataclass(frozen=True, slots=True)
class PontoApuracao:
    """Uma observação na série temporal."""

    competencia: date
    valor: Decimal


@dataclass(frozen=True, slots=True)
class AnomaliaDetectada:
    """Resultado positivo da detecção — caller persiste em ``anomalia_fiscal``."""

    tipo: TipoTributoAnomalia
    competencia: date  # = ponto-alvo (último da série)
    valor_observado: Decimal  # 2 casas
    valor_esperado: Decimal  # 2 casas (média no zscore, mediana no iqr)
    z_score: Decimal  # 3 casas, sinalizado
    delta_percentual: Decimal  # 4 casas, sinalizado (cap ±999,9999)
    severidade: SeveridadeAnomalia
    metodo: MetodoDeteccao
    amostra_n: int  # tamanho do HISTÓRICO (sem contar o alvo)
    mensagem: str  # pt-BR, citável no digest
    algoritmo_versao: str = ALGORITMO_VERSAO


def detectar_anomalia(
    tipo: TipoTributoAnomalia,
    serie: list[PontoApuracao],
) -> AnomaliaDetectada | None:
    """Avalia o último ponto de ``serie`` contra os anteriores.

    Args:
        tipo: tributo monitorado (das, pis, cofins, ...).
        serie: pontos ordenados por competência ASC. Último ponto é o alvo;
               os demais formam o histórico. Caller garante ordenação.

    Returns:
        ``AnomaliaDetectada`` quando o alvo é anômalo; ``None`` caso contrário
        (histórico insuficiente, dentro da banda esperada, etc.).

    Raises:
        ValueError: série vazia ou contendo valor negativo.
    """
    if not serie:
        raise ValueError("serie não pode ser vazia")
    if any(p.valor < _ZERO for p in serie):
        raise ValueError("valores negativos não são permitidos (CHECK do DB)")

    alvo = serie[-1]
    historico = [p.valor for p in serie[:-1]]
    n_hist = len(historico)

    if n_hist < _MIN_AMOSTRA_IQR:
        return None

    metodo = (
        MetodoDeteccao.ZSCORE
        if n_hist >= _MIN_AMOSTRA_ZSCORE
        else MetodoDeteccao.IQR
    )

    if metodo is MetodoDeteccao.ZSCORE:
        return _detectar_via_zscore(tipo, alvo, historico)
    return _detectar_via_iqr(tipo, alvo, historico)


# ── Z-score ────────────────────────────────────────────────────────────────


def _detectar_via_zscore(
    tipo: TipoTributoAnomalia,
    alvo: PontoApuracao,
    historico: list[Decimal],
) -> AnomaliaDetectada | None:
    n = len(historico)
    media = sum(historico, start=_ZERO) / Decimal(n)

    variancia = sum(
        ((x - media) * (x - media) for x in historico),
        start=_ZERO,
    ) / Decimal(n - 1)
    desvio = variancia.sqrt()

    if desvio == _ZERO:
        return _avaliar_serie_constante(
            tipo=tipo,
            alvo=alvo,
            historico=historico,
            esperado=media,
            metodo=MetodoDeteccao.ZSCORE,
        )

    z_raw = (alvo.valor - media) / desvio
    z_abs = abs(z_raw)

    if z_abs < _Z_BAIXA:
        return None

    if z_abs >= _Z_ALTA:
        severidade = SeveridadeAnomalia.ALTA
    elif z_abs >= _Z_MEDIA:
        severidade = SeveridadeAnomalia.MEDIA
    else:
        severidade = SeveridadeAnomalia.BAIXA

    z_quant = z_raw.quantize(_Z_DISPLAY, rounding=ROUND_HALF_EVEN)
    valor_esperado = media.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
    valor_obs = alvo.valor.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
    delta_pct = _delta_percentual(observado=valor_obs, esperado=valor_esperado)

    return AnomaliaDetectada(
        tipo=tipo,
        competencia=alvo.competencia,
        valor_observado=valor_obs,
        valor_esperado=valor_esperado,
        z_score=z_quant,
        delta_percentual=delta_pct,
        severidade=severidade,
        metodo=MetodoDeteccao.ZSCORE,
        amostra_n=n,
        mensagem=_montar_mensagem(
            tipo=tipo,
            valor_obs=valor_obs,
            valor_esp=valor_esperado,
            delta_pct=delta_pct,
            n=n,
            metodo=MetodoDeteccao.ZSCORE,
            severidade=severidade,
        ),
    )


# ── IQR (Tukey) ─────────────────────────────────────────────────────────────


def _detectar_via_iqr(
    tipo: TipoTributoAnomalia,
    alvo: PontoApuracao,
    historico: list[Decimal],
) -> AnomaliaDetectada | None:
    n = len(historico)
    ordenado = sorted(historico)
    q1 = _quantil(ordenado, Decimal("0.25"))
    mediana = _quantil(ordenado, Decimal("0.5"))
    q3 = _quantil(ordenado, Decimal("0.75"))
    iqr = q3 - q1

    if iqr == _ZERO:
        return _avaliar_serie_constante(
            tipo=tipo,
            alvo=alvo,
            historico=historico,
            esperado=mediana,
            metodo=MetodoDeteccao.IQR,
        )

    limite_baixo_media = q1 - _IQR_MEDIA * iqr
    limite_alto_media = q3 + _IQR_MEDIA * iqr
    limite_baixo_alta = q1 - _IQR_ALTA * iqr
    limite_alto_alta = q3 + _IQR_ALTA * iqr

    if alvo.valor < limite_baixo_alta or alvo.valor > limite_alto_alta:
        severidade = SeveridadeAnomalia.ALTA
    elif alvo.valor < limite_baixo_media or alvo.valor > limite_alto_media:
        severidade = SeveridadeAnomalia.MEDIA
    else:
        return None

    valor_obs = alvo.valor.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
    valor_esperado = mediana.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
    delta_pct = _delta_percentual(observado=valor_obs, esperado=valor_esperado)
    # z_score "equivalente" no método IQR: distância sobre IQR (escala robusta).
    z_proxy = ((alvo.valor - mediana) / iqr).quantize(
        _Z_DISPLAY, rounding=ROUND_HALF_EVEN
    )

    return AnomaliaDetectada(
        tipo=tipo,
        competencia=alvo.competencia,
        valor_observado=valor_obs,
        valor_esperado=valor_esperado,
        z_score=z_proxy,
        delta_percentual=delta_pct,
        severidade=severidade,
        metodo=MetodoDeteccao.IQR,
        amostra_n=n,
        mensagem=_montar_mensagem(
            tipo=tipo,
            valor_obs=valor_obs,
            valor_esp=valor_esperado,
            delta_pct=delta_pct,
            n=n,
            metodo=MetodoDeteccao.IQR,
            severidade=severidade,
        ),
    )


# ── Helpers ─────────────────────────────────────────────────────────────────


def _avaliar_serie_constante(
    *,
    tipo: TipoTributoAnomalia,
    alvo: PontoApuracao,
    historico: list[Decimal],
    esperado: Decimal,
    metodo: MetodoDeteccao,
) -> AnomaliaDetectada | None:
    """Trata histórico com desvio = 0 ou IQR = 0.

    Se o alvo bate com o histórico, sem anomalia. Caso contrário, severidade
    ``alta`` quando |delta| ultrapassa ``_LIMIAR_RUIDO_BRL`` — é o caso típico
    "imposto que era zero e virou R$ 5.000" ou vice-versa.
    """
    delta_abs = abs(alvo.valor - esperado)
    if delta_abs <= _LIMIAR_RUIDO_BRL:
        return None
    valor_obs = alvo.valor.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
    valor_esp = esperado.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
    delta_pct = _delta_percentual(observado=valor_obs, esperado=valor_esp)
    return AnomaliaDetectada(
        tipo=tipo,
        competencia=alvo.competencia,
        valor_observado=valor_obs,
        valor_esperado=valor_esp,
        z_score=_DELTA_CAP if alvo.valor > esperado else -_DELTA_CAP,
        delta_percentual=delta_pct,
        severidade=SeveridadeAnomalia.ALTA,
        metodo=metodo,
        amostra_n=len(historico),
        mensagem=_montar_mensagem(
            tipo=tipo,
            valor_obs=valor_obs,
            valor_esp=valor_esp,
            delta_pct=delta_pct,
            n=len(historico),
            metodo=metodo,
            severidade=SeveridadeAnomalia.ALTA,
        ),
    )


def _delta_percentual(*, observado: Decimal, esperado: Decimal) -> Decimal:
    """Retorna (observado − esperado) / esperado, capada em ±999,9999."""
    if esperado == _ZERO:
        return _DELTA_CAP if observado > _ZERO else _ZERO
    bruto = (observado - esperado) / esperado
    if bruto > _DELTA_CAP:
        return _DELTA_CAP
    if bruto < -_DELTA_CAP:
        return -_DELTA_CAP
    return bruto.quantize(_PCT_DISPLAY, rounding=ROUND_HALF_EVEN)


def _quantil(ordenado: list[Decimal], q: Decimal) -> Decimal:
    """Quantil tipo R-7 (interpolação linear, padrão de numpy/pandas).

    ``ordenado`` deve estar em ordem ascendente. ``q`` ∈ [0, 1].
    """
    n = len(ordenado)
    if n == 1:
        return ordenado[0]
    pos = q * Decimal(n - 1)
    inteiro = int(pos)
    frac = pos - Decimal(inteiro)
    if inteiro >= n - 1:
        return ordenado[-1]
    baixo = ordenado[inteiro]
    alto = ordenado[inteiro + 1]
    return baixo + frac * (alto - baixo)


def _montar_mensagem(
    *,
    tipo: TipoTributoAnomalia,
    valor_obs: Decimal,
    valor_esp: Decimal,
    delta_pct: Decimal,
    n: int,
    metodo: MetodoDeteccao,
    severidade: SeveridadeAnomalia,
) -> str:
    """Mensagem pt-BR citável no digest semanal (Sprint 15 PR3)."""
    direcao = "subiu" if valor_obs > valor_esp else "caiu"
    pct_pp = (abs(delta_pct) * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_EVEN
    )
    metodo_pt = "desvio padrão" if metodo is MetodoDeteccao.ZSCORE else "IQR"
    return (
        f"{tipo.value.upper()} {direcao} {pct_pp}% em relação à média de "
        f"{n} meses (de R$ {valor_esp:,.2f} para R$ {valor_obs:,.2f}). "
        f"Severidade: {severidade.value} ({metodo_pt}, n={n})."
    )
