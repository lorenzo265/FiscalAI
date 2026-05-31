"""Helpers compartilhados — serialização SPED pipe-delimited (Sprint 16 PR1).

Todos os arquivos SPED (ECD, ECF, EFD-Contribuições, EFD ICMS-IPI) usam
o mesmo formato:

* Cada registro é uma linha terminada em LF (``\\n``).
* Campos separados por pipe (``|``).
* Linha começa e termina com pipe: ``|REG|c1|c2|...|cN|``.
* Decimais usam vírgula como separador (sem milhar): ``1234,56``.
* Datas em ``DDMMAAAA`` (8 dígitos, sem separador).
* Campos vazios ficam vazios entre pipes: ``||``.
* O pipe é proibido dentro do valor — quando aparecer no texto livre,
  substituímos por hífen (RFB recomenda).

O bloco final (``9``) tem o registro 9900 com a CONTAGEM REAL de
cada tipo de registro presente no arquivo (incluindo o próprio 9900
e o totalizador do 9900). 9990 fecha o bloco 9; 9999 fecha o arquivo.

Estes helpers são puros (zero I/O) e usados pelos geradores
``ecd/gerador.py``, ``ecf/gerador.py`` etc.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

_CENTAVO = Decimal("0.01")


def escapar(valor: str) -> str:
    """Remove caractere pipe do texto livre (separador interno do SPED).

    A RFB recomenda substituir por hífen quando o texto natural contiver
    pipe (raro mas possível em históricos contábeis colados de email).
    Também troca CR/LF para espaço — uma linha SPED não pode quebrar.
    """
    return valor.replace("|", "-").replace("\r", " ").replace("\n", " ")


def formatar_decimal(valor: Decimal | int | float) -> str:
    """Formata número como '1234,56' (vírgula decimal, sem separador de milhar).

    Zero vira ``"0,00"``. Negativo preserva o sinal: ``"-12,34"``.
    Arredondamento bancário (HALF_EVEN) — coerente com o resto do sistema.
    """
    if not isinstance(valor, Decimal):
        valor = Decimal(str(valor))
    q = valor.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
    return format(q, "f").replace(".", ",")


def formatar_data(d: date) -> str:
    """``date(2025, 12, 31)`` → ``"31122025"`` (DDMMAAAA, layout SPED)."""
    return d.strftime("%d%m%Y")


def formatar_periodo(d: date) -> str:
    """``date(2025, 12, 1)`` → ``"122025"`` (MMAAAA — usado em ECF Bloco 0)."""
    return d.strftime("%m%Y")


def linha(reg: str, *campos: object) -> str:
    """Monta uma linha SPED: ``|REG|c1|c2|...|cN|\\n``.

    Cada campo é serializado:

    * ``None`` → string vazia
    * ``Decimal``/``int``/``float`` → ``formatar_decimal``
    * ``date`` → ``formatar_data``
    * ``str`` → escape de pipe/CR/LF
    * ``bool`` → ``"S"``/``"N"`` (convenção SPED)
    * outros → ``str(x)``

    O newline LF (``\\n``) é incluído na string retornada.
    """
    partes: list[str] = [reg]
    for c in campos:
        partes.append(_serializar_campo(c))
    return "|" + "|".join(partes) + "|\n"


def _serializar_campo(c: object) -> str:
    if c is None:
        return ""
    if isinstance(c, bool):
        return "S" if c else "N"
    # ``int`` é contagem/sequencial no SPED — NÃO leva vírgula decimal
    # (ex.: 9999 total geral, NUM_ORD, qtd lançamentos, COD_NIVEL).
    if isinstance(c, int):
        return str(c)
    if isinstance(c, Decimal | float):
        return formatar_decimal(c)
    if isinstance(c, date):
        return formatar_data(c)
    if isinstance(c, str):
        return escapar(c)
    return escapar(str(c))


def contar_registros(linhas: Iterable[str]) -> dict[str, int]:
    """Conta quantas vezes cada REG aparece — base para o registro 9900.

    Cada linha SPED é ``|REG|...|`` — o REG é o primeiro campo. Esta
    contagem é a fonte da verdade para os registros 9900 (totalizador
    por tipo de registro) + 9999 (total geral do arquivo).
    """
    c: Counter[str] = Counter()
    for ln in linhas:
        if not ln or not ln.startswith("|"):
            continue
        # Caminho rápido: primeiro campo entre pipes.
        idx_sep = ln.find("|", 1)
        if idx_sep < 0:
            continue
        reg = ln[1:idx_sep]
        if reg:
            c[reg] += 1
    return dict(c)


def gerar_bloco_9(linhas_anteriores: Sequence[str]) -> list[str]:
    """Gera o bloco 9 (encerramento) — 9001, 9900 por tipo, 9990, 9999.

    O cálculo é circular: os próprios registros 9001/9900/9990/9999
    contam para os totais. Algoritmo:

    1. Conta os registros anteriores (``Counter``).
    2. Acrescenta o **9001** (abertura do bloco 9) → +1 no counter.
    3. Sabemos que vai existir um **9900** por TIPO distinto, mais
       o 9900 para si mesmo, mais o 9900 para o 9990 e o 9999.
       → vamos planejar: tipos = chaves do counter atual ∪ {9900, 9990, 9999}.
    4. Cada tipo gera UMA linha 9900 → ``count(9900) = len(tipos)``.
    5. +1 linha 9990 (totalizador do bloco 9) e +1 linha 9999 (total geral).
    6. Calcula ``count(9990) = total_linhas_bloco_9`` e
       ``count(9999) = total_geral_do_arquivo``.

    Retorna lista de linhas SPED prontas, em ordem.
    """
    base = Counter(contar_registros(linhas_anteriores))
    # 9001 é o primeiro registro do bloco 9.
    base["9001"] = 1

    tipos_que_terao_9900 = sorted(set(base.keys()) | {"9900", "9990", "9999"})
    base["9900"] = len(tipos_que_terao_9900)
    # 9990 é a contagem total do bloco 9: 9001 + (n × 9900) + ele próprio.
    total_bloco_9 = base["9001"] + base["9900"] + 1
    base["9990"] = 1
    # 9999 conta TODAS as linhas do arquivo, inclusive ele.
    total_geral = sum(base.values()) + 1  # +1 = a própria linha 9999
    base["9999"] = 1

    out: list[str] = []
    out.append(linha("9001", "0"))
    for tipo in tipos_que_terao_9900:
        out.append(linha("9900", tipo, base[tipo]))
    out.append(linha("9990", total_bloco_9))
    out.append(linha("9999", total_geral))
    return out


def calcular_hash_sha256(conteudo: bytes) -> str:
    """SHA-256 do arquivo SPED, hex lowercase (formato do CHECK no DB)."""
    return hashlib.sha256(conteudo).hexdigest()


def parse_decimal(raw: str) -> Decimal:
    """Inverso de :func:`formatar_decimal` — ``"1234,56"`` → ``Decimal("1234.56")``.

    Sprint 18 PR2 — usado pelo importador SPED histórico para reconstruir
    valores monetários a partir das linhas pipe-delimited. Espaços laterais
    são tolerados; campo vazio devolve ``Decimal("0")``. Notação científica
    e separador de milhar não são aceitos no SPED — falham.
    """
    s = raw.strip()
    if not s:
        return Decimal("0")
    # SPED não usa separador de milhar; troca vírgula decimal por ponto.
    s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"valor decimal SPED inválido: {raw!r}") from exc


def parse_data(raw: str) -> date:
    """Inverso de :func:`formatar_data` — ``"31122025"`` → ``date(2025, 12, 31)``.

    Sprint 18 PR2. Falha rápida em formato inesperado para o importador
    devolver erro estrutural claro.
    """
    s = raw.strip()
    if len(s) != 8 or not s.isdigit():
        raise ValueError(f"data SPED inválida (esperado DDMMAAAA): {raw!r}")
    try:
        return date(int(s[4:8]), int(s[2:4]), int(s[:2]))
    except ValueError as exc:
        raise ValueError(f"data SPED inválida: {raw!r}") from exc


def parse_periodo(raw: str) -> date:
    """Inverso de :func:`formatar_periodo` — ``"122025"`` → ``date(2025, 12, 1)``.

    Sprint 18 PR2 — campos de período ECF (mês/ano) viram primeiro dia do mês.
    """
    s = raw.strip()
    if len(s) != 6 or not s.isdigit():
        raise ValueError(f"período SPED inválido (esperado MMAAAA): {raw!r}")
    try:
        return date(int(s[2:6]), int(s[:2]), 1)
    except ValueError as exc:
        raise ValueError(f"período SPED inválido: {raw!r}") from exc


def montar_arquivo(linhas: Sequence[str], *, encoding: str = "latin-1") -> bytes:
    """Junta as linhas e devolve bytes prontos para persistência/download.

    SPED ECD/ECF aceitam ``latin-1`` (Windows-1252) ou ``utf-8``. Usamos
    ``latin-1`` por compatibilidade histórica com o PVA da RFB — ele
    rejeita acentos em UTF-8 em versões antigas. Caracteres fora do
    latin-1 são substituídos por ``?`` (defesa: o input já passou por
    ``escapar`` que mantém só ASCII visível + acentos latinos).
    """
    txt = "".join(linhas)
    return txt.encode(encoding, errors="replace")
