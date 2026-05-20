"""Parser de XML NF-e 4.0 / NFC-e.

Camada 1 (determinística). Função pura — recebe bytes, retorna dataclass.
Usa defusedxml para prevenir XXE e billion-laughs attacks (OWASP A05:2021).
Tipos em stdlib xml.etree — defusedxml retorna os mesmos objetos Element.

Princípio §8.8: apenas extrai/valida; nunca persiste.
"""

from __future__ import annotations

import xml.etree.ElementTree as StdET
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo

import defusedxml.ElementTree as ET

_NS = "http://www.portalfiscal.inf.br/nfe"
_TZ_BR = ZoneInfo("America/Sao_Paulo")

TipoDocumento = Literal["nfe", "nfce"]


@dataclass(frozen=True, slots=True)
class NFeData:
    """Campos extraídos do XML NF-e 4.0 relevantes para documento_fiscal."""

    tipo: TipoDocumento
    chave: str  # 44 dígitos
    numero: str
    serie: str
    emitida_em: datetime  # timezone-aware (America/Sao_Paulo)
    cnpj_emitente: str  # 14 dígitos
    cnpj_destinatario: str | None
    valor_total: Decimal
    valor_icms: Decimal
    valor_ipi: Decimal
    valor_pis: Decimal
    valor_cofins: Decimal
    cfop: str | None  # CFOP do primeiro item
    ncm: str | None  # NCM do primeiro item
    natureza_operacao: str
    crt: str | None  # 1=SN, 2=SN_Excesso, 3=Normal


class XmlNFeInvalido(ValueError):
    """XML não é uma NF-e/NFC-e válida ou está malformado."""


def _t(local: str) -> str:
    """Retorna tag em Clark notation: {namespace}local."""
    return f"{{{_NS}}}{local}"


def _find_text(element: StdET.Element, *path_parts: str, default: str = "") -> str:
    """Navega path_parts como caminho Clark notation e retorna texto do último elemento."""
    cur: StdET.Element | None = element
    for part in path_parts:
        if cur is None:
            return default
        cur = cur.find(_t(part))
    if cur is None:
        return default
    text = cur.text
    return text.strip() if text is not None else default


def _decimal(raw: str) -> Decimal:
    try:
        return Decimal(raw)
    except InvalidOperation:
        return Decimal("0")


def _parse_dhemi(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw.strip())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_TZ_BR)
    return dt


def parse_xml_nfe(xml_bytes: bytes) -> NFeData:
    """Extrai campos do XML NF-e 4.0 ou NFC-e.

    Raises:
        XmlNFeInvalido: Se o XML não for uma NF-e/NFC-e reconhecível.
    """
    try:
        root: StdET.Element = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise XmlNFeInvalido(f"XML malformado: {exc}") from exc

    inf_nfe: StdET.Element | None = root.find(f".//{_t('infNFe')}")
    if inf_nfe is None:
        raise XmlNFeInvalido("Elemento <infNFe> não encontrado — não é uma NF-e válida")

    mod = _find_text(inf_nfe, "ide", "mod", default="55")
    tipo: TipoDocumento = "nfce" if mod == "65" else "nfe"

    # Chave de acesso — preferência pelo protNFe
    chave = ""
    prot_nfe = root.find(f".//{_t('protNFe')}")
    if prot_nfe is not None:
        ch = prot_nfe.find(f".//{_t('chNFe')}")
        if ch is not None and ch.text:
            chave = ch.text.strip()
    if not chave:
        inf_id = inf_nfe.get("Id", "")
        chave = inf_id.removeprefix("NFe").removeprefix("NFCe")

    if len(chave) != 44 or not chave.isdigit():
        raise XmlNFeInvalido(f"Chave de acesso inválida: '{chave}'")

    numero = _find_text(inf_nfe, "ide", "nNF", default="0")
    serie = _find_text(inf_nfe, "ide", "serie", default="1")
    nat_op = _find_text(inf_nfe, "ide", "natOp")
    dh_emi_raw = _find_text(inf_nfe, "ide", "dhEmi")

    if not dh_emi_raw:
        raise XmlNFeInvalido("Campo <dhEmi> ausente")
    try:
        emitida_em = _parse_dhemi(dh_emi_raw)
    except ValueError as exc:
        raise XmlNFeInvalido(f"Data de emissão inválida: {dh_emi_raw}") from exc

    cnpj_emit = _find_text(inf_nfe, "emit", "CNPJ")
    crt_raw = _find_text(inf_nfe, "emit", "CRT")
    crt: str | None = crt_raw if crt_raw else None

    dest: StdET.Element | None = inf_nfe.find(_t("dest"))
    cnpj_dest: str | None = None
    if dest is not None:
        cnpj_dest_raw = _find_text(dest, "CNPJ")
        cnpj_dest = cnpj_dest_raw if cnpj_dest_raw else None

    icms_tot: StdET.Element | None = inf_nfe.find(f".//{_t('ICMSTot')}")
    valor_total = _decimal(_find_text(icms_tot, "vNF") if icms_tot is not None else "0")
    valor_icms = _decimal(_find_text(icms_tot, "vICMS") if icms_tot is not None else "0")
    valor_ipi = _decimal(_find_text(icms_tot, "vIPI") if icms_tot is not None else "0")
    valor_pis = _decimal(_find_text(icms_tot, "vPIS") if icms_tot is not None else "0")
    valor_cofins = _decimal(_find_text(icms_tot, "vCOFINS") if icms_tot is not None else "0")

    primeiro_det: StdET.Element | None = inf_nfe.find(_t("det"))
    cfop: str | None = None
    ncm: str | None = None
    if primeiro_det is not None:
        cfop_raw = _find_text(primeiro_det, "prod", "CFOP")
        ncm_raw = _find_text(primeiro_det, "prod", "NCM")
        cfop = cfop_raw if cfop_raw else None
        ncm = ncm_raw if ncm_raw else None

    if not cnpj_emit or len(cnpj_emit) != 14:
        raise XmlNFeInvalido(f"CNPJ do emitente inválido: '{cnpj_emit}'")

    return NFeData(
        tipo=tipo,
        chave=chave,
        numero=numero,
        serie=serie,
        emitida_em=emitida_em,
        cnpj_emitente=cnpj_emit,
        cnpj_destinatario=cnpj_dest,
        valor_total=valor_total,
        valor_icms=valor_icms,
        valor_ipi=valor_ipi,
        valor_pis=valor_pis,
        valor_cofins=valor_cofins,
        cfop=cfop,
        ncm=ncm,
        natureza_operacao=nat_op,
        crt=crt,
    )
