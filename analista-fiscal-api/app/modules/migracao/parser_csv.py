"""Parser CSV — balancete + razão (Sprint 18 PR3).

Fallback para escritórios que **não têm SPED**. Aceita 2 formatos com
cabeçalho explícito e valida cada linha via Pydantic v2.

**Balancete** (snapshot read-only):
``codigo_conta;descricao;saldo_inicial;debito;credito;saldo_final``
→ ``BalanceteParseado`` (não reconstrói lançamentos — só audit em
``lote.resumo_jsonb`` para o front comparar com nosso recálculo).

**Razão** (lançamentos completos):
``data;conta_debito;conta_credito;historico;valor``
→ tupla de ``RazaoLancamentoParseado`` que o ``MigracaoService`` converte
em ``LancamentoCandidato`` com `origem_tipo='importacao'`.

Encoding aceito: UTF-8 ou Latin-1 (Excel BR exporta latin-1 com BOM).
Separador padrão ``;`` (Excel BR). Decimal aceita vírgula ou ponto.

Princípios: §8.4 (golden), §8.6 (Pydantic valida cada linha),
§8.8 (parser puro).
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.sped.compartilhado import calcular_hash_sha256

ALGORITMO_VERSAO = "migracao.csv.v2"
# Sprint 19.7 PR4 (#39) — bump v1→v2: razão aceita ``valor < 0`` como
# estorno (inverte conta_debito ↔ conta_credito + valor absoluto), em
# vez de rejeitar como "valor deve ser positivo". ``valor == 0`` continua
# rejeitado (fato vazio).

_CHAVE_NFE_RE = re.compile(r"\d{44}")
_DATA_BR_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_DATA_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


class CsvInvalido(ValueError):
    """CSV malformado ou linha não conforme — não pode ser importado."""


# ── Helpers de parsing ─────────────────────────────────────────────────────


def _decode(conteudo: bytes) -> str:
    """Tenta UTF-8 (com BOM), depois latin-1."""
    if conteudo.startswith(b"\xef\xbb\xbf"):
        return conteudo[3:].decode("utf-8", errors="replace")
    try:
        return conteudo.decode("utf-8")
    except UnicodeDecodeError:
        return conteudo.decode("latin-1", errors="replace")


def _parse_decimal_br(raw: str) -> Decimal:
    """Aceita ``"1234,56"`` ou ``"1234.56"`` — formato Excel BR ou US."""
    s = raw.strip()
    if not s:
        raise InvalidOperation("vazio")
    # Heurística: se tem vírgula, é Excel BR — troca para ponto.
    s = s.replace(".", "") if "," in s and "." in s else s
    s = s.replace(",", ".")
    return Decimal(s)


def _parse_data_br(raw: str) -> date:
    """Aceita ``"15/03/2025"`` ou ``"2025-03-15"``."""
    s = raw.strip()
    if not s:
        raise CsvInvalido("data vazia")
    if m := _DATA_BR_RE.match(s):
        d, mes, a = m.groups()
        return date(int(a), int(mes), int(d))
    if m := _DATA_ISO_RE.match(s):
        a, mes, d = m.groups()
        return date(int(a), int(mes), int(d))
    raise CsvInvalido(f"data inválida (esperado DD/MM/AAAA ou AAAA-MM-DD): {raw!r}")


def _detectar_dialeto(texto: str) -> type[csv.Dialect]:
    """Sniffer com fallback para ``;`` (Excel BR padrão).

    Retorna ``type[csv.Dialect]`` (não instância) para alinhar com a API do
    ``csv.DictReader`` — `dialect=` aceita classe ou nome registrado.
    """
    sample = texto[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        class _Padrao(csv.Dialect):
            delimiter = ";"
            quotechar = '"'
            doublequote = True
            skipinitialspace = True
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL
        return _Padrao


# ── Balancete (snapshot) ────────────────────────────────────────────────────


class _LinhaBalanceteIn(BaseModel):
    """Schema de validação por linha do balancete."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    codigo_conta: str = Field(min_length=1, max_length=20)
    descricao: str = Field(min_length=1, max_length=255)
    saldo_inicial: Decimal
    debito: Decimal
    credito: Decimal
    saldo_final: Decimal

    @field_validator(
        "saldo_inicial", "debito", "credito", "saldo_final", mode="before"
    )
    @classmethod
    def _decimal_br(cls, v: object) -> Decimal:
        if isinstance(v, Decimal):
            return v
        if isinstance(v, str):
            return _parse_decimal_br(v)
        raise ValueError(f"valor inesperado: {v!r}")


