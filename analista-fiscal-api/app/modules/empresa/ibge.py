"""Resolução de código IBGE 7-dígitos a partir do nome do município — função pura.

A BrasilAPI ``/cnpj`` retorna apenas o NOME do município (ex.: "São Paulo"),
mas as integrações fiscais (Focus NFe, SERPRO PGDAS-D) exigem o código IBGE
de 7 dígitos (ex.: "3550308"). Este módulo resolve o IBGE via match exato
contra a lista oficial de municípios da UF (consulta BrasilAPI
``/ibge/municipios/v1/{uf}`` — chamada feita pelo onboarding).

Princípios aplicados:
  * Função pura — zero I/O, zero dependência de banco ou rede.
  * Determinística — mesmo input → mesmo output.
  * Match defensivo — normalização NFKD + lowercase + remoção de acentos
    cobre divergências entre BrasilAPI (maiúsculas) e IBGE (mixed case).
"""

from __future__ import annotations

import unicodedata
from typing import Mapping


def _normalizar(texto: str) -> str:
    """Lowercase + remoção de acentos + strip — match robusto entre fontes."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acentos.lower().strip()


def resolver_ibge(
    nome_municipio: str | None,
    municipios_uf: list[Mapping[str, object]],
) -> str | None:
    """Resolve código IBGE 7-dígitos a partir do nome do município.

    Args:
        nome_municipio: Nome do município (ex.: "São Paulo", "SAO PAULO").
        municipios_uf: Lista de dicts da BrasilAPI ``/ibge/municipios/v1/{uf}``,
            cada um com chaves ``nome`` (str) e ``codigo_ibge`` (str ou int).

    Returns:
        Código IBGE 7-dígitos como string (ex.: "3550308"), ou ``None`` se não
        houver match exato (após normalização). Não tenta fuzzy match — chamador
        deve fail-open e logar para diagnóstico.

    Note:
        Homônimos entre UFs (ex.: "Boa Vista" RR vs PB) são resolvidos porque o
        chamador passa apenas a lista da UF correta. Homônimos dentro da mesma
        UF não existem no IBGE (cada município tem código único).
    """
    if not nome_municipio:
        return None

    alvo = _normalizar(nome_municipio)
    if not alvo:
        return None

    for municipio in municipios_uf:
        nome = municipio.get("nome")
        codigo = municipio.get("codigo_ibge")
        if not isinstance(nome, str) or codigo is None:
            continue
        if _normalizar(nome) == alvo:
            codigo_str = str(codigo)
            if len(codigo_str) == 7 and codigo_str.isdigit():
                return codigo_str

    return None
