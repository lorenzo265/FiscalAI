from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentoFiscalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    tipo: str
    direcao: str
    chave: str | None
    numero: str
    serie: str
    status: str
    emitida_em: datetime
    cnpj_emitente: str
    cnpj_destinatario: str | None
    valor_total: Decimal
    valor_icms: Decimal | None
    valor_ipi: Decimal | None
    valor_pis: Decimal | None
    valor_cofins: Decimal | None
    cfop: str | None
    ncm: str | None
    natureza_operacao: str | None
    ingested_via: str | None
    created_at: datetime


class IngestaoResultadoOut(BaseModel):
    documento: DocumentoFiscalOut
    mensagem: str
