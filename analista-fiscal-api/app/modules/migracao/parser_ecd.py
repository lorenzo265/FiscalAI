"""Parser SPED ECD — Escrituração Contábil Digital (Sprint 18 PR2).

**Camada 1 (determinística).** Função pura, zero I/O. Recebe ``bytes`` (o
``.txt`` SPED entregue pelo escritório antigo) e devolve uma dataclass
``EcdParseado`` com toda a escrituração materializada em memória.

**Reversão** do gerador ``app/modules/sped/ecd/gerador.py`` (Sprint 16 PR1).
Cobre os blocos cuja informação alimenta o motor contábil do FiscalAI:

* **Bloco 0** — apenas ``0000`` (cabeçalho com CNPJ + período).
* **Bloco I** — ``I050`` (plano de contas), ``I150``/``I155`` (saldos
  periódicos), ``I200``/``I250`` (lançamentos + partidas).
* **Bloco 9** — ``9999`` (validação de integridade do arquivo).

Blocos não-essenciais (``J100``/``J150`` demonstrações; ``I350``/``I355``
saldos de resultado) ficam como **snapshot para audit** em
``EcdParseado.demonstracoes_snapshot`` — não reconstruímos DRE/Balanço do
escritório anterior; **nós recalculamos** a partir dos lançamentos
importados quando o cliente acessar o relatório.

Princípios aplicados:

* **§8.4 Golden tests** — round-trip ``gerar_ecd → parse_ecd`` deve devolver
  a mesma dataclass para fixtures controladas.
* **§8.6 Re-check determinístico** — validamos amarrações (9999 == total
  real, débitos == créditos por lançamento) e levantamos ``EcdInvalido``
  antes de qualquer escrita no DB.
* **§8.8 LLM nunca escreve fatos** — parser é 100% regex / split / Decimal.
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

ALGORITMO_VERSAO = "migracao.ecd.v1"


# ── Erros do parser ──────────────────────────────────────────────────────────


class EcdInvalido(ValueError):
    """ECD malformada ou com amarração quebrada — não pode ser importada."""


# ── DTOs ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdentificacaoEcdParseada:
    """Cabeçalho extraído de ``0000``."""

    cnpj: str
    razao_social: str
    uf: str
    codigo_municipio_ibge: str
    inicio_exercicio: date
    fim_exercicio: date
    leiaute_versao: str
    indicador_situacao_inicio: str


@dataclass(frozen=True, slots=True)
class ContaPlanoParseada:
    """Linha ``I050``."""

    codigo: str
    descricao: str
    natureza: str  # 'D' | 'C'
    nivel: int
    tipo_conta: str  # 'S' | 'A'
    codigo_pai: str | None


@dataclass(frozen=True, slots=True)
class SaldoPeriodicoContaParseado:
    """Linha ``I155``."""

    codigo_conta: str
    saldo_inicial: Decimal
    indicador_saldo_inicial: str
    total_debitos: Decimal
    total_creditos: Decimal
    saldo_final: Decimal
    indicador_saldo_final: str


@dataclass(frozen=True, slots=True)
class SaldoPeriodicoParseado:
    """``I150`` + N × ``I155``."""

    inicio: date
    fim: date
    saldos: tuple[SaldoPeriodicoContaParseado, ...]


@dataclass(frozen=True, slots=True)
class PartidaLancParseada:
    """``I250`` — débito ou crédito."""

    codigo_conta: str
    valor: Decimal
    indicador_dc: str  # 'D' | 'C'
    historico: str


@dataclass(frozen=True, slots=True)
class LancamentoEcdParseado:
    """``I200`` + N × ``I250``."""

    numero: str
    data: date
    valor_total: Decimal
    indicador_origem: str  # 'N' | 'E'
    partidas: tuple[PartidaLancParseada, ...]


@dataclass(frozen=True, slots=True)
class EcdParseado:
    """Resultado do parse — pronto para o ``MigracaoService`` montar candidatos."""

    identificacao: IdentificacaoEcdParseada
    plano_contas: tuple[ContaPlanoParseada, ...]
    saldos_periodicos: tuple[SaldoPeriodicoParseado, ...]
    lancamentos: tuple[LancamentoEcdParseado, ...]
    # Snapshot bruto dos blocos J/I350 — não usado para reconstruir, só audit.
    demonstracoes_snapshot: tuple[dict[str, str], ...] = field(default_factory=tuple)
    total_linhas: int = 0
    hash_arquivo: str = ""
    algoritmo_versao: str = ALGORITMO_VERSAO


# ── Helpers ─────────────────────────────────────────────────────────────────


def _decompor(conteudo: bytes) -> list[list[str]]:
    """Decompõe o arquivo SPED em lista de campos por linha.

    Tolerante a CRLF e a encoding latin-1 ou utf-8 (tenta latin-1 primeiro;
    se decodificação falhar, usa utf-8 com ``errors='replace'``).
    """
    try:
        texto = conteudo.decode("latin-1")
    except UnicodeDecodeError:  # pragma: no cover — defesa em profundidade
        texto = conteudo.decode("utf-8", errors="replace")
    linhas: list[list[str]] = []
    for bruta in texto.splitlines():
        if not bruta or not bruta.startswith("|"):
            continue
        # SPED canônico termina em '|' — split(' |' ) deixa campos limpos.
        # Removemos o pipe inicial e final para obter os campos.
        nucleo = bruta[1:]
        if nucleo.endswith("|"):
            nucleo = nucleo[:-1]
        campos = nucleo.split("|")
        if campos and campos[0]:
            linhas.append(campos)
    return linhas


def _campo(linha: list[str], idx: int) -> str:
    """Campo no índice ``idx`` (1-based para combinar com leiaute SPED)."""
    if idx <= 0 or idx > len(linha):
        return ""
    return linha[idx - 1]


# ── Extração por bloco ──────────────────────────────────────────────────────


def _extrair_identificacao(linhas: list[list[str]]) -> IdentificacaoEcdParseada:
    for ln in linhas:
        if ln[0] != "0000":
            continue
        return IdentificacaoEcdParseada(
            leiaute_versao=_campo(ln, 2),
            indicador_situacao_inicio=_campo(ln, 3),
            inicio_exercicio=parse_data(_campo(ln, 5)),
            fim_exercicio=parse_data(_campo(ln, 6)),
            razao_social=_campo(ln, 7),
            cnpj=_campo(ln, 8),
            uf=_campo(ln, 9),
            codigo_municipio_ibge=_campo(ln, 11),
        )
    raise EcdInvalido("Registro 0000 ausente — não é um SPED ECD válido")


def _extrair_plano_contas(
    linhas: list[list[str]],
) -> tuple[ContaPlanoParseada, ...]:
    contas: list[ContaPlanoParseada] = []
    for ln in linhas:
        if ln[0] != "I050":
            continue
        # I050: |I050|DT_ALT|COD_NAT|IND_CTA|NIVEL|COD_NAT_CC|COD_CTA|COD_CTA_SUP|CTA|
        nivel_raw = _campo(ln, 5)
        try:
            nivel = int(nivel_raw)
        except ValueError as exc:
            raise EcdInvalido(
                f"I050 com NIVEL inválido: {nivel_raw!r}"
            ) from exc
        contas.append(
            ContaPlanoParseada(
                tipo_conta=_campo(ln, 4),
                nivel=nivel,
                natureza=_campo(ln, 6),
                codigo=_campo(ln, 7),
                codigo_pai=_campo(ln, 8) or None,
                descricao=_campo(ln, 9),
            )
        )
    return tuple(contas)


def _extrair_saldos_periodicos(
    linhas: list[list[str]],
) -> tuple[SaldoPeriodicoParseado, ...]:
    periodos: list[SaldoPeriodicoParseado] = []
    inicio_atual: date | None = None
    fim_atual: date | None = None
    saldos_atual: list[SaldoPeriodicoContaParseado] = []

    def fechar_periodo() -> None:
        if inicio_atual is None or fim_atual is None:
            return
        periodos.append(
            SaldoPeriodicoParseado(
                inicio=inicio_atual,
                fim=fim_atual,
                saldos=tuple(saldos_atual),
            )
        )

    for ln in linhas:
        if ln[0] == "I150":
            fechar_periodo()
            inicio_atual = parse_data(_campo(ln, 2))
            fim_atual = parse_data(_campo(ln, 3))
            saldos_atual = []
        elif ln[0] == "I155":
            if inicio_atual is None:
                raise EcdInvalido("I155 sem I150 antecedente")
            # I155: |I155|COD_CTA|COD_CCUS|VL_SLD_INI|IND_DC_INI|VL_DEB|VL_CRED|VL_SLD_FIN|IND_DC_FIN|
            saldos_atual.append(
                SaldoPeriodicoContaParseado(
                    codigo_conta=_campo(ln, 2),
                    saldo_inicial=parse_decimal(_campo(ln, 4)),
                    indicador_saldo_inicial=_campo(ln, 5),
                    total_debitos=parse_decimal(_campo(ln, 6)),
                    total_creditos=parse_decimal(_campo(ln, 7)),
                    saldo_final=parse_decimal(_campo(ln, 8)),
                    indicador_saldo_final=_campo(ln, 9),
                )
            )
    fechar_periodo()
    return tuple(periodos)


def _extrair_lancamentos(
    linhas: list[list[str]],
) -> tuple[LancamentoEcdParseado, ...]:
    lancamentos: list[LancamentoEcdParseado] = []
    numero_atual: str | None = None
    data_atual: date | None = None
    valor_atual: Decimal | None = None
    origem_atual: str | None = None
    partidas_atual: list[PartidaLancParseada] = []

    def fechar_lancamento() -> None:
        if numero_atual is None:
            return
        if data_atual is None or valor_atual is None or origem_atual is None:
            return
        lancamentos.append(
            LancamentoEcdParseado(
                numero=numero_atual,
                data=data_atual,
                valor_total=valor_atual,
                indicador_origem=origem_atual,
                partidas=tuple(partidas_atual),
            )
        )

    for ln in linhas:
        if ln[0] == "I200":
            fechar_lancamento()
            # I200: |I200|NUM_LCTO|DT_LCTO|VL_LCTO|IND_LCTO|
            numero_atual = _campo(ln, 2)
            data_atual = parse_data(_campo(ln, 3))
            valor_atual = parse_decimal(_campo(ln, 4))
            origem_atual = _campo(ln, 5)
            partidas_atual = []
        elif ln[0] == "I250":
            if numero_atual is None:
                raise EcdInvalido("I250 sem I200 antecedente")
            # I250: |I250|COD_CTA|COD_CCUS|VL_DC|IND_DC|COD_HIST_PAD|HIST|
            partidas_atual.append(
                PartidaLancParseada(
                    codigo_conta=_campo(ln, 2),
                    valor=parse_decimal(_campo(ln, 4)),
                    indicador_dc=_campo(ln, 5),
                    historico=_campo(ln, 7),
                )
            )
    fechar_lancamento()
    return tuple(lancamentos)


def _validar_amarracoes(
    identificacao: IdentificacaoEcdParseada,
    plano: tuple[ContaPlanoParseada, ...],
    lancamentos: tuple[LancamentoEcdParseado, ...],
    total_linhas: int,
    linhas: list[list[str]],
) -> None:
    """Re-check determinístico (§8.6) das amarrações estruturais."""
    if len(identificacao.cnpj) != 14 or not identificacao.cnpj.isdigit():
        raise EcdInvalido(
            f"CNPJ 0000 inválido: {identificacao.cnpj!r} (esperado 14 dígitos)"
        )
    if identificacao.fim_exercicio < identificacao.inicio_exercicio:
        raise EcdInvalido(
            "0000 com fim_exercicio < inicio_exercicio"
        )

    codigos_plano = {c.codigo for c in plano}
    for lanc in lancamentos:
        debito = sum(
            (p.valor for p in lanc.partidas if p.indicador_dc == "D"),
            start=Decimal("0"),
        )
        credito = sum(
            (p.valor for p in lanc.partidas if p.indicador_dc == "C"),
            start=Decimal("0"),
        )
        if debito != credito:
            raise EcdInvalido(
                f"I200 {lanc.numero}: débitos ({debito}) ≠ créditos ({credito})"
            )
        if debito != lanc.valor_total:
            raise EcdInvalido(
                f"I200 {lanc.numero}: VL_LCTO ({lanc.valor_total}) "
                f"≠ soma partidas ({debito})"
            )
        for p in lanc.partidas:
            if p.codigo_conta not in codigos_plano:
                raise EcdInvalido(
                    f"I250 do lançamento {lanc.numero} referencia conta "
                    f"{p.codigo_conta!r} ausente do I050"
                )

    # 9999 — total real do arquivo.
    for ln in linhas:
        if ln[0] == "9999":
            declarado_raw = _campo(ln, 2)
            try:
                declarado = int(declarado_raw)
            except ValueError as exc:
                raise EcdInvalido(
                    f"9999 com QTD_LIN inválido: {declarado_raw!r}"
                ) from exc
            if declarado != total_linhas:
                raise EcdInvalido(
                    f"9999 declarado={declarado} ≠ total real={total_linhas}"
                )
            return
    raise EcdInvalido("Registro 9999 ausente — arquivo incompleto")


def _extrair_demonstracoes_snapshot(
    linhas: list[list[str]],
) -> tuple[dict[str, str], ...]:
    """J100/J150/I355 viram dict snapshot — não usado para reconstruir DRE."""
    snapshot: list[dict[str, str]] = []
    for ln in linhas:
        if ln[0] not in {"J100", "J150", "I355"}:
            continue
        snapshot.append({f"campo_{i}": v for i, v in enumerate(ln, start=1)})
    return tuple(snapshot)


# ── API pública ─────────────────────────────────────────────────────────────


def parse_ecd(conteudo: bytes) -> EcdParseado:
    """Faz o parse completo de um arquivo SPED ECD.

    Pipeline:

    1. Decodifica latin-1 → linhas de campos pipe-delimited.
    2. Extrai cabeçalho (``0000``).
    3. Extrai plano de contas (``I050``).
    4. Extrai saldos periódicos (``I150``/``I155``).
    5. Extrai lançamentos (``I200``/``I250``).
    6. Valida amarrações (débito==crédito, conta∈plano, 9999==total).
    7. Calcula SHA-256 do conteúdo bruto (igual ao do gerador).

    Raises:
        EcdInvalido: para qualquer falha estrutural ou de amarração.
    """
    if not conteudo:
        raise EcdInvalido("Arquivo vazio")

    linhas = _decompor(conteudo)
    if not linhas:
        raise EcdInvalido("Arquivo sem nenhuma linha SPED válida")

    identificacao = _extrair_identificacao(linhas)
    plano = _extrair_plano_contas(linhas)
    saldos = _extrair_saldos_periodicos(linhas)
    lancamentos = _extrair_lancamentos(linhas)

    _validar_amarracoes(identificacao, plano, lancamentos, len(linhas), linhas)

    return EcdParseado(
        identificacao=identificacao,
        plano_contas=plano,
        saldos_periodicos=saldos,
        lancamentos=lancamentos,
        demonstracoes_snapshot=_extrair_demonstracoes_snapshot(linhas),
        total_linhas=len(linhas),
        hash_arquivo=calcular_hash_sha256(conteudo),
    )


# ── Suporte ao __all__ ──────────────────────────────────────────────────────


__all__: Sequence[str] = (
    "ALGORITMO_VERSAO",
    "ContaPlanoParseada",
    "EcdInvalido",
    "EcdParseado",
    "IdentificacaoEcdParseada",
    "LancamentoEcdParseado",
    "PartidaLancParseada",
    "SaldoPeriodicoContaParseado",
    "SaldoPeriodicoParseado",
    "parse_ecd",
)
