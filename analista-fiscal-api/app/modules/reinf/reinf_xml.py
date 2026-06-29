"""Gerador XML determinístico para eventos EFD-Reinf (Marco 4 PR2 #11).

Camada 1 (determinística). Função pura, zero I/O. Espelha
``app/modules/pessoal/esocial_xml.py``.

Transforma o dict produzido por ``reinf.esocial_payload.gerar_r4020`` no XML
canônico do leiaute EFD-Reinf v2.1.2, namespace
``http://www.reinf.esocial.gov.br/schemas/<evento>/v2_01_02``.

**O que ESTÁ coberto aqui:**
  * Estrutura `<Reinf xmlns=...><evtPgtoBenefPJ Id="ID..."><...></...></Reinf>`
  * Conversão determinística das chaves snake_case do payload → tags
    camelCase do leiaute (``ide_contri`` → ``ideContri``); chaves já em
    camelCase passam intactas.
  * Geração do atributo `Id` (`ID + tpInsc + nrInsc + AAAAMMDDhhmmss + seq`).
  * Skip de campos nulos e de chaves "meta"/internas (prefixo ``_``).

**O que NÃO está coberto (pendência consciente — diferido, igual eSocial):**
  * Assinatura XMLDSig (fica no ``XmldsigSigner``, fora desta função).
  * Validação contra o XSD oficial.
  * Eventos além do R-4020 (R-2010, R-9000…).

A separação é proposital: a parte determinística é golden-testável;
assinatura + envio são side-effect com cert do cliente (§8.12).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # nosec B405 — gera/serializa XML próprio; não parseia entrada externa
from collections.abc import Mapping
from datetime import date, datetime
from typing import Final
from zoneinfo import ZoneInfo

from app.shared.types import JsonObject

ALGORITMO_VERSAO: Final = "reinf.xml.v1"
_VERSAO_LEIAUTE: Final = "2_01_02"
_NS_BASE: Final = "http://www.reinf.esocial.gov.br/schemas"
_TZ_BR: Final = ZoneInfo("America/Sao_Paulo")


# Mapeia o "tipo" do payload para o slug do evento (tag raiz) e o slug do XSD.
_EVT_SLUG: Final[Mapping[str, str]] = {
    "R-4020": "evtPgtoBenefPJ",
}
_EVT_XSD_PATH: Final[Mapping[str, str]] = {
    "R-4020": "evt4020PagtoBeneficiarioPJ",
}


# Chaves "meta" do dict que NÃO viram tags XML.
_KEYS_META: Final = frozenset({
    "tipo", "versao_leiaute", "algoritmo_versao",
})


def _snake_to_camel(key: str) -> str:
    """``ide_contri`` → ``ideContri``; chaves sem ``_`` passam intactas."""
    if "_" not in key:
        return key
    head, *tail = key.split("_")
    return head + "".join(p[:1].upper() + p[1:] for p in tail)


def gerar_id_evento(
    cnpj: str,
    sequencial: int = 1,
    *,
    agora: datetime | None = None,
) -> str:
    """Gera o atributo `Id` do evento EFD-Reinf.

    Formato: ``ID + 1 + 14 dígitos do CNPJ + AAAAMMDDhhmmss + 5-dig seq``
    (1 = inscrição por CNPJ). Aceita ``agora`` pra ser pura/golden-testável.
    """
    if not re.fullmatch(r"\d{14}", cnpj):
        raise ValueError(f"CNPJ deve ter 14 dígitos: {cnpj!r}")
    if sequencial < 1 or sequencial > 99999:
        raise ValueError(f"sequencial fora de [1, 99999]: {sequencial}")
    ts = (agora or datetime.now(_TZ_BR)).strftime("%Y%m%d%H%M%S")
    return f"ID1{cnpj}{ts}{sequencial:05d}"


def _to_xml_value(v: object) -> str | None:
    """Converte valores Python → string XML. Retorna None para skip."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "S" if v else "N"
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _build_element(parent: ET.Element, key: str, value: object) -> None:
    """Constrói recursivamente uma tag (camelCase) dentro de ``parent``."""
    if value is None:
        return
    tag = _snake_to_camel(key)
    if isinstance(value, dict):
        if not value:
            return
        child = ET.SubElement(parent, tag)
        for k, v in value.items():
            if k in _KEYS_META or k.startswith("_"):
                continue
            _build_element(child, k, v)
        return
    if isinstance(value, list | tuple):
        # EFD-Reinf repete a MESMA tag para listas (ex.: <infoPgto>...).
        for item in value:
            _build_element(parent, key, item)
        return
    txt = _to_xml_value(value)
    if txt is None:
        return
    child = ET.SubElement(parent, tag)
    child.text = txt


def serializar_para_xml(
    payload: JsonObject,
    *,
    id_evento: str | None = None,
    agora: datetime | None = None,
) -> str:
    """Converte o dict do R-4020 (``gerar_r4020``) em XML canônico.

    Args:
        payload: dict com chave ``tipo`` == 'R-4020'.
        id_evento: atributo Id. Se ``None``, é gerado do CNPJ em
            ``ide_contri.nrInsc``.
        agora: usado quando ``id_evento`` é gerado — facilita teste golden.

    Returns:
        String XML UTF-8 sem declaração ``<?xml ...?>`` (canonicaliza antes
        de assinar).

    Raises:
        ValueError: tipo de evento desconhecido ou payload incompleto.
    """
    tipo = payload.get("tipo")
    if not isinstance(tipo, str) or tipo not in _EVT_SLUG:
        raise ValueError(
            f"Tipo de evento desconhecido ou ausente: {tipo!r}. "
            f"Tipos suportados: {sorted(_EVT_SLUG)}"
        )
    evt_slug = _EVT_SLUG[tipo]
    xsd_slug = _EVT_XSD_PATH[tipo]
    namespace = f"{_NS_BASE}/{xsd_slug}/v{_VERSAO_LEIAUTE}"

    ide_contri = payload.get("ide_contri")
    cnpj = (
        ide_contri.get("nrInsc")
        if isinstance(ide_contri, dict)
        and isinstance(ide_contri.get("nrInsc"), str)
        else None
    )
    if id_evento is None:
        if cnpj is None:
            raise ValueError(
                "id_evento não fornecido e CNPJ ausente em ide_contri.nrInsc"
            )
        id_evento = gerar_id_evento(cnpj, agora=agora)

    root = ET.Element("Reinf", {"xmlns": namespace})
    evt = ET.SubElement(root, evt_slug, {"Id": id_evento})

    for k, v in payload.items():
        if k in _KEYS_META or k.startswith("_"):
            continue
        _build_element(evt, k, v)

    return ET.tostring(root, encoding="unicode", short_empty_elements=False)
