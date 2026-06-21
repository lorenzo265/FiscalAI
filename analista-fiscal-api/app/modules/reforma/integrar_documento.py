"""Integração da Reforma com ``documento_fiscal`` (Sprint 14 PR2).

Helper puro: para NF cujo XML não trouxe ``vCBS``/``vIBS`` (NF-e 4.0 sem
extensão IBSCBS), calcula o **informacional** usando a base = valor_total
e a alíquota vigente para a competência da nota.

**Princípio §8.8** — este helper NÃO escreve no DB. Quem chama (service
da ingestão ou worker de backfill do PR3) é responsável por persistir.
Mantemos a função pura para ficar trivialmente testável + idempotente.

**Princípio §8.2** — esta integração só popula campos ainda NULL. Nunca
sobrescreve valor_cbs/valor_ibs vindos do XML (que são os fatos oficiais
da nota). O retorno indica explicitamente se houve cálculo ou não.

LC 214/2025 art. 41-42 + Resolução CGSN:
O Simples Nacional e MEI NÃO apuram/destacam CBS/IBS na fase TESTE_2026.
Quando ``regime_tributario`` for ``"simples_nacional"`` ou ``"mei"`` e a
``aliquotas.fase`` for ``FaseReforma.TESTE_2026``, este helper devolve
``calculou=False`` com valores zerados (não-aplicável).  Em 2027+ a
restrição cessa e o SN/MEI passa a destacar normalmente.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.modules.reforma.calcula_cbs_ibs import (
    ALGORITMO_VERSAO,
    AliquotaCBSIBS,
    ResultadoCBSIBS,
    calcular_cbs_ibs,
    regime_excluido_fase_teste,
)


class _DocLike(Protocol):
    """Subset de ``DocumentoFiscal`` usado por este helper.

    Aceitamos Protocol em vez de import direto do model SQLAlchemy para
    deixar o helper testável com ``SimpleNamespace`` (Sprint 14 PR2).
    """

    valor_total: Decimal
    valor_cbs: Decimal | None
    valor_ibs: Decimal | None


@dataclass(frozen=True, slots=True)
class IntegracaoCbsIbs:
    """Resultado da tentativa de popular CBS/IBS informacional.

    Quando ``calculou=False`` significa que os campos já vinham populados do
    XML (NF-e 4.x com extensão IBSCBSTot) — caller deve fazer no-op.

    Quando ``calculou=True``, ``valor_cbs``/``valor_ibs`` são os valores
    informacionais a serem persistidos. ``observacao`` carrega a label de
    estimativa (§8.12).
    """

    calculou: bool
    valor_cbs: Decimal
    valor_ibs: Decimal
    base_calculo: Decimal
    observacao: str
    algoritmo_versao: str


_ZERO = Decimal("0")

_OBS_SN_EXCLUIDO_2026 = (
    "Simples Nacional/MEI excluído do destaque CBS/IBS na fase de teste 2026 "
    "(LC 214/2025 art. 41-42 + Resolução CGSN). Destaque informacional não "
    "aplicável nesta competência."
)


def popular_cbs_ibs_informacional(
    doc: _DocLike,
    aliquotas: AliquotaCBSIBS,
    *,
    regime_tributario: str | None = None,
) -> IntegracaoCbsIbs:
    """Calcula CBS/IBS informacional para documento sem extensão IBSCBSTot.

    Não persiste — caller é responsável por aplicar ``valor_cbs``/
    ``valor_ibs`` no documento e fazer commit.

    Args:
        doc: documento fiscal — precisa ter ``valor_total``, ``valor_cbs``
            e ``valor_ibs`` (que serão lidos para idempotência).
        aliquotas: vigência resolvida pelo ``AliquotaCbsIbsRepo.vigente()``
            para a competência da nota.
        regime_tributario: regime tributário da empresa emissora/receptora
            (``empresa.regime_tributario``).  Quando ``"simples_nacional"``
            ou ``"mei"`` e ``aliquotas.fase == TESTE_2026``, devolve
            ``calculou=False`` com valores 0 e observação explicativa
            (LC 214/2025 art. 41-42).  Em 2027+ (TRANSICAO/PLENO) a
            restrição não se aplica — calcula normalmente.

    Returns:
        ``IntegracaoCbsIbs`` com ``calculou=False`` se:
          * documento já tem valor_cbs E valor_ibs populados (idempotente);
          * regime SN/MEI na fase TESTE_2026 (não-aplicável por lei).
        ``calculou=True`` com valores calculados nos demais casos.

    Raises:
        BaseCalculoInvalida: valor_total negativo (defeito de ingestão).
    """
    # ── Guard: SN/MEI excluído na fase TESTE_2026 (LC 214/2025 art. 41-42) ─
    if regime_excluido_fase_teste(regime_tributario, aliquotas.fase):
        return IntegracaoCbsIbs(
            calculou=False,
            valor_cbs=_ZERO,
            valor_ibs=_ZERO,
            base_calculo=doc.valor_total,
            observacao=_OBS_SN_EXCLUIDO_2026,
            algoritmo_versao=ALGORITMO_VERSAO,
        )

    # ── Idempotência (§8.9) ──────────────────────────────────────────────
    # Se ambos já estão populados, devolve o existente sem recalcular.
    if doc.valor_cbs is not None and doc.valor_ibs is not None:
        return IntegracaoCbsIbs(
            calculou=False,
            valor_cbs=doc.valor_cbs,
            valor_ibs=doc.valor_ibs,
            base_calculo=doc.valor_total,
            observacao=(
                "Valores CBS/IBS já presentes no documento (vindos do XML). "
                "Backfill não-aplicável."
            ),
            algoritmo_versao=aliquotas.algoritmo_versao,
        )

    # ── Cálculo informacional sobre valor_total ──────────────────────────
    # Base = valor_total da nota. No regime informacional 2026 isso pode
    # diferir da "base CBS/IBS" oficial (que excluiria CBS/IBS por dentro),
    # mas como em 2026 a cobrança é informativa, a aproximação é aceita —
    # o simulador do PR3 refina com cenários.
    resultado: ResultadoCBSIBS = calcular_cbs_ibs(doc.valor_total, aliquotas)
    return IntegracaoCbsIbs(
        calculou=True,
        valor_cbs=resultado.valor_cbs,
        valor_ibs=resultado.valor_ibs,
        base_calculo=resultado.base_calculo,
        observacao=resultado.observacao_estimativa,
        algoritmo_versao=resultado.algoritmo_versao,
    )
