"""Tipos do contrato cliente EFD-Reinf — payload de lote, recibo, estados.

Espelha ``app/shared/integrations/esocial/types.py`` (Marco 4 PR2 #11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Final


class EstadoLote(IntEnum):
    """Estados do processamento do lote assíncrono EFD-Reinf.

    A recepção assíncrona devolve um protocolo; a consulta posterior
    informa o andamento. Os códigos espelham a semântica do eSocial:
    1/2 = ainda processando; 3/4/5 = finalizado.
    """

    ENVIADO = 1
    EM_PROCESSAMENTO = 2
    PROCESSADO_COM_ERROS = 3
    PROCESSADO = 4
    REJEITADO = 5


@dataclass(frozen=True, slots=True)
class EventoLote:
    """Evento pronto pra empacotar num lote (XML já assinado)."""

    id_evento: str  # atributo Id do <evt*>
    xml_assinado: bytes  # bytes UTF-8 do XML completo


@dataclass(frozen=True, slots=True)
class LoteEnviado:
    """Resultado de POST de recepção — protocolo + estado inicial."""

    protocolo: str  # nrProtocolo (até 40 chars)
    enviado_em: datetime
    estado: EstadoLote = EstadoLote.ENVIADO


@dataclass(frozen=True, slots=True)
class ReciboEvento:
    """Recibo individual de um evento dentro de um lote processado.

    EFD-Reinf emite ``nrRecibo`` apenas para eventos aceitos; eventos
    rejeitados vêm sem recibo e com ``ocorrencias`` de erro. O service
    usa a presença de ``numero_recibo`` como sinal de aceitação.
    """

    id_evento: str
    numero_recibo: str | None
    codigo_retorno: str
    descricao: str
    ocorrencias: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ReciboLote:
    """Resposta da consulta de recibo do lote."""

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


# Marcadores de ocorrência (subset comum) — só para logs/depuração.
COD_OCORRENCIA_ERRO: Final = "erro"
