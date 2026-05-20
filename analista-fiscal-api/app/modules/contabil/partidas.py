"""Validação pura do conjunto de partidas de um lançamento contábil.

Zero I/O. Decimal-safe. Determinístico.

Invariantes verificados:
  1. Há ao menos 2 partidas (mínimo D+C).
  2. Σ débitos = Σ créditos (partidas dobradas).
  3. Todas as partidas têm valor > 0.
  4. Todas referenciam contas analíticas (``aceita_lancamento=True``).
  5. Todas as contas pertencem à mesma empresa do lançamento.
  6. As contas referenciadas estão vigentes na ``competencia`` (entre
     ``valid_from`` e ``valid_to``, conforme SCD Type 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

ALGORITMO_VERSAO = "partidas-2026.05"


@dataclass(frozen=True, slots=True)
class ContaView:
    """Subset imutável de ``ContaContabil`` usado pelo validador."""

    id: UUID
    empresa_id: UUID
    aceita_lancamento: bool
    valid_from: date
    valid_to: date | None


@dataclass(frozen=True, slots=True)
class PartidaIn:
    """Partida candidata — antes de virar :class:`PartidaLancamento`."""

    conta_id: UUID
    tipo: str  # 'D' ou 'C'
    valor: Decimal


@dataclass(frozen=True, slots=True)
class ResultadoValidacao:
    valido: bool
    erros: tuple[str, ...]
    total_debito: Decimal
    total_credito: Decimal
    versao: str = ALGORITMO_VERSAO


def validar_partidas(
    partidas: list[PartidaIn],
    contas: dict[UUID, ContaView],
    *,
    empresa_id: UUID,
    competencia: date,
) -> ResultadoValidacao:
    """Roda todas as validações invariantes do conjunto de partidas.

    Args:
        partidas: lista candidata.
        contas: lookup por id — deve cobrir todas as ``conta_id`` referenciadas.
        empresa_id: tenant da operação (defesa em profundidade além de RLS).
        competencia: data usada para verificar vigência da conta (SCD).

    Returns:
        ResultadoValidacao acumulando TODOS os erros encontrados — não para
        no primeiro. O caller decide se levanta exceção ou retorna 422 com
        a lista completa.
    """
    erros: list[str] = []
    total_d = Decimal("0.00")
    total_c = Decimal("0.00")

    if len(partidas) < 2:
        erros.append("min_2_partidas")

    for idx, p in enumerate(partidas):
        if p.tipo not in {"D", "C"}:
            erros.append(f"partida_{idx}_tipo_invalido:{p.tipo}")
            continue
        if p.valor <= Decimal("0"):
            erros.append(f"partida_{idx}_valor_nao_positivo")
            continue

        if p.tipo == "D":
            total_d += p.valor
        else:
            total_c += p.valor

        conta = contas.get(p.conta_id)
        if conta is None:
            erros.append(f"partida_{idx}_conta_nao_encontrada:{p.conta_id}")
            continue

        if conta.empresa_id != empresa_id:
            erros.append(f"partida_{idx}_conta_outra_empresa")
            continue

        if not conta.aceita_lancamento:
            erros.append(f"partida_{idx}_conta_sintetica")
            continue

        if not _vigente_em(conta, competencia):
            erros.append(f"partida_{idx}_conta_fora_vigencia")
            continue

    # Invariante das partidas dobradas — só checa se tiver partidas válidas suficientes.
    if total_d != total_c:
        erros.append(
            f"partidas_desbalanceadas:D={total_d}_C={total_c}"
        )

    return ResultadoValidacao(
        valido=not erros,
        erros=tuple(erros),
        total_debito=total_d,
        total_credito=total_c,
    )


def _vigente_em(conta: ContaView, em: date) -> bool:
    if conta.valid_from > em:
        return False
    if conta.valid_to is not None and conta.valid_to < em:
        return False
    return True
