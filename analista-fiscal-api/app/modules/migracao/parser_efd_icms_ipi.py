"""Parser SPED EFD ICMS-IPI mensal (Sprint 18 PR3).

**Camada 1 (determinística).** Reverte o gerador
``app/modules/sped/efd/gerador_icms_ipi.py`` (Sprint 17 PR2).

Extrai do arquivo:

* **0000** — cabeçalho (CNPJ + competência + UF).
* **C100/C170** — NF-e/NFC-e (cabeçalho + itens granular com CFOP/CST/ICMS).
* **E110** — snapshot da apuração ICMS do escritório antigo
  (débitos / créditos / ICMS a recolher / saldo credor a transportar).

Reusa os DTOs do ``parser_efd_contribuicoes`` (``DocumentoFiscalImportado`` +
``ItemFiscalImportado``) — mesma forma de saída para o ``MigracaoService``
montar ``documento_fiscal`` + ``documento_fiscal_item``.

Princípios: §8.4, §8.6, §8.8.
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
from app.modules.migracao.parser_efd_contribuicoes import (
    DocumentoFiscalImportado,
    ItemFiscalImportado,
    _decimal_opt,
    _direcao_pelo_ind,
    _extrair_mapa_participantes,
)

ALGORITMO_VERSAO = "migracao.efd_icms_ipi.v2"
# Sprint 19.7 PR3 #36 — emite ``cnpj_participante`` via lookup 0150.


class EfdIcmsIpiInvalida(ValueError):
    """EFD ICMS-IPI malformada — não pode ser importada."""


# ── DTOs ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdentificacaoIcmsIpiParseada:
    cnpj: str
    razao_social: str
    uf: str
    inscricao_estadual: str
    codigo_municipio_ibge: str
    competencia_inicio: date
    competencia_fim: date
    leiaute_versao: str


@dataclass(frozen=True, slots=True)
class EfdIcmsIpiParseado:
    identificacao: IdentificacaoIcmsIpiParseada
    documentos: tuple[DocumentoFiscalImportado, ...]
    apuracao_icms_snapshot: dict[str, str] = field(default_factory=dict)
    blocos_brutos: dict[str, int] = field(default_factory=dict)
    total_linhas: int = 0
    hash_arquivo: str = ""
    algoritmo_versao: str = ALGORITMO_VERSAO


# ── Extração ────────────────────────────────────────────────────────────────


def _extrair_identificacao(
    linhas: list[list[str]],
) -> IdentificacaoIcmsIpiParseada:
    for ln in linhas:
        if ln[0] != "0000":
            continue
        # 0000 EFD ICMS-IPI: |REG|COD_VER|COD_FIN|DT_INI|DT_FIN|NOME|CNPJ|CPF|UF|IE|COD_MUN|IM|SUFRAMA|IND_ATIV|IND_PERFIL|
        return IdentificacaoIcmsIpiParseada(
            leiaute_versao=_campo(ln, 2),
            competencia_inicio=parse_data(_campo(ln, 4)),
            competencia_fim=parse_data(_campo(ln, 5)),
            razao_social=_campo(ln, 6),
            cnpj=_campo(ln, 7),
            uf=_campo(ln, 9),
            inscricao_estadual=_campo(ln, 10),
            codigo_municipio_ibge=_campo(ln, 11),
        )
    raise EfdIcmsIpiInvalida(
        "Registro 0000 ausente — não é EFD ICMS-IPI válida"
    )


def _parse_item_c170_icms(ln: list[str]) -> ItemFiscalImportado:
    """C170 do EFD ICMS-IPI — mesma estrutura que EFD-Contribuições.

    Campos relevantes para ICMS: VL_ITEM(7), CST_ICMS(10), CFOP(11),
    VL_BC_ICMS(13), ALIQ_ICMS(14), VL_ICMS(15), VL_IPI(24),
    CST_PIS(25), VL_PIS(30), CST_COFINS(31), VL_COFINS(36).
    """
    try:
        n_item = int(_campo(ln, 2))
    except ValueError as exc:
        raise EfdIcmsIpiInvalida(
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


def _extrair_documentos(
    linhas: list[list[str]],
) -> tuple[DocumentoFiscalImportado, ...]:
    """C100→C170* casando itens com cabeçalho.

    Sprint 19.7 PR3 (#36): resolve ``cnpj_participante`` por documento
    via mapa COD_PART → CNPJ extraído dos 0150 do mesmo arquivo (mesma
    rotina compartilhada com o parser EFD-Contribuições).
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
                valor_pis=None,
                valor_cofins=None,
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
                "cfop": None,
                "cancelado": cod_sit == "02",
                "cod_part": _campo(ln, 4),  # PR3 #36
            }
            itens_atual = []
        elif reg == "C170":
            if cabecalho is None:
                raise EfdIcmsIpiInvalida("C170 sem C100 antecedente")
            item = _parse_item_c170_icms(ln)
            itens_atual.append(item)
            if cabecalho["cfop"] is None and item.cfop is not None:
                cabecalho["cfop"] = item.cfop
    fechar()
    return tuple(documentos)


