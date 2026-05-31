"""Cronograma da Reforma Tributária (LC 214/2025 art. 124+).

Função pura — não toca DB, não chama LLM. Encapsula o mapeamento
competência → fase para uso pelo simulador e pelo lookup SCD.

Cronograma da Reforma (resumido):

  * **2026** — período de teste informacional. CBS 0,9% + IBS 0,1% (1,0%
    total) coexistem com PIS+Cofins+ICMS+ISS sem recolhimento separado.
  * **2027-2032** — CBS plena substitui PIS+Cofins. IBS continua em
    período de teste (0,1%). ICMS+ISS reduzem gradualmente.
  * **2033+** — regime pleno. IBS plenamente substitui ICMS+ISS. Apenas
    CBS+IBS+IS coexistem.

Datas críticas confirmadas (LC 214/2025):
  * 2026-01-01 → início da cobrança-teste (art. 348 §3º)
  * 2027-01-01 → CBS plena entra em vigor (art. 349)
  * 2033-01-01 → ICMS+ISS extintos (art. 124)
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from app.shared.exceptions import PeriodoReformaNaoMapeado


class FaseReforma(StrEnum):
    """Fases da transição da Reforma Tributária."""

    TESTE_2026 = "teste_2026"
    TRANSICAO = "transicao_2027_2032"
    PLENO = "regime_pleno_2033"


# ── Datas-chave (LC 214/2025) ────────────────────────────────────────────────
INICIO_TESTE_2026 = date(2026, 1, 1)
INICIO_TRANSICAO = date(2027, 1, 1)
INICIO_PLENO = date(2033, 1, 1)


def fase(competencia: date) -> FaseReforma:
    """Devolve a fase da Reforma vigente em ``competencia``.

    Args:
        competencia: data dentro do mês de apuração (qualquer dia serve).

    Returns:
        FaseReforma — TESTE_2026, TRANSICAO ou PLENO.

    Raises:
        PeriodoReformaNaoMapeado: competência anterior a 2026-01-01.
    """
    if competencia < INICIO_TESTE_2026:
        raise PeriodoReformaNaoMapeado(
            f"Competência {competencia.isoformat()} é anterior ao início da "
            f"Reforma Tributária ({INICIO_TESTE_2026.isoformat()}). LC 214/2025 "
            f"art. 348 §3º — cobrança-teste só inicia em 01/01/2026."
        )
    if competencia < INICIO_TRANSICAO:
        return FaseReforma.TESTE_2026
    if competencia < INICIO_PLENO:
        return FaseReforma.TRANSICAO
    return FaseReforma.PLENO
