"""Parser de XML NF-e 4.0 / NFC-e.

Camada 1 (determinística). Função pura — recebe bytes, retorna dataclass.
Usa defusedxml para prevenir XXE e billion-laughs attacks (OWASP A05:2021).
Tipos em stdlib xml.etree — defusedxml retorna os mesmos objetos Element.

Princípio §8.8: apenas extrai/valida; nunca persiste.

Sprint 18 PR1: ``parse_xml_nfe`` passa a popular ``NFeData.itens`` lendo
``<det>`` em sequência (pendência #26 resolvida). Campos agregados do
cabeçalho permanecem para retrocompat — quem só precisa do total da NF
não muda nada; quem precisa de granularidade lê ``itens``.
"""

from __future__ import annotations

import xml.etree.ElementTree as StdET  # nosec B405 — usado só para tipos stdlib; parse usa defusedxml abaixo
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from zoneinfo import ZoneInfo

import defusedxml.ElementTree as ET

_NS = "http://www.portalfiscal.inf.br/nfe"
_TZ_BR = ZoneInfo("America/Sao_Paulo")

TipoDocumento = Literal["nfe", "nfce"]


@dataclass(frozen=True, slots=True)
class NFeItem:
    """Item de uma NF-e — granularidade por linha (``<det nItem=N>``).

    Sprint 18 PR1 — pendência #26 resolvida. Persistido em
    ``documento_fiscal_item`` (1:N com ``documento_fiscal``). Os campos
    de imposto (``valor_icms``, ``valor_pis``, etc.) são opcionais
    porque NF-e pode ter linhas com tributação suspensa/isenta sem o
    bloco específico.
    """

    n_item: int
    codigo_produto: str | None
    descricao: str
    ncm: str | None
    cfop: str | None
    cst_icms: str | None
    cst_pis: str | None
    cst_cofins: str | None
    unidade: str | None
    quantidade: Decimal
    valor_unitario: Decimal
    valor_total: Decimal
    valor_icms: Decimal | None = None
    valor_ipi: Decimal | None = None
    valor_pis: Decimal | None = None
    valor_cofins: Decimal | None = None
    valor_cbs: Decimal | None = None
    valor_ibs: Decimal | None = None


@dataclass(frozen=True, slots=True)
class NFeData:
    """Campos extraídos do XML NF-e 4.0/4.x relevantes para documento_fiscal.

    Campos CBS/IBS (Reforma Tributária, NT 2025/001) são opcionais: NF-e 4.0
    sem extensão IBSCBS preserva valores ``None``. Sprint 14 PR2.

    Sprint 18 PR1: ``itens`` traz a granularidade por linha (pendência #26).
    Cabeçalho continua agregando: ``valor_total`` = soma de ``valor_total``
    dos itens (validado em ``parse_xml_nfe`` se ICMSTot e itens diferirem
    por mais de R$0,02 — tolerância de arredondamento NF-e).
    """

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
    # ── Reforma Tributária (NF-e 4.x extensão IBSCBS) — opcionais ──────────
    valor_cbs: Decimal | None = None     # <total><IBSCBSTot><vCBS>
    valor_ibs: Decimal | None = None     # <total><IBSCBSTot><vIBS>
    cclasstrib: str | None = None        # <det><imposto><IBSCBS><cClassTrib>
    # ── Itens (Sprint 18 PR1) ───────────────────────────────────────────────
    itens: list[NFeItem] = field(default_factory=list)


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


def _decimal_opt(raw: str) -> Decimal | None:
    """Variante de ``_decimal`` que devolve ``None`` para string vazia.

    Usada para campos opcionais (CBS/IBS) onde NULL é informação relevante:
    NF-e 4.0 sem extensão NÃO traz a tag — não devemos persistir 0,00 nem
    ``Decimal("0")`` como se a tag estivesse presente com valor zero.
    """
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _parse_dhemi(raw: str) -> datetime:
    dt = datetime.fromisoformat(raw.strip())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_TZ_BR)
    return dt


def _imposto_valor(det: StdET.Element, *tag_path: str) -> Decimal | None:
    """Busca um campo ``vXXX`` dentro de ``<det><imposto>`` em caminho variável.

    NF-e tem ICMS00/10/20/.../ICMSSN101/.../IPITrib/IPINT/... em variantes —
    fazemos varredura por tag ``vICMS``/``vIPI``/``vPIS``/``vCOFINS`` em
    qualquer sub-elemento de imposto. Devolve ``None`` se o campo não
    está presente (item isento/suspenso sem valor declarado).
    """
    imposto = det.find(_t("imposto"))
    if imposto is None:
        return None
    # Procura recursivamente o primeiro elemento com a tag de valor.
    target_local = tag_path[-1]
    for elem in imposto.iter():
        # iter() devolve tags em Clark notation; comparamos sufixo local.
        local = elem.tag.rpartition("}")[2]
        if local == target_local:
            text = (elem.text or "").strip()
            if not text:
                return None
            try:
                return Decimal(text)
            except InvalidOperation:
                return None
    return None


