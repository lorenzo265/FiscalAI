"""Parser SPED EFD-Contribuições mensal (Sprint 18 PR3).

**Camada 1 (determinística).** Reverte o gerador
``app/modules/sped/efd/gerador_contribuicoes.py`` (Sprint 17 PR1).

Extrai do arquivo:

* **0000** — cabeçalho (CNPJ + competência).
* **C100/C170** — NF-e/NFC-e do mês (cabeçalho + itens granular).
* **A100/A170** — NFS-e do mês (cabeçalho + itens granular).
* **M200/M600** — snapshot da apuração PIS/Cofins do escritório antigo.

Documentos viram ``DocumentoFiscalImportado`` + ``ItemFiscalImportado``
prontos para o ``MigracaoService`` criar ``documento_fiscal`` /
``documento_fiscal_item``. Apuração snapshot fica em
``EfdContribuicoesParseado.apuracao_snapshot`` para
``lote.resumo_jsonb``.

Princípios: §8.4 (round-trip golden), §8.6 (validação CNPJ + 9999),
§8.8 (parser puro).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.modules.sped.compartilhado import (
    calcular_hash_sha256,
    parse_data,
    parse_decimal,
)

from app.modules.migracao.parser_ecd import _campo, _decompor

ALGORITMO_VERSAO = "migracao.efd_contribuicoes.v2"
# Sprint 19.7 PR3 #36 — emite ``cnpj_participante`` por documento via
# lookup do registro 0150 (COD_PART → CNPJ/CPF). v1 deixava o emitente
# como placeholder; agora cada NF importada carrega o CNPJ real.


class EfdContribuicoesInvalida(ValueError):
    """EFD-Contribuições malformada — não pode ser importada."""


# ── DTOs ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdentificacaoEfdParseada:
    cnpj: str
    razao_social: str
    uf: str
    codigo_municipio_ibge: str
    competencia_inicio: date
    competencia_fim: date
    leiaute_versao: str


@dataclass(frozen=True, slots=True)
class ItemFiscalImportado:
    """Linha C170/A170 — granularidade por item resolvendo pendência #26."""

    n_item: int
    codigo_produto: str | None
    descricao: str
    quantidade: Decimal
    unidade: str | None
    valor_total: Decimal
    cfop: str | None
    cst_icms: str | None
    cst_pis: str | None
    cst_cofins: str | None
    valor_icms: Decimal | None
    valor_pis: Decimal | None
    valor_cofins: Decimal | None


@dataclass(frozen=True, slots=True)
class DocumentoFiscalImportado:
    """Cabeçalho C100/A100 — vira ``documento_fiscal``.

    Sprint 19.7 PR3 (#36) — novo campo ``cnpj_participante``: CNPJ do
    participante referenciado em ``COD_PART`` (campo 4 do C100/A100),
    resolvido via lookup no registro 0150 do mesmo arquivo. Quando
    ``direcao='entrada'``, esse é o **CNPJ do emitente da NF** (o
    fornecedor); quando ``direcao='saida'``, é o destinatário (o
    cliente — útil pra conferência futura). ``None`` se o participante
    está só com CPF ou se o 0150 não casou.
    """

    tipo: str  # 'nfe' | 'nfce' | 'nfse'
    direcao: str  # 'saida' | 'entrada'
    chave: str | None  # 44 (NFe) ou 50 (NFSe) dígitos
    numero: str
    serie: str
    emitida_em: date
    valor_total: Decimal
    valor_mercadorias: Decimal | None
    valor_pis: Decimal | None
    valor_cofins: Decimal | None
    cfop: str | None
    cancelado: bool
    itens: tuple[ItemFiscalImportado, ...]
    # Sprint 19.7 PR3 #36 — emitente via 0150 (default mantém compat).
    cnpj_participante: str | None = None
    cpf_participante: str | None = None


@dataclass(frozen=True, slots=True)
class EfdContribuicoesParseado:
    identificacao: IdentificacaoEfdParseada
    documentos: tuple[DocumentoFiscalImportado, ...]
    apuracao_snapshot: dict[str, str] = field(default_factory=dict)
    blocos_brutos: dict[str, int] = field(default_factory=dict)
    total_linhas: int = 0
    hash_arquivo: str = ""
    algoritmo_versao: str = ALGORITMO_VERSAO


# ── Extração ────────────────────────────────────────────────────────────────


