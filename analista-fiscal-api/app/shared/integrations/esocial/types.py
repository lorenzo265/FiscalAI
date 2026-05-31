"""Tipos do contrato cliente eSocial — payload de lote, recibo, estados."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Final


class EstadoLote(IntEnum):
    """Estados oficiais do processamento do lote eSocial.

    Documentados no Manual de Orientação do Desenvolvedor S-1.3 §3.4.
    """

    ENVIADO = 1
    EM_PROCESSAMENTO = 2
    PROCESSADO_COM_ERROS = 3
    PROCESSADO = 4
    REJEITADO = 5


# Códigos de retorno por evento (subset comum).
COD_RETORNO_SUCESSO: Final = "201"
COD_RETORNO_SCHEMA_INVALIDO: Final = "401"


@dataclass(frozen=True, slots=True)
class EventoLote:
    """Evento pronto pra empacotar num lote (XML já assinado)."""

    id_evento: str  # atributo Id do <evt*>
    xml_assinado: bytes  # bytes UTF-8 do XML completo


@dataclass(frozen=True, slots=True)
class LoteEnviado:
    """Resultado de POST /lotes/eventos — protocolo + estado inicial."""

    protocolo: str  # nrProtocolo (até 40 chars)
    enviado_em: datetime
    estado: EstadoLote = EstadoLote.ENVIADO


@dataclass(frozen=True, slots=True)
class ReciboEvento:
    """Recibo individual de um evento dentro de um lote processado."""

    id_evento: str
    numero_recibo: str | None
    codigo_retorno: str  # "201" = OK
    descricao: str
    ocorrencias: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReciboLote:
    """Resposta de GET /lotes/eventos/{protocolo}."""

    protocolo: str
    estado: EstadoLote
    consultado_em: datetime
    eventos: tuple[ReciboEvento, ...] = field(default_factory=tuple)

    @property
    def finalizado(self) -> bool:
        return self.estado in (
            EstadoLote.PROCESSADO,
            EstadoLote.PROCESSADO_COM_ERROS,
            EstadoLote.REJEITADO,
        )
