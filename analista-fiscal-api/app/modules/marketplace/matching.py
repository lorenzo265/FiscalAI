"""Algoritmo de matching cliente PME → contadores parceiros (Sprint 13 PR2).

Função pura, sem I/O. Recebe uma lista de candidatos já carregados do DB e
devolve o top-k ordenado por curadoria. Critérios:

  1. Filtros (HARD):
     * ``ativo=True`` (aprovado por curadoria — §10.4).
     * ``crc_status == 'ativo'`` (CRC vigente).
     * Especialidade requerida pela categoria ∈ ``especialidades`` do parceiro.
     * ``uf in uf_atuacao`` OR ``uf_atuacao is None`` (atuação nacional).

  2. Ordenação (SOFT):
     * ``rating_medio`` DESC (NULLs no fim — parceiro sem avaliação ainda).
     * ``total_consultas`` DESC (experiência prática).
     * ``taxa_resposta_horas`` ASC (responsividade — NULLs no fim).

Versionado em ``ALGORITMO_VERSAO`` para snapshot em ``consulta_marketplace`` —
mudança de critério bump explícito + regravação opcional dos rankings.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.modules.marketplace.especialidades import especialidade_para

ALGORITMO_VERSAO: str = "mkt-matching-2026.05"

# Sentinels usados pelo sort para empurrar NULLs para o fim do ranking.
# Decimal(-1) é menor que qualquer rating válido (0..5).
_RATING_AUSENTE: Decimal = Decimal("-1")
# Inteiro maior que qualquer SLA razoável (max plausível = 720h).
_TAXA_AUSENTE: int = 10**9


class _CandidatoParceiro(Protocol):
    """Shape mínimo esperado — compatível com ``ContadorParceiro`` ORM."""

    id: UUID
    nome: str
    crc_numero: str
    crc_uf: str
    crc_status: str
    especialidades: list[str]
    uf_atuacao: list[str] | None
    rating_medio: Decimal | None
    total_consultas: int
    taxa_resposta_horas: int | None
    sla_resposta_horas: int
    oab_numero: str | None
    ativo: bool


@dataclass(frozen=True, slots=True)
class ParceiroRanked:
    """Linha de saída do matching — payload enxuto para o assistente."""

    id: UUID
    nome: str
    crc_numero: str
    crc_uf: str
    especialidades: list[str]
    uf_atuacao: list[str] | None
    rating_medio: Decimal | None
    total_consultas: int
    taxa_resposta_horas: int | None
    sla_aceitar_horas: int  # vem da categoria/Pricing, não do parceiro
    oab_numero: str | None


def _passa_filtros(
    parceiro: _CandidatoParceiro,
    *,
    especialidade_requerida: str,
    uf: str | None,
) -> bool:
    if not parceiro.ativo:
        return False
    if parceiro.crc_status != "ativo":
        return False
    if especialidade_requerida not in parceiro.especialidades:
        return False
    # UF: None em uf_atuacao = atende todas. Filtro só se cliente declarou UF.
    return not (
        uf is not None
        and parceiro.uf_atuacao is not None
        and uf not in parceiro.uf_atuacao
    )


def _chave_ordenacao(
    parceiro: _CandidatoParceiro,
) -> tuple[Decimal, int, int]:
    """Quanto MAIOR a tupla, melhor o parceiro.

    Negamos ``taxa_resposta_horas`` para que "menor taxa = melhor" funcione com
    sort descendente. Empate no rating cai para experiência; empate em
    experiência cai para responsividade.
    """
    rating = parceiro.rating_medio if parceiro.rating_medio is not None else _RATING_AUSENTE
    taxa = (
        parceiro.taxa_resposta_horas
        if parceiro.taxa_resposta_horas is not None
        else _TAXA_AUSENTE
    )
    return (rating, parceiro.total_consultas, -taxa)


def top_parceiros(
    candidatos: Sequence[_CandidatoParceiro],
    *,
    categoria: str,
    uf: str | None,
    k: int = 3,
    sla_aceitar_horas: int,
) -> list[ParceiroRanked]:
    """Devolve o top-k de parceiros aptos para uma categoria + UF.

    ``categoria`` é a do marketplace (§10.3). Resolve a especialidade
    requerida via ``especialidade_para`` (fail-fast em categoria inválida).
    ``sla_aceitar_horas`` vem da ``Pricing`` da categoria — incorporado no
    output para o assistente exibir ao cliente sem nova lookup.
    """
    if k <= 0:
        return []
    especialidade = especialidade_para(categoria)
    elegiveis = [
        p
        for p in candidatos
        if _passa_filtros(p, especialidade_requerida=especialidade, uf=uf)
    ]
    elegiveis.sort(key=_chave_ordenacao, reverse=True)
    top = elegiveis[:k]
    return [
        ParceiroRanked(
            id=p.id,
            nome=p.nome,
            crc_numero=p.crc_numero,
            crc_uf=p.crc_uf,
            especialidades=list(p.especialidades),
            uf_atuacao=list(p.uf_atuacao) if p.uf_atuacao is not None else None,
            rating_medio=p.rating_medio,
            total_consultas=p.total_consultas,
            taxa_resposta_horas=p.taxa_resposta_horas,
            sla_aceitar_horas=sla_aceitar_horas,
            oab_numero=p.oab_numero,
        )
        for p in top
    ]