def _extrair_identificacao(
    linhas: list[list[str]],
) -> IdentificacaoEfdParseada:
    for ln in linhas:
        if ln[0] != "0000":
            continue
        # 0000: |REG|COD_VER|TIPO_ESCRIT|COD_FIN|DT_INI|DT_FIN|NOME|CNPJ|UF|COD_MUN|IE|IND_NAT_PJ|IND_ATIV|
        return IdentificacaoEfdParseada(
            leiaute_versao=_campo(ln, 2),
            competencia_inicio=parse_data(_campo(ln, 5)),
            competencia_fim=parse_data(_campo(ln, 6)),
            razao_social=_campo(ln, 7),
            cnpj=_campo(ln, 8),
            uf=_campo(ln, 9),
            codigo_municipio_ibge=_campo(ln, 10),
        )
    raise EfdContribuicoesInvalida(
        "Registro 0000 ausente — não é EFD-Contribuições válida"
    )


def _direcao_pelo_ind(ind_oper: str) -> str:
    """Leiaute EFD: ``"0"`` = entrada, ``"1"`` = saída."""
    return "entrada" if ind_oper == "0" else "saida"


def _parse_item_c170(ln: list[str]) -> ItemFiscalImportado:
    """C170: NUM_ITEM|COD_ITEM|DESCR|QTD|UNID|VL_ITEM|VL_DESC|IND_MOV|
    CST_ICMS|CFOP|COD_NAT|VL_BC_ICMS|ALIQ_ICMS|VL_ICMS|...|
    CST_PIS(25)|VL_BC_PIS(26)|...|VL_PIS(30)|CST_COFINS(31)|VL_BC_COFINS(32)|...|VL_COFINS(36)|...
    """
    try:
        n_item = int(_campo(ln, 2))
    except ValueError as exc:
        raise EfdContribuicoesInvalida(
            f"C170 com NUM_ITEM inválido: {_campo(ln, 2)!r}"
        ) from exc
    return ItemFiscalImportado(
        n_item=n_item,
        codigo_produto=_campo(ln, 3) or None,
        descricao=_campo(ln, 4) or "(sem descrição)",
        quantidade=parse_decimal(_campo(ln, 5) or "1"),
        unidade=_campo(ln, 6) or None,
        valor_total=parse_decimal(_campo(ln, 7) or "0"),
        cst_icms=_campo(ln, 10) or None,
        cfop=_campo(ln, 11) or None,
        valor_icms=_decimal_opt(_campo(ln, 15)),
        cst_pis=_campo(ln, 25) or None,
        valor_pis=_decimal_opt(_campo(ln, 30)),
        cst_cofins=_campo(ln, 31) or None,
        valor_cofins=_decimal_opt(_campo(ln, 36)),
    )


def _parse_item_a170(ln: list[str]) -> ItemFiscalImportado:
    """A170: NUM_ITEM|COD_ITEM|DESCR|VL_ITEM|VL_DESC|NAT_BC_CRED|IND_ORIG_CRED|
    CST_PIS|VL_BC_PIS|ALIQ_PIS|VL_PIS|CST_COFINS|VL_BC_COFINS|ALIQ_COFINS|VL_COFINS|COD_CTA|
    """
    try:
        n_item = int(_campo(ln, 2))
    except ValueError as exc:
        raise EfdContribuicoesInvalida(
            f"A170 com NUM_ITEM inválido: {_campo(ln, 2)!r}"
        ) from exc
    return ItemFiscalImportado(
        n_item=n_item,
        codigo_produto=_campo(ln, 3) or None,
        descricao=_campo(ln, 4) or "(sem descrição)",
        quantidade=Decimal("1"),  # NFS-e não tem quantidade por item
        unidade=None,
        valor_total=parse_decimal(_campo(ln, 5) or "0"),
        cfop=None,
        cst_icms=None,
        valor_icms=None,
        cst_pis=_campo(ln, 9) or None,
        valor_pis=_decimal_opt(_campo(ln, 12)),
        cst_cofins=_campo(ln, 13) or None,
        valor_cofins=_decimal_opt(_campo(ln, 16)),
    )


def _decimal_opt(raw: str) -> Decimal | None:
    """``parse_decimal`` que devolve ``None`` para campo vazio."""
    if not raw.strip():
        return None
    return parse_decimal(raw)


