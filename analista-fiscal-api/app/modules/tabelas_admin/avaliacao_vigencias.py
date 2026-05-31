"""Avaliação determinística de vigência SCD vs. data corrente (Sprint 19.5 PR2).

Função pura ``avaliar_vigencia(tipo_tabela, vigencia_ativa, hoje)`` que
devolve a "necessidade de alerta" para o worker ``tabelas.verificar_vigencias``.

Sem I/O — entra dataclass simples, sai dataclass simples. Golden-testable
(toda a complexidade de "quando é crítico vs aviso" fica nesta função).

Regras por tipo (espelhadas no spec da sprint):

  | Tabela          | Critério                                          | Severidade |
  |-----------------|---------------------------------------------------|------------|
  | INSS / IRRF     | mês ≥ março E ano(vigência) < ano(hoje)           | critico    |
  | FGTS            | hoje - valid_from > 10 anos                       | info       |
  | Simples Nacional| hoje - valid_from > 5 anos                        | aviso      |
  | Presunção LP    | hoje - valid_from > 10 anos                       | info       |
  | ICMS UF         | hoje - valid_from > 2 anos                        | aviso      |
  | CBS / IBS       | vigência futura ≤ 90 dias e nenhuma cadastrada    | info       |

Sem vigência ativa = sempre crítico (sistema operacional incompleto —
muito mais grave que "vigência desatualizada").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, Literal


Severidade = Literal["info", "aviso", "critico"]


# Marcadores tipados, exportados para o caller usar como contexto JSONB.
TIPO_VENCIDA: Final[str] = "tabela_tributaria_vencida"
TIPO_PROXIMA_VENCER: Final[str] = "tabela_proxima_vencer"
TIPO_FUTURA_PROXIMA: Final[str] = "vigencia_futura_proxima"


@dataclass(frozen=True, slots=True)
class ResultadoAvaliacao:
    """Saída da avaliação. ``deve_alertar=False`` significa "tudo OK"."""

    deve_alertar: bool
    severidade: Severidade
    tipo: str  # mapeado em TIPOS_ALERTA
    titulo: str
    descricao: str
    contexto: dict[str, object]


_OK = ResultadoAvaliacao(
    deve_alertar=False,
    severidade="info",
    tipo="",
    titulo="",
    descricao="",
    contexto={},
)


def _dias_desde(d: date, hoje: date) -> int:
    return (hoje - d).days


def _ano(d: date) -> int:
    return d.year


def avaliar_inss_irrf(
    *,
    tipo_tabela: Literal["inss", "irrf"],
    valid_from_ativa: date | None,
    hoje: date,
) -> ResultadoAvaliacao:
    """INSS/IRRF: Portaria sai em janeiro. Damos folga até março (caso
    burocrático). A partir de março, se a vigência ativa é de ano anterior,
    é **crítico** — folha sai errada todo dia.
    """
    if valid_from_ativa is None:
        return ResultadoAvaliacao(
            deve_alertar=True,
            severidade="critico",
            tipo=TIPO_VENCIDA,
            titulo=f"Tabela {tipo_tabela.upper()} ausente",
            descricao=(
                f"Nenhuma vigência {tipo_tabela.upper()} cadastrada no "
                f"sistema. Sistema operacional incompleto."
            ),
            contexto={
                "tipo_tabela": tipo_tabela,
                "ano_corrente": hoje.year,
                "ano_vigencia_ativa": None,
            },
        )
    ano_hoje = _ano(hoje)
    ano_vig = _ano(valid_from_ativa)
    if ano_vig < ano_hoje and hoje.month >= 3:
        return ResultadoAvaliacao(
            deve_alertar=True,
            severidade="critico",
            tipo=TIPO_VENCIDA,
            titulo=f"Tabela {tipo_tabela.upper()} {ano_hoje} não atualizada",
            descricao=(
                f"Portaria de {tipo_tabela.upper()} {ano_hoje} já deveria "
                f"ter sido publicada. Última atualização: "
                f"{valid_from_ativa.isoformat()} (ano {ano_vig})."
            ),
            contexto={
                "tipo_tabela": tipo_tabela,
                "ano_corrente": ano_hoje,
                "ano_vigencia_ativa": ano_vig,
                "valid_from_ativa": valid_from_ativa.isoformat(),
                "dias_desde_ultima_atualizacao": _dias_desde(
                    valid_from_ativa, hoje
                ),
            },
        )
    return _OK


def avaliar_fgts(
    *, valid_from_ativa: date | None, hoje: date
) -> ResultadoAvaliacao:
    """FGTS: Lei 8.036/1990 art. 15 — 8% raramente muda. Mas se >10 anos
    sem revisão do registro, vale info para audit interno.
    """
    if valid_from_ativa is None:
        return ResultadoAvaliacao(
            deve_alertar=True,
            severidade="critico",
            tipo=TIPO_VENCIDA,
            titulo="Tabela FGTS ausente",
            descricao=(
                "Nenhuma alíquota FGTS cadastrada — folha CLT não roda."
            ),
            contexto={
                "tipo_tabela": "fgts",
                "ano_corrente": hoje.year,
                "ano_vigencia_ativa": None,
            },
        )
    dias = _dias_desde(valid_from_ativa, hoje)
    if dias > 365 * 10:
        return ResultadoAvaliacao(
            deve_alertar=True,
            severidade="info",
            tipo=TIPO_PROXIMA_VENCER,
            titulo="FGTS sem revisão há mais de 10 anos",
            descricao=(
                f"Última vigência FGTS é de {valid_from_ativa.isoformat()} "
                f"({dias // 365} anos atrás). Confirme se ainda reflete a "
                f"lei vigente."
            ),
            contexto={
                "tipo_tabela": "fgts",
                "ano_corrente": hoje.year,
                "ano_vigencia_ativa": valid_from_ativa.year,
                "valid_from_ativa": valid_from_ativa.isoformat(),
                "dias_desde_ultima_atualizacao": dias,
            },
        )
    return _OK


def avaliar_simples_nacional(
    *, valid_from_ativa: date | None, hoje: date
) -> ResultadoAvaliacao:
    """Resolução CGSN: rara mas previsível. >5 anos sem revisão = aviso."""
    if valid_from_ativa is None:
        return ResultadoAvaliacao(
            deve_alertar=True,
            severidade="critico",
            tipo=TIPO_VENCIDA,
            titulo="Tabela Simples Nacional ausente",
            descricao="Nenhuma faixa Simples Nacional cadastrada.",
            contexto={
                "tipo_tabela": "simples_nacional",
                "ano_corrente": hoje.year,
                "ano_vigencia_ativa": None,
            },
        )
    dias = _dias_desde(valid_from_ativa, hoje)
    if dias > 365 * 5:
        return ResultadoAvaliacao(
            deve_alertar=True,
            severidade="aviso",
            tipo=TIPO_PROXIMA_VENCER,
            titulo="Simples Nacional sem revisão há mais de 5 anos",
            descricao=(
                f"Última vigência: {valid_from_ativa.isoformat()} ({dias // 365} "
                f"anos atrás). Confira se houve Resolução CGSN posterior."
            ),
            contexto={
                "tipo_tabela": "simples_nacional",
                "ano_corrente": hoje.year,
                "ano_vigencia_ativa": valid_from_ativa.year,
                "valid_from_ativa": valid_from_ativa.isoformat(),
                "dias_desde_ultima_atualizacao": dias,
            },
        )
    return _OK


def avaliar_presuncao_lp(
    *, valid_from_ativa: date | None, hoje: date
) -> ResultadoAvaliacao:
    """Lei 9.249/1995 — extremamente estável. >10 anos = info (sanity check)."""
    if valid_from_ativa is None:
        return ResultadoAvaliacao(
            deve_alertar=True,
            severidade="critico",
            tipo=TIPO_VENCIDA,
            titulo="Tabela presunção LP ausente",
            descricao=(
                "Nenhum percentual de presunção Lucro Presumido cadastrado."
            ),
            contexto={
                "tipo_tabela": "presuncao_lp",
                "ano_corrente": hoje.year,
                "ano_vigencia_ativa": None,
            },
        )
    dias = _dias_desde(valid_from_ativa, hoje)
    if dias > 365 * 10:
        return ResultadoAvaliacao(
            deve_alertar=True,
            severidade="info",
            tipo=TIPO_PROXIMA_VENCER,
            titulo="Presunção LP sem revisão há mais de 10 anos",
            descricao=(
                f"Última vigência: {valid_from_ativa.isoformat()}."
            ),
            contexto={
                "tipo_tabela": "presuncao_lp",
                "ano_corrente": hoje.year,
                "ano_vigencia_ativa": valid_from_ativa.year,
                "valid_from_ativa": valid_from_ativa.isoformat(),
                "dias_desde_ultima_atualizacao": dias,
            },
        )
    return _OK


def avaliar_icms_uf(
    *,
    uf: str,
    valid_from_ativa: date | None,
    hoje: date,
) -> ResultadoAvaliacao:
    """ICMS por UF: 27 estados mudam alíquotas com frequência razoável.
    >2 anos = aviso para revisar.
    """
    if valid_from_ativa is None:
        return ResultadoAvaliacao(
            deve_alertar=True,
            severidade="critico",
            tipo=TIPO_VENCIDA,
            titulo=f"ICMS {uf} ausente",
            descricao=(
                f"UF {uf} sem alíquota ICMS cadastrada — apuração ICMS "
                f"para empresas nessa UF falha."
            ),
            contexto={
                "tipo_tabela": "icms_uf",
                "uf": uf,
                "ano_corrente": hoje.year,
                "ano_vigencia_ativa": None,
            },
        )
    dias = _dias_desde(valid_from_ativa, hoje)
    if dias > 365 * 2:
        return ResultadoAvaliacao(
            deve_alertar=True,
            severidade="aviso",
            tipo=TIPO_PROXIMA_VENCER,
            titulo=f"ICMS {uf} sem revisão há mais de 2 anos",
            descricao=(
                f"Última vigência ICMS {uf}: {valid_from_ativa.isoformat()}. "
                f"Confira lei estadual ou convênio CONFAZ recente."
            ),
            contexto={
                "tipo_tabela": "icms_uf",
                "uf": uf,
                "ano_corrente": hoje.year,
                "ano_vigencia_ativa": valid_from_ativa.year,
                "valid_from_ativa": valid_from_ativa.isoformat(),
                "dias_desde_ultima_atualizacao": dias,
            },
        )
    return _OK


def avaliar_cbs_ibs(
    *,
    valid_from_ativa: date | None,
    proxima_vigencia_futura: date | None,
    hoje: date,
) -> ResultadoAvaliacao:
    """CBS/IBS: vigência futura ≤ 90 dias sem registro = info para o admin
    verificar se houve atualização da LC 214/2025 ou PLP 68.
    """
    if valid_from_ativa is None and proxima_vigencia_futura is None:
        return ResultadoAvaliacao(
            deve_alertar=True,
            severidade="critico",
            tipo=TIPO_VENCIDA,
            titulo="Tabela CBS/IBS ausente",
            descricao=(
                "Nenhuma vigência CBS/IBS cadastrada — Reforma Tributária "
                "ativa desde 2026."
            ),
            contexto={
                "tipo_tabela": "cbs_ibs",
                "ano_corrente": hoje.year,
                "ano_vigencia_ativa": None,
            },
        )
    if proxima_vigencia_futura is not None:
        dias_para = (proxima_vigencia_futura - hoje).days
        if 0 < dias_para <= 90:
            return ResultadoAvaliacao(
                deve_alertar=True,
                severidade="info",
                tipo=TIPO_FUTURA_PROXIMA,
                titulo="CBS/IBS — nova fase em ≤ 90 dias",
                descricao=(
                    f"Próxima vigência CBS/IBS em {proxima_vigencia_futura.isoformat()} "
                    f"({dias_para} dias). Confirme que as alíquotas refletem a "
                    f"LC 214/2025 + regulamentação do Comitê Gestor IBS."
                ),
                contexto={
                    "tipo_tabela": "cbs_ibs",
                    "ano_corrente": hoje.year,
                    "proxima_vigencia": proxima_vigencia_futura.isoformat(),
                    "dias_para_vigencia": dias_para,
                },
            )
    return _OK


__all__ = [
    "ResultadoAvaliacao",
    "Severidade",
    "TIPO_FUTURA_PROXIMA",
    "TIPO_PROXIMA_VENCER",
    "TIPO_VENCIDA",
    "avaliar_cbs_ibs",
    "avaliar_fgts",
    "avaliar_icms_uf",
    "avaliar_inss_irrf",
    "avaliar_presuncao_lp",
    "avaliar_simples_nacional",
]
