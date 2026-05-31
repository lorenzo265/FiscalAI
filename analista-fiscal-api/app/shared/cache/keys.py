"""Helpers de chave para o cache Redis (Sprint 19 PR2).

Convenções:
  * Hierarquia ``<dominio>:<entidade>:<id_ou_query>`` — facilita invalidação
    por SCAN com padrões como ``scd:cbs_ibs:*``.
  * SCD lookups SEMPRE incluem a competência (ou data de referência) na
    chave. SCD2 é versionado por ``valid_from/valid_to`` — cachear sem
    data_referencia é envenenamento garantido.
  * Ordem de filtros opcionais é fixa para evitar fragmentação
    (``regime`` antes de ``cnae`` antes de ``classificacao``).
  * Chaves não contêm PII (CNPJ, email, telefone) — sempre IDs/datas.

§8.7 LGPD: nenhum helper aqui aceita PII; tudo derivado de IDs e datas.
"""

from __future__ import annotations

from datetime import date


def _slot(valor: str | None) -> str:
    """Normaliza filtro opcional: None → ``-`` (string fixa que não conflita)."""
    return valor if valor is not None else "-"


def aliquota_cbs_ibs_key(
    competencia: date,
    *,
    regime: str | None,
    cnae: str | None,
    classificacao: str | None,
) -> str:
    """Chave do SCD lookup de alíquota CBS/IBS.

    Estrutura: ``scd:cbs_ibs:<YYYY-MM-DD>:<regime>:<cnae>:<classificacao>``.

    Cada combinação produz uma chave única. Pattern de invalidação:
    ``scd:cbs_ibs:*`` limpa toda a tabela em 1 SCAN.
    """
    return (
        f"scd:cbs_ibs:{competencia.isoformat()}:"
        f"{_slot(regime)}:{_slot(cnae)}:{_slot(classificacao)}"
    )


def scd_cache_pattern(tabela: str | None = None) -> str:
    """Padrão para invalidar caches SCD por tabela.

    Sem argumento → ``scd:*`` (toda a família SCD).
    Com ``tabela='cbs_ibs'`` → ``scd:cbs_ibs:*``.
    """
    if tabela is None:
        return "scd:*"
    return f"scd:{tabela}:*"