@dataclass(frozen=True, slots=True)
class LinhaBalanceteParseada:
    codigo_conta: str
    descricao: str
    saldo_inicial: Decimal
    debito: Decimal
    credito: Decimal
    saldo_final: Decimal


@dataclass(frozen=True, slots=True)
class BalanceteParseado:
    linhas: tuple[LinhaBalanceteParseada, ...]
    total_debitos: Decimal
    total_creditos: Decimal
    hash_arquivo: str
    algoritmo_versao: str = ALGORITMO_VERSAO


def parse_balancete_csv(conteudo: bytes) -> BalanceteParseado:
    """Parseia balancete CSV — snapshot de saldos por conta.

    Cabeçalho obrigatório (case-insensitive, ordem livre):
    ``codigo_conta``, ``descricao``, ``saldo_inicial``, ``debito``,
    ``credito``, ``saldo_final``.

    Raises:
        CsvInvalido: cabeçalho ausente, linha com formato errado, ou vazio.
    """
    if not conteudo:
        raise CsvInvalido("Arquivo vazio")
    texto = _decode(conteudo)
    dialeto = _detectar_dialeto(texto)
    reader = csv.DictReader(io.StringIO(texto), dialect=dialeto)
    obrigatorias = {
        "codigo_conta", "descricao", "saldo_inicial",
        "debito", "credito", "saldo_final",
    }
    if reader.fieldnames is None:
        raise CsvInvalido("CSV sem cabeçalho")
    nomes = {(c or "").strip().lower() for c in reader.fieldnames}
    faltando = obrigatorias - nomes
    if faltando:
        raise CsvInvalido(
            f"Cabeçalho balancete sem colunas obrigatórias: {sorted(faltando)}"
        )

    linhas: list[LinhaBalanceteParseada] = []
    total_d = Decimal("0")
    total_c = Decimal("0")
    for n, raw in enumerate(reader, start=2):  # n=2 inclui cabeçalho
        # Normaliza chaves para lowercase.
        norm = {(k or "").strip().lower(): v for k, v in raw.items()}
        try:
            validado = _LinhaBalanceteIn(**norm)
        except Exception as exc:
            raise CsvInvalido(f"Linha {n} inválida: {exc}") from exc
        linhas.append(
            LinhaBalanceteParseada(
                codigo_conta=validado.codigo_conta,
                descricao=validado.descricao,
                saldo_inicial=validado.saldo_inicial,
                debito=validado.debito,
                credito=validado.credito,
                saldo_final=validado.saldo_final,
            )
        )
        total_d += validado.debito
        total_c += validado.credito

    if not linhas:
        raise CsvInvalido("Balancete sem linhas após o cabeçalho")

    return BalanceteParseado(
        linhas=tuple(linhas),
        total_debitos=total_d,
        total_creditos=total_c,
        hash_arquivo=calcular_hash_sha256(conteudo),
    )


# ── Razão (lançamentos) ─────────────────────────────────────────────────────