def _extrair_apuracao_icms(linhas: list[list[str]]) -> dict[str, str]:
    """E110 → snapshot dict para audit cross-cliente."""
    snapshot: dict[str, str] = {}
    for ln in linhas:
        if ln[0] == "E110":
            # E110: VL_TOT_DEB|VL_AJ_DEB|VL_TOT_AJ_DEB|VL_ESTORNOS_CRED|
            #       VL_TOT_CRED|VL_AJ_CRED|VL_TOT_AJ_CRED|VL_ESTORNOS_DEB|
            #       VL_SLD_CREDOR_ANT|VL_SLD_APURADO|VL_TOT_DED|VL_ICMS_RECOLHER|
            #       VL_SLD_CREDOR_TRANSPORTAR|DEB_ESP|
            snapshot["icms_total_debitos"] = _campo(ln, 2)
            snapshot["icms_total_creditos"] = _campo(ln, 6)
            snapshot["icms_a_recolher"] = _campo(ln, 13)
            snapshot["icms_saldo_credor_transportar"] = _campo(ln, 14)
            break  # E110 só aparece 1× por arquivo
    return snapshot


def _contar_blocos(linhas: list[list[str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for ln in linhas:
        out[ln[0]] = out.get(ln[0], 0) + 1
    return out


def _validar_amarracoes(
    identificacao: IdentificacaoIcmsIpiParseada,
    linhas: list[list[str]],
    total_linhas: int,
) -> None:
    if len(identificacao.cnpj) != 14 or not identificacao.cnpj.isdigit():
        raise EfdIcmsIpiInvalida(
            f"CNPJ 0000 inválido: {identificacao.cnpj!r}"
        )
    for ln in linhas:
        if ln[0] == "9999":
            try:
                declarado = int(_campo(ln, 2))
            except ValueError as exc:
                raise EfdIcmsIpiInvalida(
                    f"9999 com QTD_LIN inválido: {_campo(ln, 2)!r}"
                ) from exc
            if declarado != total_linhas:
                raise EfdIcmsIpiInvalida(
                    f"9999 declarado={declarado} ≠ total real={total_linhas}"
                )
            return
    raise EfdIcmsIpiInvalida("Registro 9999 ausente — arquivo incompleto")


def parse_efd_icms_ipi(conteudo: bytes) -> EfdIcmsIpiParseado:
    """Faz o parse de um arquivo EFD ICMS-IPI mensal.

    Raises:
        EfdIcmsIpiInvalida: para qualquer falha estrutural ou amarração.
    """
    if not conteudo:
        raise EfdIcmsIpiInvalida("Arquivo vazio")
    linhas = _decompor(conteudo)
    if not linhas:
        raise EfdIcmsIpiInvalida("Arquivo sem nenhuma linha SPED válida")

    identificacao = _extrair_identificacao(linhas)
    documentos = _extrair_documentos(linhas)
    _validar_amarracoes(identificacao, linhas, len(linhas))

    return EfdIcmsIpiParseado(
        identificacao=identificacao,
        documentos=documentos,
        apuracao_icms_snapshot=_extrair_apuracao_icms(linhas),
        blocos_brutos=_contar_blocos(linhas),
        total_linhas=len(linhas),
        hash_arquivo=calcular_hash_sha256(conteudo),
    )


__all__: Sequence[str] = (
    "ALGORITMO_VERSAO",
    "EfdIcmsIpiInvalida",
    "EfdIcmsIpiParseado",
    "IdentificacaoIcmsIpiParseada",
    "parse_efd_icms_ipi",
)
