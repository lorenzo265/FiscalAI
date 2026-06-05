"""Algoritmo puro de provisão trabalhista mensal.

Decimal-safe. Determinístico. Zero I/O.

Fundamento legal:
  * Férias: CF art. 7º XVII (1/3 constitucional) + CLT art. 129
  * 13º:     CF art. 7º VIII + Lei 4.090/1962
  * INSS patronal: Lei 8.212/1991 art. 22 I (20% CPP sobre folha)
              + Lei 8.212/1991 art. 22 II (RAT/SAT 1–3% × FAP)
              + Terceiros/Sistema S (~5,8% típico)
  * FGTS:    Lei 8.036/1990 art. 15 (8%)
  * Simples Nacional/MEI Anexos I–III,V dispensam CPP patronal sobre folha
    (LC 123/2006 art. 13): a contribuição está dentro do DAS.
    Anexo IV: CPP fora do DAS (LC 123/2006 art. 13 §1º VI).

Regras:
  ferias_base = folha_mes / 12
  ferias_total = ferias_base × (1 + 1/3) = ferias_base + 1/3 constitucional
  13_base = folha_mes / 12

  inss_ferias = aliquota_inss_patronal × ferias_total
  inss_13     = aliquota_inss_patronal × 13_base
  fgts_ferias = 0,08 × ferias_total
  fgts_13     = 0,08 × 13_base

  aliquota_inss_patronal (regime-aware, fornecida pelo chamador):
    - SN Anexos I/II/III/V e MEI: 0% (CPP dentro do DAS — dupla contagem).
    - SN Anexo IV, Lucro Presumido, Lucro Real: 20% + RAT×FAP + Terceiros.
    - Default do parâmetro: 20% (conservador / backward-compat).
      RAT e Terceiros: default 0% até seed definitivo por CNAE/grau de risco
      (ver docs/pendencias/rat-fap-terceiros-seed.md).

Quantização: 2 casas, ROUND_HALF_EVEN.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

ALGORITMO_VERSAO = "prov-2026.08"

_CENTAVO = Decimal("0.01")
_UM_DOZE = Decimal("1") / Decimal("12")
_UM_TERCO = Decimal("1") / Decimal("3")

# Alíquota CPP base (Lei 8.212/1991 art. 22 I) — não mais usada internamente
# como hardcode; exposta como constante pública para o service e para testes
# de backward-compat.
ALIQ_CPP_BASE = Decimal("0.20")

_ALIQ_FGTS = Decimal("0.080000")

# Regimes onde a CPP patronal NÃO se aplica separada (está dentro do DAS).
# SN Anexo IV está FORA — CPP é recolhida separada (LC 123/2006 art. 13 §1º VI);
# a distinção de Anexo IV é feita em ``aliquota_patronal_regime``, não aqui.
_REGIMES_SEM_INSS_PATRONAL = frozenset({"mei", "simples_nacional"})

# Alíquota efetiva para provisão de férias: 1/12 × 4/3 = 4/36 ≈ 0.111111
# Garante que base_calculo (folha_mes) × aliquota == valor_provisao (férias + 1/3)
# com erro ≤ R$0,01 — reconciliação de auditoria preservada.
_ALIQ_FERIAS_EFETIVA = (Decimal("4") / Decimal("36")).quantize(
    Decimal("0.000001"), rounding=ROUND_HALF_EVEN
)


@dataclass(frozen=True, slots=True)
class LinhaProvisao:
    """Uma linha persistida em ``provisao_mensal``."""

    tipo: str
    base_calculo: Decimal
    aliquota: Decimal
    valor_provisao: Decimal


@dataclass(frozen=True, slots=True)
class ResultadoProvisoes:
    """Resultado consolidado — sempre devolve as 6 linhas (INSS/FGTS = 0 se não se aplica)."""

    ferias: LinhaProvisao
    decimo_terceiro: LinhaProvisao
    inss_ferias: LinhaProvisao
    inss_13: LinhaProvisao
    fgts_ferias: LinhaProvisao
    fgts_13: LinhaProvisao
    algoritmo_versao: str = ALGORITMO_VERSAO

    def as_lista(self) -> tuple[LinhaProvisao, ...]:
        return (
            self.ferias,
            self.decimo_terceiro,
            self.inss_ferias,
            self.inss_13,
            self.fgts_ferias,
            self.fgts_13,
        )


def inss_patronal_aplicavel(regime: str) -> bool:
    """SN/MEI (Anexos I–III,V) não recolhem CPP patronal separada (LC 123/2006 art. 13).

    Atenção: SN Anexo IV recolhe CPP separada — mas como o regime no banco
    é apenas ``simples_nacional`` (sem distinção de anexo), esta função retorna
    False para todo SN. O service usa ``aliquota_patronal_regime`` (que recebe
    o anexo) para distinguir o Anexo IV corretamente.
    """
    return regime.lower() not in _REGIMES_SEM_INSS_PATRONAL


def aliquota_patronal_regime(
    regime: str,
    anexo_simples: str | None = None,
    rat_sat: Decimal = Decimal("0"),
    aliquota_terceiros: Decimal = Decimal("0"),
) -> Decimal:
    """Retorna a alíquota previdenciária patronal total para provisão de férias/13º.

    Regime-aware — consultar antes de chamar ``calcular_provisoes``.

    Regra:
      - SN Anexos I, II, III, V → 0% (CPP dentro do DAS; dupla contagem se provisionar).
      - MEI → 0% (idem).
      - SN Anexo IV → 20% + RAT×FAP + Terceiros (CPP fora do DAS).
      - Lucro Presumido / Lucro Real → 20% + RAT×FAP + Terceiros.
      - ``simples_nacional`` sem anexo informado → 0% (assumir desonerado; conservador
        para evitar dupla contagem; se for Anexo IV o contador deve informar o anexo).

    Args:
        regime: ``empresa.regime_tributario`` (``mei``, ``simples_nacional``,
            ``lucro_presumido``, ``lucro_real``).
        anexo_simples: ``empresa.anexo_simples`` (``I``–``V``) — só relevante
            quando ``regime == "simples_nacional"``.
        rat_sat: alíquota RAT/SAT do art. 22 II (0,01–0,03 × FAP). Default 0%
            até seed definitivo por CNAE/grau de risco.
            Ver docs/pendencias/rat-fap-terceiros-seed.md.
        aliquota_terceiros: alíquota Sistema S / Terceiros (~5,8% típico).
            Default 0% até seed definitivo.

    Returns:
        Decimal com a alíquota total (ex.: 0,278 para 20%+2%+5,8%).
    """
    r = regime.lower()
    if r == "mei":
        return Decimal("0")
    if r == "simples_nacional":
        anexo = (anexo_simples or "").strip().upper()
        if anexo == "IV":
            # SN Anexo IV: CPP fora do DAS — recolhe 20% + RAT + Terceiros.
            return ALIQ_CPP_BASE + rat_sat + aliquota_terceiros
        # Anexos I, II, III, V (e SN sem anexo informado): CPP dentro do DAS.
        return Decimal("0")
    # Lucro Presumido / Lucro Real: CPP sempre fora do DAS.
    return ALIQ_CPP_BASE + rat_sat + aliquota_terceiros


def calcular_provisoes(
    folha_mes: Decimal,
    regime: str,
    aliquota_inss_patronal: Decimal = ALIQ_CPP_BASE,
) -> ResultadoProvisoes:
    """Calcula as 6 provisões mensais a partir da folha agregada da empresa.

    Args:
        folha_mes: total bruto da folha do mês (Decimal, BRL).
        regime: ``empresa.regime_tributario`` — afeta INSS patronal.
            Mantido para backward-compat e para a lógica FGTS (que nunca é
            dispensado). **Não mais** determina a alíquota previdenciária
            sozinho — use ``aliquota_inss_patronal`` para isso.
        aliquota_inss_patronal: alíquota previdenciária patronal total
            (CPP + RAT×FAP + Terceiros), já regime-aware. Fornecida pelo
            service via ``aliquota_patronal_regime()``. Default: ``ALIQ_CPP_BASE``
            (0,20) — backward-compat; representa o piso conservador (só CPP,
            sem RAT/Terceiros) até o seed definitivo.

            Valores típicos:
            * SN Anexos I/II/III/V, MEI: 0 (CPP no DAS).
            * SN Anexo IV, LP, LR sem RAT/Terceiros: 0,20 (piso).
            * LP, LR com RAT 2% + Terceiros 5,8%: 0,278.

    Returns:
        ResultadoProvisoes com as 6 linhas. Linhas de INSS ficam com
        valor_provisao=0 quando aliquota_inss_patronal == 0.
    """
    if folha_mes < Decimal("0"):
        raise ValueError("folha_mes não pode ser negativa")

    ferias_base = _quantizar(folha_mes * _UM_DOZE)
    um_terco_constitucional = _quantizar(ferias_base * _UM_TERCO)
    ferias_total = ferias_base + um_terco_constitucional

    base_13 = _quantizar(folha_mes * _UM_DOZE)

    aliq_inss = aliquota_inss_patronal
    inss_ferias_val = _quantizar(ferias_total * aliq_inss)
    inss_13_val = _quantizar(base_13 * aliq_inss)

    fgts_ferias_val = _quantizar(ferias_total * _ALIQ_FGTS)
    fgts_13_val = _quantizar(base_13 * _ALIQ_FGTS)

    return ResultadoProvisoes(
        ferias=LinhaProvisao(
            tipo="ferias",
            # base = folha_mes; aliquota = 1/12 × 4/3 ≈ 0.111111 →
            # base × aliquota ≈ ferias_total (reconciliação ≤ R$0,01).
            # Antes: aliquota=1/12 → base × 0.083333 ≠ ferias_total (off by 1/3).
            base_calculo=folha_mes,
            aliquota=_ALIQ_FERIAS_EFETIVA,
            valor_provisao=ferias_total,
        ),
        decimo_terceiro=LinhaProvisao(
            tipo="13_salario",
            base_calculo=folha_mes,
            aliquota=_UM_DOZE_PCT_ARREDONDADA,
            valor_provisao=base_13,
        ),
        inss_ferias=LinhaProvisao(
            tipo="inss_ferias",
            base_calculo=ferias_total,
            aliquota=aliq_inss,
            valor_provisao=inss_ferias_val,
        ),
        inss_13=LinhaProvisao(
            tipo="inss_13",
            base_calculo=base_13,
            aliquota=aliq_inss,
            valor_provisao=inss_13_val,
        ),
        fgts_ferias=LinhaProvisao(
            tipo="fgts_ferias",
            base_calculo=ferias_total,
            aliquota=_ALIQ_FGTS,
            valor_provisao=fgts_ferias_val,
        ),
        fgts_13=LinhaProvisao(
            tipo="fgts_13",
            base_calculo=base_13,
            aliquota=_ALIQ_FGTS,
            valor_provisao=fgts_13_val,
        ),
    )


# Alíquota "1/12" persistida em provisao_mensal.aliquota a 6 casas decimais
# (coluna NUMERIC(8,6) desde a migration 0030). Usado apenas para a linha de
# 13_salario: auditor que multiplicar base_calculo × 0.083333 ≈ valor_provisao
# com erro ≤ R$ 0,01.
# Para a linha de férias, use _ALIQ_FERIAS_EFETIVA (≈ 0.111111 = 1/12 × 4/3),
# que reconcilia corretamente (inclui o terço constitucional).
_UM_DOZE_PCT_ARREDONDADA = (Decimal("1") / Decimal("12")).quantize(
    Decimal("0.000001"), rounding=ROUND_HALF_EVEN
)


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
