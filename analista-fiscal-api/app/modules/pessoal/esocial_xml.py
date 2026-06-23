"""Gerador XML determinístico para eventos eSocial (Sprint 10 PR3+).

Camada 1 (determinística). Função pura, zero I/O.

Transforma o dict produzido por ``esocial_payloads.gerar_sXXXX_*`` no XML
canônico do leiaute S-1.3, namespace
``http://www.esocial.gov.br/schema/evt/<evento>/v_S_01_03_00``.

**O que ESTÁ coberto aqui:**
  * Estrutura `<eSocial xmlns=...><evt<EVENTO> Id="ID..."><...></...></evt...>...`
  * Mapeamento determinístico camelCase do payload → tags XML
  * Ordem de tags preservada (eSocial é schema strict — ordem importa)
  * Geração do atributo `Id` segundo leiaute (`ID + tpInsc + nrInsc + perApur + seq`)
  * Skip de campos nulos (eSocial não aceita `<tag></tag>` vazia em opcionais)
  * Escape XML padrão (`&`, `<`, `>`, `"`, `'`)

**O que NÃO está coberto (pendência consciente — diferido):**
  * Assinatura digital XMLDSig com certificado A1 (.pfx ICP-Brasil)
  * Envio à API eSocial (lote, manifest, recibo)
  * Validação contra XSD oficial (`schemas-S-1.3.xsd`)
  * Tabelas eSocial S-1xxx (rubricas, lotações, estabelecimentos)
  * Eventos não-cobertos (S-2205, S-2206, S-2230, S-2298, S-2300, S-3000)

A separação é proposital: a parte determinística pode ser testada via
golden tests; assinatura + envio são side-effect com cert do cliente e
ficam para sprint dedicada (§8.12 "transmissão é ato consciente").

Quando a assinatura + transmissão entrarem, o pipeline será:

    dict_payload    = gerar_s1200_remuneracao(...)      # esta sprint
    xml_canonico    = serializar_para_xml(dict_payload) # esta sprint
    xml_assinado    = assinar_xmldsig(xml_canonico, cert_a1) # sprint futura
    recibo          = enviar_para_esocial(xml_assinado) # sprint futura
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # nosec B405 — gera/serializa XML próprio; não parseia entrada externa
from collections.abc import Mapping
from datetime import date, datetime
from typing import Final
from zoneinfo import ZoneInfo

from app.shared.types import JsonObject

# Sprint 19.7 PR2 (#13): adiciona S-2205/2206/2230/2298/3000 (transmissão real).
ALGORITMO_VERSAO: Final = "esocial.xml.v3"
_VERSAO_LEIAUTE: Final = "S_01_03_00"
_NS_BASE: Final = "http://www.esocial.gov.br/schema/evt"
_TZ_BR: Final = ZoneInfo("America/Sao_Paulo")


# Mapeia o "tipo" do payload para o slug do XSD eSocial.
# Sprint 19.6 PR1 (#14): S-2400 (RPPS) substituído por S-2300 (TSVE Início).
# Sprint 19.7 PR2 (#13): adiciona S-2205/2206/2230/2298/3000.
_EVT_SLUG: Final[Mapping[str, str]] = {
    "S-1200": "evtRemun",
    "S-1210": "evtPgtos",
    "S-2200": "evtAdmissao",
    "S-2205": "evtAltCadastral",
    "S-2206": "evtAltContratual",
    "S-2230": "evtAfastTemp",
    "S-2298": "evtReintegr",
    "S-2299": "evtDeslig",
    "S-2300": "evtTSVInicio",
    "S-3000": "evtExclusao",
}


# Sub-paths NAMESPACE — eSocial usa schemas por evento.
_EVT_XSD_PATH: Final[Mapping[str, str]] = {
    "S-1200": "remun",
    "S-1210": "pgtosTrab",
    "S-2200": "admissao",
    "S-2205": "altCadastral",
    "S-2206": "altContratual",
    "S-2230": "afastTemp",
    "S-2298": "reintegr",
    "S-2299": "desligTSV",
    "S-2300": "TSVInicio",
    "S-3000": "exclusao",
}


# Chaves "meta" do dict que NÃO viram tags XML.
_KEYS_META: Final = frozenset({
    "tipo", "versao_leiaute", "algoritmo_versao",
})


def gerar_id_evento(
    cnpj: str,
    perApur: str | None,
    sequencial: int = 1,
    *,
    agora: datetime | None = None,
) -> str:
    """Gera o atributo `Id` exigido pelo eSocial (35 chars total).

    Formato: ``ID + (1 ou 2) + 14 dígitos do CNPJ + AAAAMMDDhhmmss + 5-dig seq``
    onde 1=CNPJ, 2=CPF. Total: 2 + 1 + 14 + 14 + 5 = 36 chars (oficial: 36).

    Para tornar a função pura (golden-testável), aceita `agora` como input.
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
    if isinstance(v, date) and not isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _build_element(parent: ET.Element, key: str, value: object) -> None:
    """Constrói recursivamente uma tag dentro de ``parent``."""
    if value is None:
        return
    if isinstance(value, dict):
        if not value:
            return
        child = ET.SubElement(parent, key)
        for k, v in value.items():
            _build_element(child, k, v)
        return
    if isinstance(value, list | tuple):
        # eSocial usa repetição da MESMA tag para listas (ex.: <dmDev>...</dmDev><dmDev>...).
        for item in value:
            _build_element(parent, key, item)
        return
    txt = _to_xml_value(value)
    if txt is None:
        return
    child = ET.SubElement(parent, key)
    child.text = txt


def serializar_para_xml(
    payload: JsonObject,
    *,
    id_evento: str | None = None,
    agora: datetime | None = None,
) -> str:
    """Converte dict do payload (esocial_payloads.gerar_*) em XML canônico.

    Args:
        payload: dict produzido por ``gerar_sXXXX_*``. Deve conter chave
            ``tipo`` com 'S-1200'..'S-2299' ou 'S-2300' (TSVE).
        id_evento: atributo Id do evento. Se ``None``, é gerado via
            ``gerar_id_evento`` a partir do CNPJ em `ide_empregador.nrInsc`.
        agora: usado quando ``id_evento`` é gerado — facilita teste golden.

    Returns:
        String XML UTF-8 sem declaração ``<?xml ...?>`` no início
        (eSocial canonicaliza antes de assinar; a declaração não vai junto).

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

    # Computa Id do evento se não veio explícito.
    ide_emp = payload.get("ide_empregador")
    cnpj = (
        ide_emp.get("nrInsc")
        if isinstance(ide_emp, dict) and isinstance(ide_emp.get("nrInsc"), str)
        else None
    )
    if id_evento is None:
        if cnpj is None:
            raise ValueError(
                "id_evento não fornecido e CNPJ ausente em ide_empregador.nrInsc"
            )
        ide_evt = payload.get("ide_evento")
        per_apur = (
            ide_evt.get("perApur")
            if isinstance(ide_evt, dict) and isinstance(ide_evt.get("perApur"), str)
            else None
        )
        id_evento = gerar_id_evento(cnpj, per_apur, agora=agora)

    # Elemento raiz: <eSocial xmlns="...">
    root = ET.Element("eSocial", {"xmlns": namespace})
    evt = ET.SubElement(root, evt_slug, {"Id": id_evento})

    # Anexa as seções do payload, exceto metadata.
    for k, v in payload.items():
        if k in _KEYS_META:
            continue
        _build_element(evt, k, v)

    # Serializa — short_empty_elements=False para tags vazias virem <tag></tag>.
    return ET.tostring(root, encoding="unicode", short_empty_elements=False)
