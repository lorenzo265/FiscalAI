"""Schemas Pydantic v2 — Manifestação do Destinatário NF-e (MD-e).

PR1: RegistrarManifestacaoIn, ManifestacaoNFeOut, TipoEventoManifestacaoIn.
PR2: NfeDestinadaOut, SincronizarManifestacaoIn, SincronizacaoResultadoOut.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TipoEventoManifestacaoIn(StrEnum):
    """Enum dos 4 tipos de evento MD-e (NT 2014.002)."""

    CONFIRMACAO = "210200"
    CIENCIA = "210210"
    DESCONHECIMENTO = "210220"
    NAO_REALIZADA = "210240"


class RegistrarManifestacaoIn(BaseModel):
    """Registra um evento de manifestação do destinatário.

    Idempotência: passe ``idempotency_key`` para evitar duplicatas
    em retentativas. Sem a chave, a unicidade é por
    (empresa, chave_nfe, tipo_evento, sequencial).

    ``justificativa`` é obrigatória APENAS para o tipo 210240
    (Operação não Realizada) e proibida nos demais.
    """

    model_config = ConfigDict(extra="forbid")

    chave_nfe: Annotated[
        str,
        Field(
            min_length=44,
            max_length=44,
            pattern=r"^\d{44}$",
            description="Chave de acesso NF-e — 44 dígitos numéricos (NT 2014.002 §4.1.1.2).",
        ),
    ]
    cnpj_destinatario: Annotated[
        str,
        Field(
            min_length=14,
            max_length=14,
            pattern=r"^\d{14}$",
            description="CNPJ do destinatário que manifesta (14 dígitos sem máscara).",
        ),
    ]
    tipo_evento: TipoEventoManifestacaoIn
    sequencial: Annotated[
        int,
        Field(
            ge=1,
            le=20,
            default=1,
            description=(
                "nSeqEvento — tipicamente 1. "
                "Permite até 20 por tipo de evento/nota (NT 2014.002)."
            ),
        ),
    ]
    justificativa: Annotated[
        str | None,
        Field(
            default=None,
            min_length=15,
            max_length=255,
            description=(
                "xJust: obrigatório para tipo 210240, proibido nos demais. "
                "15–255 caracteres (NT 2014.002 §4.1.1.3)."
            ),
        ),
    ]
    tp_amb: Annotated[
        str,
        Field(
            default="1",
            pattern=r"^[12]$",
            description="Ambiente SEFAZ: '1'=produção, '2'=homologação.",
        ),
    ]
    idempotency_key: Annotated[
        str | None,
        Field(
            default=None,
            max_length=100,
            description=(
                "Chave opaca de idempotência cross-system (§8.9). "
                "Se fornecida e já existir, retorna o registro existente "
                "sem criar duplicata."
            ),
        ),
    ]


class ManifestacaoNFeOut(BaseModel):
    """Representação de uma Manifestação do Destinatário persistida."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    chave_nfe: str
    cnpj_destinatario: str
    tipo_evento: str
    sequencial: int
    justificativa: str | None
    status: str
    protocolo: str | None
    codigo_status_sefaz: int | None
    motivo_sefaz: str | None
    xml_evento_storage_key: str | None
    algoritmo_versao: str
    criado_em: datetime
    assinado_em: datetime | None
    transmitido_em: datetime | None
    respondido_em: datetime | None


# ── PR2: Descoberta (DistribuiçãoDFe) ────────────────────────────────────────


class NfeDestinadaOut(BaseModel):
    """NF-e emitida contra o CNPJ da empresa, descoberta pelo DistribuiçãoDFe.

    Gerada pelo upsert idempotente do ``DistribuicaoService.sincronizar``.
    Valor em Decimal (nunca float). Datas aware.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    chave_nfe: str
    nsu: int
    emitente_cnpj: str | None
    emitente_nome: str | None
    valor_total: Decimal | None
    dh_emissao: datetime | None
    tipo_documento: str  # 'resumo' | 'completo'
    tem_xml_completo: bool
    xml_storage_key: str | None
    criado_em: datetime
    atualizado_em: datetime


class SincronizarManifestacaoIn(BaseModel):
    """Body opcional para o endpoint POST /manifestacao/sincronizar.

    Nenhum campo é obrigatório. ``extra='forbid'`` recusa campos desconhecidos
    para evitar confusion silenciosa.
    """

    model_config = ConfigDict(extra="forbid")

    # Reservado para extensões futuras (PR3: flag para forçar re-sync completo,
    # override de max_paginas, etc.). Atualmente sem campos obrigatórios.


class SincronizacaoResultadoOut(BaseModel):
    """Resultado de uma sincronização do DistribuiçãoDFe.

    ``truncado=True`` indica que o loop foi interrompido pelo cap ``max_paginas``
    antes de consumir todos os documentos disponíveis. Uma nova chamada ao endpoint
    continuará do ``ult_nsu`` persistido no cursor.
    """

    model_config = ConfigDict(from_attributes=False)

    novos: int
    """Documentos inseridos pela primeira vez nesta sincronização."""

    atualizados: int
    """Documentos já existentes que foram atualizados (re-sync idempotente)."""

    ult_nsu: int
    """Último NSU consumido (persistido no cursor da empresa)."""

    max_nsu: int
    """Maior NSU disponível no Ambiente Nacional para o CNPJ da empresa."""

    truncado: bool
    """True quando a sincronização foi interrompida pelo cap de páginas."""
