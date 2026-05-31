"""Validadores §8.6 puros (golden-testable) do painel admin (Sprint 19.5 PR1).

Cada função recebe um schema Pydantic já validado pela borda (tipos OK,
faixa de domínio OK) e aplica regras de **plausibilidade fiscal** que o
Pydantic não consegue expressar:

  * Faixas progressivas — ``limite[n] > limite[n-1]`` em INSS/IRRF/SN.
  * Salário mínimo de referência — primeira faixa INSS/IRRF cobre 1 SM.
  * Plausibilidade — IRPJ presumido 8–32%, CSLL 9%, INSS 7,5–14%, IRRF até
    27,5%, etc. Defesa contra typo do admin postando "0.275" como "0.0275".
  * UFs válidas — conjunto fechado das 27 UFs brasileiras.

Toda falha levanta ``VigenciaTributariaInvalida`` com mensagem específica
(campo + valor inválido + porque). O caller traduz para 422.

A regra "``valid_from > max(valid_from existente)``" requer DB — fica no
service, **não aqui**. Estes validadores são puros (Decimal-only, sem I/O).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from app.modules.tabelas_admin.salario_minimo import salario_minimo_oficial
from app.modules.tabelas_admin.schemas import (
    VigenciaCbsIbsIn,
    VigenciaFgtsIn,
    VigenciaIcmsUfIn,
    VigenciaInssIn,
    VigenciaIrrfIn,
    VigenciaPresuncaoLpIn,
    VigenciaSimplesNacionalIn,
)
from app.shared.exceptions import VigenciaTributariaInvalida


# ── Constantes de plausibilidade ────────────────────────────────────────────


# Faixas históricas das alíquotas — usadas como "esperado" para detectar
# typo do admin (ex.: postar "0.275" como "0.0275"). Não são limites legais
# absolutos — são heurísticas com folga generosa.

_INSS_ALIQUOTA_MIN: Final[Decimal] = Decimal("0.05")   # < piso histórico (~7,5%)
_INSS_ALIQUOTA_MAX: Final[Decimal] = Decimal("0.20")   # > teto histórico (~14%)

_IRRF_ALIQUOTA_MAX: Final[Decimal] = Decimal("0.35")   # > teto histórico (~27,5%)

_FGTS_ALIQUOTA_MIN: Final[Decimal] = Decimal("0.01")
_FGTS_ALIQUOTA_MAX: Final[Decimal] = Decimal("0.10")   # > 8% CLT

_SIMPLES_NOMINAL_MIN: Final[Decimal] = Decimal("0.04")  # ~4% faixa 1 Anexo I
_SIMPLES_NOMINAL_MAX: Final[Decimal] = Decimal("0.35")  # > 33% topo Anexo V

_PRESUNCAO_IRPJ_MIN: Final[Decimal] = Decimal("0.016")  # ~1,6% revenda combustível
_PRESUNCAO_IRPJ_MAX: Final[Decimal] = Decimal("0.40")   # > 32% serviços
_PRESUNCAO_CSLL_MIN: Final[Decimal] = Decimal("0.05")
_PRESUNCAO_CSLL_MAX: Final[Decimal] = Decimal("0.40")

_ICMS_INTERNA_MIN: Final[Decimal] = Decimal("0.04")   # ZFM 4% / FRONT
_ICMS_INTERNA_MAX: Final[Decimal] = Decimal("0.30")   # acima do teto histórico (~25%)
_ICMS_FECP_MAX: Final[Decimal] = Decimal("0.05")

# CBS/IBS — pré-Reforma plena (2033) os percentuais estimados são CBS ~8,8%
# IBS ~17,7%. Damos folga generosa para acomodar futuras revisões legais.
_CBS_IBS_ALIQUOTA_MAX: Final[Decimal] = Decimal("0.30")

_FASES_CBS_IBS_VALIDAS: Final[frozenset[str]] = frozenset(
    {
        "teste_2026",
        "transicao_2027_2028",
        "transicao_2029_2032",
        "regime_pleno_2033",
        # Hístrico/legado (caso o admin queira corrigir):
        "transicao_2027_2032",
    }
)

_UFS_BRASIL: Final[frozenset[str]] = frozenset(
    {
        "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
        "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
        "RO", "RR", "RS", "SC", "SE", "SP", "TO",
    }
)


def _raise(campo: str, mensagem: str) -> None:
    raise VigenciaTributariaInvalida(
        f"campo {campo!r}: {mensagem}",
    )


def _validar_progressao(
    valores: list[Decimal], *, campo: str
) -> None:
    """``valores[n] > valores[n-1]`` para toda n. Lista vazia ou unitária
    passa direto (caso 1 faixa em INSS contribuinte_individual ou FGTS).
    """
    if len(valores) < 2:
        return
    anterior = valores[0]
    for idx, atual in enumerate(valores[1:], start=1):
        if atual <= anterior:
            _raise(
                campo,
                f"faixa {idx + 1} ({atual}) não é maior que faixa {idx} "
                f"({anterior}) — faixas precisam ser estritamente progressivas",
            )
        anterior = atual


# ── INSS ────────────────────────────────────────────────────────────────────


def validar_vigencia_inss(payload: VigenciaInssIn) -> None:
    """Tabela INSS — progressão por tipo + plausibilidade + salário mínimo."""

    # Separa por tipo (empregado x contribuinte_individual).
    empregado = [f for f in payload.faixas if f.tipo == "empregado"]
    ci = [f for f in payload.faixas if f.tipo == "contribuinte_individual"]

    if not empregado:
        _raise(
            "faixas",
            "tabela INSS precisa de pelo menos 1 faixa do tipo 'empregado' "
            "(é o cálculo principal da folha CLT)",
        )

    # Faixas do empregado: ordenadas por 'faixa' e progressivas em 'valor_ate'.
    empregado_ordenado = sorted(empregado, key=lambda f: f.faixa)
    if [f.faixa for f in empregado_ordenado] != list(
        range(1, len(empregado_ordenado) + 1)
    ):
        _raise(
            "faixas.empregado",
            "numeração das faixas 'empregado' precisa ser 1, 2, 3, 4 "
            "(sequencial sem gaps)",
        )
    _validar_progressao(
        [f.valor_ate for f in empregado_ordenado],
        campo="faixas.empregado.valor_ate",
    )

    # Plausibilidade das alíquotas (defesa anti-typo "0.275" vs "0.0275").
    for f in payload.faixas:
        if not (_INSS_ALIQUOTA_MIN <= f.aliquota <= _INSS_ALIQUOTA_MAX):
            _raise(
                f"faixas[{f.tipo}/faixa={f.faixa}].aliquota",
                f"alíquota {f.aliquota} fora da faixa plausível INSS "
                f"[{_INSS_ALIQUOTA_MIN}, {_INSS_ALIQUOTA_MAX}] — confirme se "
                f"não foi typo (postar 0.075 em vez de 0.0075)",
            )

    # Primeira faixa cobre o salário mínimo do ano.
    try:
        sm = salario_minimo_oficial(payload.valid_from.year)
    except ValueError as exc:
        _raise("valid_from", str(exc))
        return  # unreachable mas mypy não sabe
    primeira = empregado_ordenado[0]
    if primeira.valor_ate < sm:
        _raise(
            "faixas.empregado[0].valor_ate",
            f"primeira faixa ({primeira.valor_ate}) abaixo do salário mínimo "
            f"de {payload.valid_from.year} (R$ {sm}) — quem ganha 1 SM ficaria "
            f"sem cobertura na primeira faixa",
        )

    # Contribuinte individual: 1 faixa, valor_ate = teto INSS (>= salário mínimo).
    if ci:
        if len(ci) > 1:
            _raise(
                "faixas.contribuinte_individual",
                f"contribuinte individual deve ter no máximo 1 faixa "
                f"(alíquota plana até o teto); recebido {len(ci)}",
            )
        if ci[0].valor_ate < sm:
            _raise(
                "faixas.contribuinte_individual[0].valor_ate",
                f"teto do contribuinte individual ({ci[0].valor_ate}) abaixo "
                f"do salário mínimo de {payload.valid_from.year}",
            )


# ── IRRF ────────────────────────────────────────────────────────────────────


def validar_vigencia_irrf(payload: VigenciaIrrfIn) -> None:
    """Tabela IRRF — 5 faixas progressivas + dedução por dependente plausível."""

    if [f.faixa for f in payload.faixas] != [1, 2, 3, 4, 5]:
        ordenado = sorted(payload.faixas, key=lambda f: f.faixa)
        if [f.faixa for f in ordenado] != [1, 2, 3, 4, 5]:
            _raise(
                "faixas",
                "numeração das faixas IRRF precisa ser 1, 2, 3, 4, 5 "
                "(sem repetidos nem gaps)",
            )
    ordenado = sorted(payload.faixas, key=lambda f: f.faixa)
    _validar_progressao(
        [f.base_ate for f in ordenado], campo="faixas.base_ate"
    )

    # Faixa 1 = isenção (alíquota 0). Faixas 2-5: crescentes até 27,5% típico.
    if ordenado[0].aliquota != Decimal("0"):
        _raise(
            "faixas[0].aliquota",
            f"primeira faixa IRRF é faixa de isenção (alíquota deve ser 0); "
            f"recebido {ordenado[0].aliquota}",
        )
    for f in ordenado[1:]:
        if f.aliquota > _IRRF_ALIQUOTA_MAX:
            _raise(
                f"faixas[faixa={f.faixa}].aliquota",
                f"alíquota IRRF {f.aliquota} acima do máximo plausível "
                f"({_IRRF_ALIQUOTA_MAX}) — confirme se não foi typo",
            )

    # Alíquotas progressivas (faixa N > faixa N-1).
    _validar_progressao(
        [f.aliquota for f in ordenado], campo="faixas.aliquota"
    )

    # Primeira faixa cobre o salário mínimo do ano (isenção).
    try:
        sm = salario_minimo_oficial(payload.valid_from.year)
    except ValueError as exc:
        _raise("valid_from", str(exc))
        return
    if ordenado[0].base_ate < sm:
        _raise(
            "faixas[0].base_ate",
            f"faixa de isenção IRRF ({ordenado[0].base_ate}) abaixo do "
            f"salário mínimo de {payload.valid_from.year} (R$ {sm}) — "
            f"quem ganha 1 SM seria tributado",
        )


# ── FGTS ────────────────────────────────────────────────────────────────────


def validar_vigencia_fgts(payload: VigenciaFgtsIn) -> None:
    """Tabela FGTS — alíquotas dentro da faixa histórica + sem vinculo
    repetido. ``aliquota=0.08`` é o caso canônico (Lei 8.036/1990).
    """
    vistos: set[str] = set()
    for a in payload.aliquotas:
        if a.vinculo in vistos:
            _raise(
                f"aliquotas[{a.vinculo}]",
                f"vínculo {a.vinculo!r} aparece mais de uma vez",
            )
        vistos.add(a.vinculo)
        if not (_FGTS_ALIQUOTA_MIN <= a.aliquota <= _FGTS_ALIQUOTA_MAX):
            _raise(
                f"aliquotas[{a.vinculo}].aliquota",
                f"alíquota FGTS {a.aliquota} fora da faixa plausível "
                f"[{_FGTS_ALIQUOTA_MIN}, {_FGTS_ALIQUOTA_MAX}]",
            )


# ── Simples Nacional ────────────────────────────────────────────────────────


def validar_vigencia_simples_nacional(
    payload: VigenciaSimplesNacionalIn,
) -> None:
    """Tabela Simples Nacional — 6 faixas progressivas por anexo."""
    if [f.faixa for f in payload.faixas] != [1, 2, 3, 4, 5, 6]:
        ordenado = sorted(payload.faixas, key=lambda f: f.faixa)
        if [f.faixa for f in ordenado] != [1, 2, 3, 4, 5, 6]:
            _raise(
                "faixas",
                "numeração das faixas Simples Nacional precisa ser 1..6 "
                "(sem repetidos nem gaps)",
            )
    ordenado = sorted(payload.faixas, key=lambda f: f.faixa)
    _validar_progressao(
        [f.rbt12_ate for f in ordenado], campo="faixas.rbt12_ate"
    )
    _validar_progressao(
        [f.aliquota_nominal for f in ordenado], campo="faixas.aliquota_nominal"
    )
    for f in ordenado:
        if not (
            _SIMPLES_NOMINAL_MIN <= f.aliquota_nominal <= _SIMPLES_NOMINAL_MAX
        ):
            _raise(
                f"faixas[faixa={f.faixa}].aliquota_nominal",
                f"alíquota nominal {f.aliquota_nominal} fora da faixa "
                f"plausível Simples Nacional "
                f"[{_SIMPLES_NOMINAL_MIN}, {_SIMPLES_NOMINAL_MAX}]",
            )

    # Faixa 6 do SN geralmente cobre até R$ 4.800.000 (teto LC 123).
    teto_faixa_6 = ordenado[-1].rbt12_ate
    if teto_faixa_6 < Decimal("3000000"):  # margem conservadora
        _raise(
            "faixas[5].rbt12_ate",
            f"faixa 6 do Simples Nacional cobre até {teto_faixa_6} — abaixo "
            f"do esperado (teto histórico R$ 4.800.000); confirme se não "
            f"faltou uma faixa",
        )


# ── Presunção Lucro Presumido ───────────────────────────────────────────────


def validar_vigencia_presuncao_lp(payload: VigenciaPresuncaoLpIn) -> None:
    """Presunção LP — percentuais dentro da faixa histórica (IRPJ 8-32%,
    CSLL 12-32%). Lei 9.249/1995 art. 15 §1º + art. 20.
    """
    if not payload.presuncoes:
        _raise("presuncoes", "lista de presunções vazia")

    for p in payload.presuncoes:
        if not (_PRESUNCAO_IRPJ_MIN <= p.percentual_irpj <= _PRESUNCAO_IRPJ_MAX):
            _raise(
                f"presuncoes[{p.grupo_atividade}].percentual_irpj",
                f"percentual IRPJ {p.percentual_irpj} fora da faixa plausível "
                f"[{_PRESUNCAO_IRPJ_MIN}, {_PRESUNCAO_IRPJ_MAX}]",
            )
        if not (_PRESUNCAO_CSLL_MIN <= p.percentual_csll <= _PRESUNCAO_CSLL_MAX):
            _raise(
                f"presuncoes[{p.grupo_atividade}].percentual_csll",
                f"percentual CSLL {p.percentual_csll} fora da faixa plausível "
                f"[{_PRESUNCAO_CSLL_MIN}, {_PRESUNCAO_CSLL_MAX}]",
            )


# ── ICMS por UF ─────────────────────────────────────────────────────────────


def validar_vigencia_icms_uf(payload: VigenciaIcmsUfIn) -> None:
    """ICMS por UF — UFs válidas, alíquotas internas dentro da faixa histórica."""
    vistos: set[str] = set()
    for a in payload.aliquotas:
        if a.uf not in _UFS_BRASIL:
            _raise(
                f"aliquotas[{a.uf}].uf",
                f"UF {a.uf!r} não está na lista das 27 UFs brasileiras",
            )
        if a.uf in vistos:
            _raise(
                f"aliquotas[{a.uf}]",
                f"UF {a.uf!r} aparece mais de uma vez no payload",
            )
        vistos.add(a.uf)
        if not (_ICMS_INTERNA_MIN <= a.aliquota_interna <= _ICMS_INTERNA_MAX):
            _raise(
                f"aliquotas[{a.uf}].aliquota_interna",
                f"alíquota interna {a.aliquota_interna} fora da faixa "
                f"plausível [{_ICMS_INTERNA_MIN}, {_ICMS_INTERNA_MAX}]",
            )
        if a.aliquota_fecp > _ICMS_FECP_MAX:
            _raise(
                f"aliquotas[{a.uf}].aliquota_fecp",
                f"FECP {a.aliquota_fecp} acima do máximo plausível "
                f"({_ICMS_FECP_MAX})",
            )


# ── CBS / IBS ───────────────────────────────────────────────────────────────


def validar_vigencia_cbs_ibs(payload: VigenciaCbsIbsIn) -> None:
    """CBS/IBS — fase no conjunto LC 214 + alíquotas dentro do máximo plausível."""
    for a in payload.aliquotas:
        if a.fase not in _FASES_CBS_IBS_VALIDAS:
            _raise(
                f"aliquotas[{a.fase}].fase",
                f"fase {a.fase!r} fora do conjunto LC 214/2025 "
                f"({sorted(_FASES_CBS_IBS_VALIDAS)})",
            )
        if a.aliquota_cbs > _CBS_IBS_ALIQUOTA_MAX:
            _raise(
                f"aliquotas[{a.fase}].aliquota_cbs",
                f"CBS {a.aliquota_cbs} acima do máximo plausível "
                f"({_CBS_IBS_ALIQUOTA_MAX})",
            )
        if a.aliquota_ibs > _CBS_IBS_ALIQUOTA_MAX:
            _raise(
                f"aliquotas[{a.fase}].aliquota_ibs",
                f"IBS {a.aliquota_ibs} acima do máximo plausível "
                f"({_CBS_IBS_ALIQUOTA_MAX})",
            )


__all__ = [
    "validar_vigencia_cbs_ibs",
    "validar_vigencia_fgts",
    "validar_vigencia_icms_uf",
    "validar_vigencia_inss",
    "validar_vigencia_irrf",
    "validar_vigencia_presuncao_lp",
    "validar_vigencia_simples_nacional",
]