class _LinhaRazaoIn(BaseModel):
    """Schema de validação por linha do razão."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    data: date
    conta_debito: str = Field(min_length=1, max_length=20)
    conta_credito: str = Field(min_length=1, max_length=20)
    historico: str = Field(min_length=1, max_length=500)
    valor: Decimal

    @field_validator("data", mode="before")
    @classmethod
    def _data_br(cls, v: object) -> date:
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            return _parse_data_br(v)
        raise ValueError(f"data inesperada: {v!r}")

    @field_validator("valor", mode="before")
    @classmethod
    def _valor_br(cls, v: object) -> Decimal:
        if isinstance(v, Decimal):
            return v
        if isinstance(v, str):
            return _parse_decimal_br(v)
        raise ValueError(f"valor inesperado: {v!r}")


@dataclass(frozen=True, slots=True)
class RazaoLancamentoParseado:
    """Linha de razão CSV — vira ``LancamentoCandidato`` no service.

    Sprint 19.7 PR4 (#39) — quando o CSV original trazia ``valor`` negativo
    (estorno: cancelamento/devolução), o parser **inverte** ``conta_debito``
    e ``conta_credito`` automaticamente, toma valor absoluto e marca
    ``estorno=True``. Quem consome o DTO trata estorno como lançamento
    normal — a inversão já foi materializada na própria linha.
    """

    data: date
    conta_debito: str
    conta_credito: str
    historico: str
    valor: Decimal
    chave_nfe_referenciada: str | None = None  # extraída do histórico (44 dígitos)
    estorno: bool = False


@dataclass(frozen=True, slots=True)
class RazaoParseado:
    lancamentos: tuple[RazaoLancamentoParseado, ...]
    total_valor: Decimal
    hash_arquivo: str
    algoritmo_versao: str = ALGORITMO_VERSAO


def parse_razao_csv(conteudo: bytes) -> RazaoParseado:
    """Parseia razão CSV — lançamentos contábeis completos.

    Cabeçalho obrigatório (case-insensitive, ordem livre):
    ``data``, ``conta_debito``, ``conta_credito``, ``historico``, ``valor``.

    Detecta chave NF-e (44 dígitos consecutivos) no ``historico`` para
    posterior cross-check com ``documento_fiscal``.

    Raises:
        CsvInvalido: cabeçalho ausente, formato errado, valor ≤ 0.
    """
    if not conteudo:
        raise CsvInvalido("Arquivo vazio")
    texto = _decode(conteudo)
    dialeto = _detectar_dialeto(texto)
    reader = csv.DictReader(io.StringIO(texto), dialect=dialeto)
    obrigatorias = {"data", "conta_debito", "conta_credito", "historico", "valor"}
    if reader.fieldnames is None:
        raise CsvInvalido("CSV sem cabeçalho")
    nomes = {(c or "").strip().lower() for c in reader.fieldnames}
    faltando = obrigatorias - nomes
    if faltando:
        raise CsvInvalido(
            f"Cabeçalho razão sem colunas obrigatórias: {sorted(faltando)}"
        )

    lancs: list[RazaoLancamentoParseado] = []
    total = Decimal("0")
    for n, raw in enumerate(reader, start=2):
        norm = {(k or "").strip().lower(): v for k, v in raw.items()}
        try:
            validado = _LinhaRazaoIn(**norm)
        except Exception as exc:
            raise CsvInvalido(f"Linha {n} inválida: {exc}") from exc
        if validado.valor == 0:
            raise CsvInvalido(
                f"Linha {n}: valor não pode ser zero (fato contábil vazio)"
            )
        # Sprint 19.7 PR4 (#39) — valor negativo é estorno: inverte D/C
        # e materializa absoluto. Quem consome trata como lançamento normal.
        estorno = validado.valor < 0
        if estorno:
            conta_d = validado.conta_credito
            conta_c = validado.conta_debito
            valor = -validado.valor  # absoluto
        else:
            conta_d = validado.conta_debito
            conta_c = validado.conta_credito
            valor = validado.valor
        chave_match = _CHAVE_NFE_RE.search(validado.historico)
        lancs.append(
            RazaoLancamentoParseado(
                data=validado.data,
                conta_debito=conta_d,
                conta_credito=conta_c,
                historico=validado.historico,
                valor=valor,
                chave_nfe_referenciada=chave_match.group(0) if chave_match else None,
                estorno=estorno,
            )
        )
        total += valor

    if not lancs:
        raise CsvInvalido("Razão sem lançamentos após o cabeçalho")

    return RazaoParseado(
        lancamentos=tuple(lancs),
        total_valor=total,
        hash_arquivo=calcular_hash_sha256(conteudo),
    )


__all__: Sequence[str] = (
    "ALGORITMO_VERSAO",
    "BalanceteParseado",
    "CsvInvalido",
    "LinhaBalanceteParseada",
    "RazaoLancamentoParseado",
    "RazaoParseado",
    "parse_balancete_csv",
    "parse_razao_csv",
)
