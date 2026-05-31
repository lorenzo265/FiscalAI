"""Schemas do subsystema de alertas (Sprint 19.5 PR2).

Separado de ``schemas.py`` para manter o arquivo do PR1 enxuto — alerta é
um conceito operacional, não input de vigência tributária.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.types import JsonObject


Severidade = Literal["info", "aviso", "critico"]


# Tipos de alerta gerados pelo worker tabelas.verificar_vigencias.
# Centralizado aqui para que o worker, o service e os testes não
# divirjam do contrato.
TIPOS_ALERTA: tuple[str, ...] = (
    "tabela_tributaria_vencida",  # INSS/IRRF não atualizada no ano corrente
    "tabela_proxima_vencer",      # FGTS/Presunção/SN/ICMS UF com vigência velha
    "vigencia_futura_proxima",    # CBS/IBS — vigência futura ≤ 90 dias
    "sugestao_vigencia_disponivel",  # reservado PR3 (DOU + LLM gera sugestão)
)


class AlertaAdminOut(BaseModel):
    """Representação do alerta para os endpoints GET."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tipo: str
    severidade: Severidade
    titulo: str
    descricao: str
    contexto_jsonb: JsonObject
    idempotency_key: UUID
    resolvido_em: datetime | None
    resolvido_por_usuario_id: UUID | None
    criado_em: datetime


class SnoozeIn(BaseModel):
    """Payload do POST /alertas/{id}/snooze."""

    model_config = ConfigDict(extra="forbid")

    dias: int = Field(default=30, ge=1, le=90)


__all__ = ["AlertaAdminOut", "Severidade", "SnoozeIn", "TIPOS_ALERTA"]