def _parse_item(det: StdET.Element) -> NFeItem | None:
    """Extrai um ``<det>`` em ``NFeItem``. Devolve ``None`` se inválido."""
    n_item_raw = det.get("nItem", "")
    try:
        n_item = int(n_item_raw)
    except ValueError:
        return None
    if n_item < 1:
        return None

    prod = det.find(_t("prod"))
    if prod is None:
        return None

    descricao = _find_text(prod, "xProd")
    if not descricao:
        # NF-e sem xProd é inválida — pula o item silenciosamente.
        return None

    codigo_raw = _find_text(prod, "cProd")
    codigo = codigo_raw if codigo_raw else None
    ncm_raw = _find_text(prod, "NCM")
    ncm = ncm_raw if ncm_raw and ncm_raw.isdigit() and len(ncm_raw) == 8 else None
    cfop_raw = _find_text(prod, "CFOP")
    cfop = cfop_raw if cfop_raw and cfop_raw.isdigit() and len(cfop_raw) == 4 else None
    unidade_raw = _find_text(prod, "uCom")
    unidade = unidade_raw if unidade_raw else None
    quantidade = _decimal(_find_text(prod, "qCom") or "0")
    valor_unitario = _decimal(_find_text(prod, "vUnCom") or "0")
    valor_total = _decimal(_find_text(prod, "vProd") or "0")

    # CST por tributo — caminho exato varia (ICMSSN, ICMS00, ICMS40...).
    cst_icms: str | None = None
    cst_pis: str | None = None
    cst_cofins: str | None = None
    imposto = det.find(_t("imposto"))
    if imposto is not None:
        icms_block = imposto.find(_t("ICMS"))
        if icms_block is not None:
            # Subtipo: ICMS00, ICMS10, ICMSSN101, etc. — pegamos qualquer filho.
            for child in icms_block:
                cst_raw = (
                    _find_text(child, "CST")
                    or _find_text(child, "CSOSN")
                )
                if cst_raw:
                    cst_icms = cst_raw
                    break
        pis_block = imposto.find(_t("PIS"))
        if pis_block is not None:
            for child in pis_block:
                cst_raw = _find_text(child, "CST")
                if cst_raw:
                    cst_pis = cst_raw
                    break
        cofins_block = imposto.find(_t("COFINS"))
        if cofins_block is not None:
            for child in cofins_block:
                cst_raw = _find_text(child, "CST")
                if cst_raw:
                    cst_cofins = cst_raw
                    break

    valor_icms = _imposto_valor(det, "vICMS")
    valor_ipi = _imposto_valor(det, "vIPI")
    valor_pis = _imposto_valor(det, "vPIS")
    valor_cofins = _imposto_valor(det, "vCOFINS")

    # CBS/IBS por item (Reforma Tributária)
    valor_cbs: Decimal | None = None
    valor_ibs: Decimal | None = None
    if imposto is not None:
        ibscbs = imposto.find(_t("IBSCBS"))
        if ibscbs is not None:
            valor_cbs = _decimal_opt(_find_text(ibscbs, "vCBS"))
            valor_ibs = _decimal_opt(_find_text(ibscbs, "vIBS"))

    return NFeItem(
        n_item=n_item,
        codigo_produto=codigo,
        descricao=descricao,
        ncm=ncm,
        cfop=cfop,
        cst_icms=cst_icms,
        cst_pis=cst_pis,
        cst_cofins=cst_cofins,
        unidade=unidade,
        quantidade=quantidade if quantidade > 0 else Decimal("1"),
        valor_unitario=valor_unitario,
        valor_total=valor_total,
        valor_icms=valor_icms,
        valor_ipi=valor_ipi,
        valor_pis=valor_pis,
        valor_cofins=valor_cofins,
        valor_cbs=valor_cbs,
        valor_ibs=valor_ibs,
    )


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

    # ── Itens (Sprint 18 PR1) ──────────────────────────────────────────────
    itens: list[NFeItem] = []
    for det in inf_nfe.findall(_t("det")):
        item = _parse_item(det)
        if item is not None:
            itens.append(item)

    # Cabeçalho — agregados do primeiro item para retrocompat.
    primeiro_det: StdET.Element | None = inf_nfe.find(_t("det"))
    cfop: str | None = None
    ncm: str | None = None
    cclasstrib: str | None = None
    if primeiro_det is not None:
        cfop_raw = _find_text(primeiro_det, "prod", "CFOP")
        ncm_raw = _find_text(primeiro_det, "prod", "NCM")
        cfop = cfop_raw if cfop_raw else None
        ncm = ncm_raw if ncm_raw else None
        # ── Reforma Tributária — cClassTrib (NF-e 4.x extensão IBSCBS) ────
        # Caminho canônico: <det><imposto><IBSCBS><cClassTrib>. Ausência é
        # esperada em NF-e 4.0 — fallback silencioso para None.
        ibscbs_det: StdET.Element | None = primeiro_det.find(
            f"{_t('imposto')}/{_t('IBSCBS')}"
        )
        if ibscbs_det is not None:
            cclasstrib_raw = _find_text(ibscbs_det, "cClassTrib")
            cclasstrib = cclasstrib_raw if cclasstrib_raw else None

    # ── Reforma Tributária — totais CBS/IBS (extensão IBSCBSTot) ─────────
    # NF-e 4.0 sem extensão NÃO traz a tag — valor_cbs/valor_ibs ficam None
    # (distinto de 0,00, que sinalizaria nota com IBSCBSTot presente mas zerado).
    ibs_cbs_tot: StdET.Element | None = inf_nfe.find(f".//{_t('IBSCBSTot')}")
    valor_cbs: Decimal | None = None
    valor_ibs: Decimal | None = None
    if ibs_cbs_tot is not None:
        valor_cbs = _decimal_opt(_find_text(ibs_cbs_tot, "vCBS"))
        valor_ibs = _decimal_opt(_find_text(ibs_cbs_tot, "vIBS"))

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
        valor_cbs=valor_cbs,
        valor_ibs=valor_ibs,
        cclasstrib=cclasstrib,
        itens=itens,
    )