def _extrair_mapa_participantes(
    linhas: list[list[str]],
) -> dict[str, tuple[str | None, str | None]]:
    """Constrói dict ``COD_PART → (CNPJ, CPF)`` a partir dos registros 0150.

    Sprint 19.7 PR3 (#36). Layout 0150:
      ``|0150|COD_PART|NOME|COD_PAIS|CNPJ|CPF|IE|COD_MUN|SUFRAMA|...|``
    Valores vazios viram ``None`` no resultado pra não confundir lookup.
    """
    # _campo é 1-indexado contando o REG na pos 1 → COD_PART=2, CNPJ=5, CPF=6.
    mapa: dict[str, tuple[str | None, str | None]] = {}
    for ln in linhas:
        if ln[0] != "0150":
            continue
        cod = _campo(ln, 2)
        if not cod:
            continue
        cnpj = _campo(ln, 5) or None
        cpf = _campo(ln, 6) or None
        mapa[cod] = (cnpj, cpf)
    return mapa


def _extrair_documentos(
    linhas: list[list[str]],
) -> tuple[DocumentoFiscalImportado, ...]:
    """Itera C100→C170* e A100→A170* casando itens com seus cabeçalhos.

    Sprint 19.7 PR3 (#36): resolve ``cnpj_participante`` por documento
    via mapa COD_PART → CNPJ extraído dos 0150 do mesmo arquivo.
    """
    mapa_part = _extrair_mapa_participantes(linhas)
    documentos: list[DocumentoFiscalImportado] = []
    cabecalho: dict[str, object] | None = None
    itens_atual: list[ItemFiscalImportado] = []

    def fechar() -> None:
        if cabecalho is None:
            return
        cod_part = str(cabecalho.get("cod_part") or "")
        cnpj_p, cpf_p = mapa_part.get(cod_part, (None, None))
        documentos.append(
            DocumentoFiscalImportado(
                tipo=str(cabecalho["tipo"]),
                direcao=str(cabecalho["direcao"]),
                chave=cabecalho["chave"],  # type: ignore[arg-type]
                numero=str(cabecalho["numero"]),
                serie=str(cabecalho["serie"]),
                emitida_em=cabecalho["emitida_em"],  # type: ignore[arg-type]
                valor_total=cabecalho["valor_total"],  # type: ignore[arg-type]
                valor_mercadorias=cabecalho["valor_mercadorias"],  # type: ignore[arg-type]
                valor_pis=cabecalho["valor_pis"],  # type: ignore[arg-type]
                valor_cofins=cabecalho["valor_cofins"],  # type: ignore[arg-type]
                cfop=cabecalho["cfop"],  # type: ignore[arg-type]
                cancelado=bool(cabecalho["cancelado"]),
                itens=tuple(itens_atual),
                cnpj_participante=cnpj_p,
                cpf_participante=cpf_p,
            )
        )

    for ln in linhas:
        reg = ln[0]
        if reg == "C100":
            fechar()
            # |C100|IND_OPER|IND_EMIT|COD_PART|COD_MOD|COD_SIT|SER|NUM_DOC|CHV_NFE|DT_DOC|DT_E_S|VL_DOC|
            # ...|VL_MERC(16)|
            modelo = _campo(ln, 5)
            cod_sit = _campo(ln, 6)
            tipo = "nfce" if modelo == "65" else "nfe"
            cabecalho = {
                "tipo": tipo,
                "direcao": _direcao_pelo_ind(_campo(ln, 2)),
                "chave": _campo(ln, 9) or None,
                "numero": _campo(ln, 8),
                "serie": _campo(ln, 7),
                "emitida_em": parse_data(_campo(ln, 10)),
                "valor_total": parse_decimal(_campo(ln, 12) or "0"),
                "valor_mercadorias": _decimal_opt(_campo(ln, 16)),
                "valor_pis": _decimal_opt(_campo(ln, 26)),
                "valor_cofins": _decimal_opt(_campo(ln, 27)),
                "cfop": None,  # CFOP só aparece no C170 (item-level)
                "cancelado": cod_sit == "02",
                "cod_part": _campo(ln, 4),  # PR3 #36
            }
            itens_atual = []
        elif reg == "C170":
            if cabecalho is None:
                raise EfdContribuicoesInvalida("C170 sem C100 antecedente")
            item = _parse_item_c170(ln)
            itens_atual.append(item)
            if cabecalho["cfop"] is None and item.cfop is not None:
                # Promove primeiro CFOP de item ao cabeçalho (compat doc_fiscal).
                cabecalho["cfop"] = item.cfop
        elif reg == "A100":
            fechar()
            # |A100|IND_OPER|IND_EMIT|COD_PART|"99"|""|SER(7)|""|NUM(9)|CHV(10)|DT_DOC(11)|DT_EXE(12)|VL_DOC(13)|COD_SIT(14)|
            # ...|VL_BC_PIS(16)|VL_PIS(17)|VL_BC_COFINS(18)|VL_COFINS(19)|
            cod_sit = _campo(ln, 14)
            cabecalho = {
                "tipo": "nfse",
                "direcao": _direcao_pelo_ind(_campo(ln, 2)),
                "chave": _campo(ln, 10) or None,
                "numero": _campo(ln, 9),
                "serie": _campo(ln, 7),
                "emitida_em": parse_data(_campo(ln, 11)),
                "valor_total": parse_decimal(_campo(ln, 13) or "0"),
                "valor_mercadorias": None,
                "valor_pis": _decimal_opt(_campo(ln, 17)),
                "valor_cofins": _decimal_opt(_campo(ln, 19)),
                "cfop": None,
                "cancelado": cod_sit == "02",
                "cod_part": _campo(ln, 4),  # PR3 #36
            }
            itens_atual = []
        elif reg == "A170":
            if cabecalho is None:
                raise EfdContribuicoesInvalida("A170 sem A100 antecedente")
            itens_atual.append(_parse_item_a170(ln))
    fechar()
    return tuple(documentos)


