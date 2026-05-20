"""TypedDicts do envelope SERPRO Integra Contador (Fase 2 PR4).

A SERPRO usa um envelope estável em todos os serviços (CND, PGDAS-D, DEFIS,
DASN-SIMEI, e-CAC, …). A estrutura interna de ``pedidoDados.dados`` varia
por serviço — esse campo carrega um JSON serializado em string, então fica
fora do TypedDict do envelope.

Refs: Manual Integra Contador — https://apicenter.estaleiro.serpro.gov.br
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict


class SerproParticipante(TypedDict):
    """Contratante / autor / contribuinte. ``tipo``: 1=CPF, 2=CNPJ."""

    numero: str
    tipo: int


class SerproPedidoDados(TypedDict):
    idSistema: str
    idServico: str
    versaoSistema: str
    dados: str  # JSON serializado — schema interno depende do serviço


class SerproRequest(TypedDict):
    contratante: SerproParticipante
    autorPedidoDados: SerproParticipante
    contribuinte: SerproParticipante
    pedidoDados: SerproPedidoDados


class SerproMensagem(TypedDict, total=False):
    codigo: str
    texto: str


class SerproResponse(TypedDict, total=False):
    """Envelope de resposta — todos os campos opcionais (varia por serviço)."""

    status: int
    dados: str  # JSON serializado, caller faz json.loads e interpreta
    mensagens: list[SerproMensagem]
    contratante: SerproParticipante
    contribuinte: SerproParticipante


# Inputs que o caller monta dinamicamente (PGDAS-D payload, DEFIS payload, etc.).
# Mapeamento aberto — schema-by-service vive no service correspondente.
SerproDadosDeclaracao = Mapping[str, object]
