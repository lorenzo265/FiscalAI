"""Parser SPED ECF — Escrituração Contábil Fiscal anual LP (Sprint 18 PR2).

**Snapshot read-only**. Diferente da ECD (cujos lançamentos contábeis viram
``LancamentoCandidato`` e entram no nosso motor), a ECF é **declarativa**:
contém apurações IRPJ/CSLL trimestrais que já foram **calculadas** pelo
escritório anterior. Não as recriamos.

O que extraímos vira ``EcfParseado`` com:

* Identificação (CNPJ + período + forma de tributação) → para audit cruzado
  com ``Empresa`` no DB (rejeitar se CNPJ diverge).
* Apurações P200 (IRPJ) / P300 (CSLL) por trimestre → snapshot persistido em
  ``lote_importacao.resumo_jsonb`` para o front exibir comparativo
  "**declarado pelo escritório antigo × recalculado por nós**" depois
  que rodarmos nossas próprias apurações em cima dos lançamentos
  contábeis importados via ECD.

Princípios aplicados: §8.4 (golden round-trip ECF gerada → parseada),
§8.6 (validação CNPJ + período coerente), §8.8 (parser puro).
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

ALGORITMO_VERSAO = "migracao.ecf.v1"


# ── Erros ───────────────────────────────────────────────────────────────────


class EcfInvalido(ValueError):
    """ECF malformada — não pode ser importada."""


# ── DTOs ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdentificacaoEcfParseada:
    cnpj: str
    razao_social: str
    inicio_exercicio: date
    fim_exercicio: date
    forma_tributacao: str  # '1'..'8'
    leiaute_versao: str


@dataclass(frozen=True, slots=True)
class ApuracaoTrimestralSnapshot:
    """Snapshot da apuração trimestral declarada pelo escritório antigo."""

    inicio: date
    fim: date
    # IRPJ (P100/P200) — quando ausente, fica em zero.
    receita_bruta: Decimal
    base_presumida_irpj: Decimal
    base_total_irpj: Decimal
    irpj_normal: Decimal
    irpj_adicional: Decimal
    irpj_total: Decimal
    irpj_devido: Decimal
    # CSLL (P300).
    base_total_csll: Decimal
    csll_devida: Decimal


@dataclass(frozen=True, slots=True)
class EcfParseado:
    """Resultado do parse — pronto para o ``MigracaoService`` registrar audit."""

    identificacao: IdentificacaoEcfParseada
    apuracoes_trimestrais: tuple[ApuracaoTrimestralSnapshot, ...]
    # Blocos brutos para diagnóstico avançado (não usado pelo serviço, só audit).
    blocos_brutos: dict[str, int] = field(default_factory=dict)
    total_linhas: int = 0
    hash_arquivo: str = ""
    algoritmo_versao: str = ALGORITMO_VERSAO


# ── Extração ────────────────────────────────────────────────────────────────


def _extrair_identificacao(linhas: list[list[str]]) -> IdentificacaoEcfParseada:
    for ln in linhas:
        if ln[0] != "0000":
            continue
        # 0000: |0000|COD_VER|LEIAUTE|CNPJ|NOME|IND_SIT_ESP|SIT_ESP_VERSAO_ANT|
        #       PAT_REM_INI|DT_INI|DT_FIN|IND_FIN_ESC|NUM_REC_ANTERIOR|TIP_ECF|
        #       COD_SCP|IND_GR_PER|FORMA_TRIB|FORMA_APUR|
        return IdentificacaoEcfParseada(
            leiaute_versao=_campo(ln, 3),
            cnpj=_campo(ln, 4),
            razao_social=_campo(ln, 5),
            inicio_exercicio=parse_data(_campo(ln, 9)),
            fim_exercicio=parse_data(_campo(ln, 10)),
            forma_tributacao=_campo(ln, 16),
        )
    raise EcfInvalido("Registro 0000 ausente — não é um SPED ECF válido")


def _extrair_apuracoes(
    linhas: list[list[str]],
) -> tuple[ApuracaoTrimestralSnapshot, ...]:
    """Casa P010 (período) com P100/P200/P300 da mesma iteração trimestral."""
    apuracoes: list[ApuracaoTrimestralSnapshot] = []
    inicio: date | None = None
    fim: date | None = None
    # Campos do P100/P200/P300 do trimestre corrente.
    receita_bruta = Decimal("0")
    base_presumida_irpj = Decimal("0")
    base_total_irpj = Decimal("0")
    irpj_normal = Decimal("0")
    irpj_adicional = Decimal("0")
    irpj_total = Decimal("0")
    irpj_devido = Decimal("0")
    base_total_csll = Decimal("0")
    csll_devida = Decimal("0")

    def fechar() -> None:
        nonlocal receita_bruta, base_presumida_irpj, base_total_irpj
        nonlocal irpj_normal, irpj_adicional, irpj_total, irpj_devido
        nonlocal base_total_csll, csll_devida
        if inicio is None or fim is None:
            return
        apuracoes.append(
            ApuracaoTrimestralSnapshot(
                inicio=inicio,
                fim=fim,
                receita_bruta=receita_bruta,
                base_presumida_irpj=base_presumida_irpj,
                base_total_irpj=base_total_irpj,
                irpj_normal=irpj_normal,
                irpj_adicional=irpj_adicional,
                irpj_total=irpj_total,
                irpj_devido=irpj_devido,
                base_total_csll=base_total_csll,
                csll_devida=csll_devida,
            )
        )
        # Reset para o próximo P010.
        receita_bruta = Decimal("0")
        base_presumida_irpj = Decimal("0")
        base_total_irpj = Decimal("0")
        irpj_normal = Decimal("0")
        irpj_adicional = Decimal("0")
        irpj_total = Decimal("0")
        irpj_devido = Decimal("0")
        base_total_csll = Decimal("0")
        csll_devida = Decimal("0")

    for ln in linhas:
        reg = ln[0]
        if reg == "P010":
            fechar()
            inicio = parse_data(_campo(ln, 2))
            fim = parse_data(_campo(ln, 3))
        elif reg == "P100":
            # P100: |P100|REC_BRU|PERC_PRES_IRPJ|BASE_PRES_IRPJ|GANHO_CAP|
            #       RECEITA_APLIC|OUTRAS_ADIC|BASE_TOTAL|
            receita_bruta = parse_decimal(_campo(ln, 2))
            base_presumida_irpj = parse_decimal(_campo(ln, 4))
            base_total_irpj = parse_decimal(_campo(ln, 8))
        elif reg == "P200":
            # P200: |P200|BASE_TOTAL|LIM_ADIC|IRPJ_NORMAL|IRPJ_ADIC|IRPJ_TOTAL|
            #       IRRF_CONSUM|IRPJ_DEVIDO|
            irpj_normal = parse_decimal(_campo(ln, 4))
            irpj_adicional = parse_decimal(_campo(ln, 5))
            irpj_total = parse_decimal(_campo(ln, 6))
            irpj_devido = parse_decimal(_campo(ln, 8))
        elif reg == "P300":
            # P300: |P300|REC_BRU|PERC_PRES|BASE_PRES|OUTRAS_ADIC|BASE_TOTAL|CSLL_DEVIDA|
            base_total_csll = parse_decimal(_campo(ln, 6))
            csll_devida = parse_decimal(_campo(ln, 7))
    fechar()
    return tuple(apuracoes)


def _contar_blocos(linhas: list[list[str]]) -> dict[str, int]:
    """Conta registros por REG — diagnóstico de cobertura do parser."""
    counter: dict[str, int] = {}
    for ln in linhas:
        reg = ln[0]
        counter[reg] = counter.get(reg, 0) + 1
    return counter


def _validar_amarracoes(
    identificacao: IdentificacaoEcfParseada,
    linhas: list[list[str]],
    total_linhas: int,
) -> None:
    if len(identificacao.cnpj) != 14 or not identificacao.cnpj.isdigit():
        raise EcfInvalido(
            f"CNPJ 0000 inválido: {identificacao.cnpj!r} (esperado 14 dígitos)"
        )
    if identificacao.fim_exercicio < identificacao.inicio_exercicio:
        raise EcfInvalido("0000 com fim_exercicio < inicio_exercicio")

    for ln in linhas:
        if ln[0] == "9999":
            declarado_raw = _campo(ln, 2)
            try:
                declarado = int(declarado_raw)
            except ValueError as exc:
                raise EcfInvalido(
                    f"9999 com QTD_LIN inválido: {declarado_raw!r}"
                ) from exc
            if declarado != total_linhas:
                raise EcfInvalido(
                    f"9999 declarado={declarado} ≠ total real={total_linhas}"
                )
            return
    raise EcfInvalido("Registro 9999 ausente — arquivo incompleto")


# ── API pública ─────────────────────────────────────────────────────────────


def parse_ecf(conteudo: bytes) -> EcfParseado:
    """Faz o parse de um arquivo SPED ECF (snapshot read-only).

    Raises:
        EcfInvalido: para qualquer falha estrutural ou de amarração.
    """
    if not conteudo:
        raise EcfInvalido("Arquivo vazio")

    linhas = _decompor(conteudo)
    if not linhas:
        raise EcfInvalido("Arquivo sem nenhuma linha SPED válida")

    identificacao = _extrair_identificacao(linhas)
    apuracoes = _extrair_apuracoes(linhas)
    _validar_amarracoes(identificacao, linhas, len(linhas))

    return EcfParseado(
        identificacao=identificacao,
        apuracoes_trimestrais=apuracoes,
        blocos_brutos=_contar_blocos(linhas),
        total_linhas=len(linhas),
        hash_arquivo=calcular_hash_sha256(conteudo),
    )


__all__: Sequence[str] = (
    "ALGORITMO_VERSAO",
    "ApuracaoTrimestralSnapshot",
    "EcfInvalido",
    "EcfParseado",
    "IdentificacaoEcfParseada",
    "parse_ecf",
)