def _extrair_apuracao_snapshot(linhas: list[list[str]]) -> dict[str, str]:
    """M200/M600 → snapshot dict (Decimal → str para JSON determinístico)."""
    snapshot: dict[str, str] = {}
    for ln in linhas:
        if ln[0] == "M200":
            # M200: VL_TOT_CONT_NC_PER|VL_TOT_CRED_DESC|...|VL_TOT_CONT_REC_PER(14)|...
            snapshot["pis_apurado_periodo"] = _campo(ln, 2)
        elif ln[0] == "M600":
            snapshot["cofins_apurado_periodo"] = _campo(ln, 2)
    return snapshot


def _contar_blocos(linhas: list[list[str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for ln in linhas:
        out[ln[0]] = out.get(ln[0], 0) + 1
    return out


def _validar_amarracoes(
    identificacao: IdentificacaoEfdParseada,
    linhas: list[list[str]],
    total_linhas: int,
) -> None:
    if len(identificacao.cnpj) != 14 or not identificacao.cnpj.isdigit():
        raise EfdContribuicoesInvalida(
            f"CNPJ 0000 inválido: {identificacao.cnpj!r}"
        )
    for ln in linhas:
        if ln[0] == "9999":
            declarado_raw = _campo(ln, 2)
            try:
                declarado = int(declarado_raw)
            except ValueError as exc:
                raise EfdContribuicoesInvalida(
                    f"9999 com QTD_LIN inválido: {declarado_raw!r}"
                ) from exc
            if declarado != total_linhas:
                raise EfdContribuicoesInvalida(
                    f"9999 declarado={declarado} ≠ total real={total_linhas}"
                )
            return
    raise EfdContribuicoesInvalida("Registro 9999 ausente — arquivo incompleto")


def parse_efd_contribuicoes(conteudo: bytes) -> EfdContribuicoesParseado:
    """Faz o parse de um arquivo EFD-Contribuições mensal.

    Raises:
        EfdContribuicoesInvalida: para qualquer falha estrutural ou amarração.
    """
    if not conteudo:
        raise EfdContribuicoesInvalida("Arquivo vazio")
    linhas = _decompor(conteudo)
    if not linhas:
        raise EfdContribuicoesInvalida("Arquivo sem nenhuma linha SPED válida")

    identificacao = _extrair_identificacao(linhas)
    documentos = _extrair_documentos(linhas)
    _validar_amarracoes(identificacao, linhas, len(linhas))

    return EfdContribuicoesParseado(
        identificacao=identificacao,
        documentos=documentos,
        apuracao_snapshot=_extrair_apuracao_snapshot(linhas),
        blocos_brutos=_contar_blocos(linhas),
        total_linhas=len(linhas),
        hash_arquivo=calcular_hash_sha256(conteudo),
    )


__all__: Sequence[str] = (
    "ALGORITMO_VERSAO",
    "DocumentoFiscalImportado",
    "EfdContribuicoesInvalida",
    "EfdContribuicoesParseado",
    "IdentificacaoEfdParseada",
    "ItemFiscalImportado",
    "parse_efd_contribuicoes",
)
