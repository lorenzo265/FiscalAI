"""Conjunto fechado de especialidades + mapping categoria → especialidade.

Cada ``ContadorParceiro`` declara um conjunto de especialidades
(``especialidades JSONB`` no DB). O matching (PR2) filtra parceiros cuja lista
contenha a especialidade requerida pela categoria da consulta.

Conjunto fechado para evitar drift — novas especialidades exigem bump de
``ESPECIALIDADES_VERSAO`` + atualização do mapa.
"""

from __future__ import annotations

ESPECIALIDADES_VERSAO: str = "mkt-especialidades-2026.05"


# Conjunto fechado. Curadoria controla quem entra.
ESPECIALIDADES: frozenset[str] = frozenset(
    {
        "tributario",
        "trabalhista",
        "societario",
        "contencioso",
        "planejamento",
        "operacoes",
    }
)


# Categoria do marketplace → especialidade requerida. Categorias jurídicas
# (peticao_administrativa, defesa_auto) recomendam OAB, mas a especialidade
# requerida no parceiro é "contencioso" — OAB é checada em curadoria, não
# no matching automático.
_CATEGORIA_PARA_ESPECIALIDADE: dict[str, str] = {
    "consulta_rapida": "tributario",
    "analise_intimacao_simples": "contencioso",
    "analise_intimacao_complexa": "contencioso",
    "parecer_tecnico": "tributario",
    "peticao_administrativa": "contencioso",
    "defesa_auto": "contencioso",
    "planejamento_tributario": "planejamento",
    "holding": "societario",
    "sucessao": "societario",
}


def especialidade_para(categoria: str) -> str:
    """Devolve a especialidade requerida — fail-fast em categoria desconhecida."""
    try:
        return _CATEGORIA_PARA_ESPECIALIDADE[categoria]
    except KeyError as exc:
        raise ValueError(
            f"Categoria desconhecida: {categoria!r}. Sem especialidade mapeada."
        ) from exc


def validar_especialidades(valores: list[str]) -> None:
    """Levanta ``ValueError`` se qualquer item não estiver em ``ESPECIALIDADES``.

    Lista vazia é rejeitada — parceiro sem nenhuma especialidade não aparece
    em nenhum matching, então cadastrar nesse estado é erro de input.
    """
    if not valores:
        raise ValueError("Especialidades vazias: declarar pelo menos uma.")
    invalidas = [v for v in valores if v not in ESPECIALIDADES]
    if invalidas:
        raise ValueError(
            f"Especialidades inválidas: {invalidas}. "
            f"Aceitas: {sorted(ESPECIALIDADES)}"
        )
