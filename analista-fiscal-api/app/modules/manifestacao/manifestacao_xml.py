"""Gerador XML determinístico para eventos de Manifestação do Destinatário NF-e (MD-e).

Camada 1 puramente determinística — zero I/O, zero side-effects.
Golden-testável: mesmos inputs → mesmo XML.

Fonte normativa:
  * NT 2014.002 v1.10 (Evento de Manifestação do Destinatário — layout principal)
  * NT 2020.001 v1.10 (atualização de prazos e regras de manifestação)
  * Manual de Orientação ao Contribuinte (MOC) NF-e v7.0 §5.4

Layout ``envEvento`` versão 1.00 (namespace portalfiscal.inf.br/nfe):
  <envEvento versao="1.00">
    <idLote>{idLote}</idLote>
    <evento versao="1.00">
      <infEvento Id="ID{tpEvento(6)}{chNFe(44)}{nSeqEvento(02d)}">
        <cOrgao>91</cOrgao>            <!-- Ambiente Nacional (NT 2014.002 §4.1) -->
        <tpAmb>{tpAmb}</tpAmb>         <!-- 1=prod, 2=homologação -->
        <CNPJ>{cnpj_destinatario}</CNPJ>
        <chNFe>{chave_nfe}</chNFe>
        <dhEvento>{ISO-8601-TZ}</dhEvento>
        <tpEvento>{tipo_evento}</tpEvento>
        <nSeqEvento>{sequencial}</nSeqEvento>
        <verEvento>1.00</verEvento>
        <detEvento versao="1.00">
          <descEvento>{desc}</descEvento>
          <!-- apenas 210240: -->
          <xJust>{justificativa}</xJust>
        </detEvento>
      </infEvento>
    </evento>
  </envEvento>

A assinatura XMLDSig (XmldsigSigner) é aplicada **fora** desta função
(camada de serviço). A separação é proposital: a parte pura é testável
sem deps de criptografia; a assinatura é side-effect com cert do cliente.

Decisões de design registradas:
  * ``cOrgao = 91`` (Ambiente Nacional) é fixo para MD-e — NT 2014.002 §4.1.1.
    Manifestação de destinatário não é roteada pelo cOrgao do emitente.
  * ``verEvento = 1.00`` — único leiaute oficial até NT 2020.001.
  * ``idLote`` é derivado de ``chave_nfe + tipo_evento + sequencial``
    via SHA-256[:12] → inteiro (15 dígitos máximo exigido pelo leiaute).
    Garante unicidade sem UUID (leiaute exige numérico).
  * Namespace fixo: ``http://www.portalfiscal.inf.br/nfe``.
  * ``dhEvento`` em ISO 8601 com offset de fuso (``aware datetime``),
    ex.: ``2026-06-29T14:00:00-03:00`` (isoformat() nativo do Python).
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET  # nosec B405 — gera XML próprio; não parseia entrada externa
from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

ALGORITMO_VERSAO: Final = "mde.xml.v1"

_NS: Final = "http://www.portalfiscal.inf.br/nfe"
_VERSAO_EVENTO: Final = "1.00"
_C_ORGAO: Final = "91"  # Ambiente Nacional — NT 2014.002 §4.1.1
_TZ_BR: Final = ZoneInfo("America/Sao_Paulo")

# Mapa tpEvento → descEvento (exatamente conforme o XSD do leiaute)
_DESC_EVENTO: Final[dict[str, str]] = {
    "210200": "Confirmacao da Operacao",
    "210210": "Ciencia da Operacao",
    "210220": "Desconhecimento da Operacao",
    "210240": "Operacao nao Realizada",
}

# tpEvento que exige <xJust>
_TIPOS_COM_JUSTIFICATIVA: Final = frozenset({"210240"})

# Tipos que NÃO devem ter justificativa
_TIPOS_SEM_JUSTIFICATIVA: Final = frozenset({"210200", "210210", "210220"})


def desc_evento(tipo_evento: str) -> str:
    """Retorna o descEvento oficial para o tipo de evento.

    Args:
        tipo_evento: Um dos 4 tipos válidos ('210200', '210210', '210220', '210240').

    Returns:
        String exata do campo ``<descEvento>`` do leiaute (sem acento,
        conforme XSD da SEFAZ).

    Raises:
        ValueError: tipo_evento desconhecido.
    """
    if tipo_evento not in _DESC_EVENTO:
        raise ValueError(
            f"tipo_evento desconhecido: {tipo_evento!r}. "
            f"Tipos válidos: {sorted(_DESC_EVENTO)}"
        )
    return _DESC_EVENTO[tipo_evento]


def _gerar_id_lote(chave_nfe: str, tipo_evento: str, sequencial: int) -> str:
    """Gera idLote numérico determinístico (≤ 15 dígitos).

    SHA-256[:12] dos 3 campos → converte para int base-16 → módulo 10^15.
    Garante unicidade dentro de uma empresa sem UUID.
    """
    conteudo = f"{chave_nfe}{tipo_evento}{sequencial:02d}"
    digest = hashlib.sha256(conteudo.encode("utf-8")).hexdigest()[:12]
    return str(int(digest, 16) % (10**15))


def gerar_id_infevento(
    tipo_evento: str,
    chave_nfe: str,
    sequencial: int,
) -> str:
    """Gera o atributo ``Id`` do ``<infEvento>``.

    Formato NT 2014.002 §4.1.1.2:
      ``ID + tpEvento(6) + chNFe(44) + nSeqEvento(2 dígitos zero-padded)``
      Total = 2 + 6 + 44 + 2 = 54 caracteres.

    Args:
        tipo_evento: '210200', '210210', '210220' ou '210240'.
        chave_nfe: 44 dígitos da chave de acesso NF-e.
        sequencial: nSeqEvento (int ≥ 1).

    Returns:
        String no formato ``ID2102001234...567890123401``.
    """
    return f"ID{tipo_evento}{chave_nfe}{sequencial:02d}"


def gerar_xml_evento(
    *,
    cnpj_destinatario: str,
    chave_nfe: str,
    tipo_evento: str,
    sequencial: int,
    tp_amb: str,
    dh_evento: datetime,
    justificativa: str | None = None,
) -> tuple[str, str]:
    """Gera o XML canônico do evento MD-e e o atributo Id.

    Função pura — sem I/O. Valida os argumentos e constrói o XML.

    Args:
        cnpj_destinatario: CNPJ do destinatário (14 dígitos, sem máscara).
        chave_nfe: Chave de acesso da NF-e (44 dígitos numéricos).
        tipo_evento: '210200', '210210', '210220' ou '210240'.
        sequencial: nSeqEvento (tipicamente 1; máximo 20 por tipo/nota).
        tp_amb: '1' (produção) ou '2' (homologação).
        dh_evento: datetime aware (America/Sao_Paulo ou UTC).
        justificativa: texto de 15–255 chars; obrigatório em 210240,
            proibido nos demais (service valida antes de chamar esta função).

    Returns:
        Tupla (xml_str, id_infevento) onde:
        - xml_str: XML serializado sem declaração ``<?xml ...?>``, UTF-8.
        - id_infevento: valor do atributo ``Id`` da ``<infEvento>``.

    Raises:
        ValueError: argumento inválido (chave, tipo, sequencial, fuso).

    Decisão: a função não assina — assinatura é responsabilidade do
    ``XmldsigSigner`` (camada de serviço). Esta função só gera a estrutura
    canônica que o assinador recebe como entrada.
    """
    # ── Validações de entrada ─────────────────────────────────────────────────
    if not re.fullmatch(r"\d{44}", chave_nfe):
        raise ValueError(
            f"chave_nfe deve ter exatamente 44 dígitos numéricos: {chave_nfe!r}"
        )
    if not re.fullmatch(r"\d{14}", cnpj_destinatario):
        raise ValueError(
            f"cnpj_destinatario deve ter 14 dígitos numéricos: {cnpj_destinatario!r}"
        )
    if tipo_evento not in _DESC_EVENTO:
        raise ValueError(
            f"tipo_evento inválido: {tipo_evento!r}. "
            f"Tipos válidos: {sorted(_DESC_EVENTO)}"
        )
    if sequencial < 1 or sequencial > 20:
        raise ValueError(
            f"sequencial deve ser entre 1 e 20 (NT 2014.002): {sequencial}"
        )
    if tp_amb not in ("1", "2"):
        raise ValueError(
            f"tp_amb deve ser '1' (prod) ou '2' (homolog): {tp_amb!r}"
        )
    if dh_evento.tzinfo is None:
        raise ValueError(
            "dh_evento deve ser aware (com tzinfo). Use ZoneInfo('America/Sao_Paulo')."
        )
    # Justificativa: obrigatória em 210240, proibida nos outros
    if tipo_evento in _TIPOS_COM_JUSTIFICATIVA:
        if justificativa is None:
            raise ValueError(
                "Evento 210240 exige justificativa (NT 2014.002 §4.1.1.3)."
            )
        if not (15 <= len(justificativa) <= 255):
            raise ValueError(
                f"justificativa deve ter entre 15 e 255 chars: {len(justificativa)}"
            )
    else:
        if justificativa is not None:
            raise ValueError(
                f"Evento {tipo_evento} não aceita justificativa "
                "(exclusiva do tipo 210240)."
            )

    # ── Montagem XML ─────────────────────────────────────────────────────────
    id_infevento = gerar_id_infevento(tipo_evento, chave_nfe, sequencial)
    id_lote = _gerar_id_lote(chave_nfe, tipo_evento, sequencial)

    # Formata dhEvento em ISO-8601 com offset de fuso: 2026-06-29T14:00:00-03:00
    dh_str = dh_evento.isoformat()

    root = ET.Element("envEvento", {"xmlns": _NS, "versao": _VERSAO_EVENTO})

    ET.SubElement(root, "idLote").text = id_lote

    evento_el = ET.SubElement(root, "evento", {"versao": _VERSAO_EVENTO})
    inf_evento = ET.SubElement(evento_el, "infEvento", {"Id": id_infevento})

    ET.SubElement(inf_evento, "cOrgao").text = _C_ORGAO
    ET.SubElement(inf_evento, "tpAmb").text = tp_amb
    ET.SubElement(inf_evento, "CNPJ").text = cnpj_destinatario
    ET.SubElement(inf_evento, "chNFe").text = chave_nfe
    ET.SubElement(inf_evento, "dhEvento").text = dh_str
    ET.SubElement(inf_evento, "tpEvento").text = tipo_evento
    ET.SubElement(inf_evento, "nSeqEvento").text = str(sequencial)
    ET.SubElement(inf_evento, "verEvento").text = _VERSAO_EVENTO

    det_evento = ET.SubElement(inf_evento, "detEvento", {"versao": _VERSAO_EVENTO})
    ET.SubElement(det_evento, "descEvento").text = _DESC_EVENTO[tipo_evento]
    if justificativa is not None:
        ET.SubElement(det_evento, "xJust").text = justificativa

    xml_str = ET.tostring(root, encoding="unicode", short_empty_elements=False)
    return xml_str, id_infevento
