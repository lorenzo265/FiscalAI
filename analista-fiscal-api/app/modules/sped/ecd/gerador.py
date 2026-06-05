"""Gerador ECD — Escrituração Contábil Digital (Sprint 16 PR1).

**Camada 1 (determinística).** Função pura, zero I/O. Recebe um snapshot
estruturado (``EntradaEcd``) e devolve o conteúdo do arquivo ``.txt``
SPED ECD pronto para download.

Cobertura por bloco — perfil PME (Lucro Presumido / Simples opcional):

* **Bloco 0** — abertura + identificação:
    * ``0000`` — abertura do arquivo (versão leiaute, CNPJ, período, etc.)
    * ``0001`` — abertura do bloco 0
    * ``0007`` — outras inscrições da entidade (placeholder vazio)
    * ``0020`` — escrituração descentralizada (não usado — single estabelecimento)
    * ``0030`` — dados cadastrais
    * ``0035`` — identificação SCP (não aplicável)
    * ``0150`` — participantes (placeholder vazio nesta versão — não amarra a
      registros financeiros do MVP)
    * ``0990`` — encerramento do bloco 0
* **Bloco I** — escrituração contábil:
    * ``I001`` — abertura do bloco I
    * ``I010`` — identificação da escrituração (livro G normal, código 'G')
    * ``I012`` — código do livro (não detalhamos auxiliares no MVP — só G)
    * ``I030`` — termo de abertura
    * ``I050`` — plano de contas (uma linha por conta — sintética e analítica)
    * ``I051`` — plano de contas referencial (mapeamento RFB)
    * ``I100`` — centro de custos (placeholder vazio)
    * ``I150`` — saldos periódicos (intervalo, e.g. mês)
    * ``I155`` — detalhe dos saldos por conta
    * ``I200`` — lançamentos (cabeçalho)
    * ``I250`` — partidas do lançamento (D/C)
    * ``I350`` — saldo das contas de resultado antes do encerramento
    * ``I355`` — detalhe do saldo de resultado por conta
    * ``I990`` — encerramento do bloco I
* **Bloco J** — demonstrações:
    * ``J001`` — abertura do bloco J
    * ``J005`` — identificação das demonstrações
    * ``J100`` — Balanço Patrimonial (1 linha por agrupamento)
    * ``J150`` — DRE (1 linha por agrupamento)
    * ``J990`` — encerramento do bloco J
* **Bloco 9** — encerramento (computado por ``compartilhado.gerar_bloco_9``)

ALGORITMO_VERSAO bump em qualquer mudança que altere o conteúdo
gerado (campo novo, ordem diferente, header mudou).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.modules.sped.compartilhado import (
    calcular_hash_sha256,
    gerar_bloco_9,
    linha,
    montar_arquivo,
)

ALGORITMO_VERSAO = "sped.ecd.v2"

# Versão do leiaute ECD publicado pela RFB. ADE Cofis 64/2024 define
# v10 vigente a partir do ano-calendário 2024. Atualizar em conjunto
# com bump de ALGORITMO_VERSAO.
_LEIAUTE_VERSAO = "10.00"

# Indicador do tipo de escrituração (Tabela do leiaute):
#   "G" — Livro Diário (completo, sem auxiliar)
#   "R" — Diário com escrituração resumida
#   "A" — Razão Auxiliar
#   "Z" — Razão Auxiliar das subcontas
# MVP gera só G (mais comum em PME LP).
_TIPO_ESCRITURACAO_DEFAULT = "G"

# Indicador da situação especial (0 = normal; 1..5 = abertura/cisão/fusão/etc.).
# MVP foca em 0; tratamento de situação especial fica para sprint dedicada.
_SITUACAO_NORMAL = "0"


# ── DTOs de entrada ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdentificacaoEmpresaEcd:
    """Dados cadastrais persistidos no ``0000``/``0030``."""

    cnpj: str  # 14 dígitos
    razao_social: str
    nome_fantasia: str | None
    uf: str  # 2 letras
    municipio: str | None
    codigo_municipio_ibge: str  # 7 dígitos
    cep: str | None = None
    email: str | None = None
    telefone: str | None = None
    inscricao_estadual: str | None = None
    inscricao_municipal: str | None = None
    # Indicador do tipo de pessoa jurídica (registro 0000):
    # "0" PJ em geral, "1" PJ com filial no exterior, etc. MVP usa "0".
    indicador_pj: str = "0"


@dataclass(frozen=True, slots=True)
class ContaPlano:
    """Linha do plano de contas (``I050``)."""

    codigo: str
    descricao: str
    natureza: str  # 'D' | 'C'
    nivel: int  # 1..N (1 = raiz)
    tipo_conta: str  # 'S' = sintética, 'A' = analítica
    codigo_pai: str | None  # vazio se raiz
    codigo_ecd_referencial: str | None  # registro I051


@dataclass(frozen=True, slots=True)
class SaldoPeriodicoConta:
    """Saldo de uma conta no intervalo do ``I150`` (``I155``)."""

    codigo_conta: str
    saldo_inicial: Decimal
    indicador_saldo_inicial: str  # 'D' | 'C'
    total_debitos: Decimal
    total_creditos: Decimal
    saldo_final: Decimal
    indicador_saldo_final: str  # 'D' | 'C'


@dataclass(frozen=True, slots=True)
class SaldoPeriodico:
    """Intervalo + saldos por conta (``I150`` + N × ``I155``)."""

    inicio: date
    fim: date
    saldos: tuple[SaldoPeriodicoConta, ...]


@dataclass(frozen=True, slots=True)
class PartidaLanc:
    """Linha de partida (D ou C) de um lançamento (``I250``)."""

    codigo_conta: str
    valor: Decimal
    indicador_dc: str  # 'D' | 'C'
    historico: str  # texto livre


@dataclass(frozen=True, slots=True)
class LancamentoEcd:
    """Lançamento contábil — cabeçalho ``I200`` + partidas ``I250``."""

    numero: str  # sequencial no livro
    data: date
    valor_total: Decimal  # = soma dos D = soma dos C
    indicador_origem: str  # 'N' = normal, 'E' = estorno
    partidas: tuple[PartidaLanc, ...]


@dataclass(frozen=True, slots=True)
class SaldoResultadoConta:
    """Saldo de uma conta de resultado antes do encerramento (``I355``)."""

    codigo_conta: str
    valor: Decimal
    indicador_dc: str  # 'D' | 'C'


@dataclass(frozen=True, slots=True)
class LinhaDemonstracao:
    """Linha de Balanço (``J100``) ou DRE (``J150``).

    ``codigo_aglutinacao`` = código RFB de agrupamento (e.g. ``"1.01"``
    para Ativo Circulante; ``"3.01"`` para Receita Bruta).
    ``nivel_aglutinacao`` é 1..N como no plano referencial.
    """

    codigo_aglutinacao: str
    nivel: int
    natureza: str  # 'D' | 'C'
    descricao: str
    valor: Decimal


@dataclass(frozen=True, slots=True)
class EntradaEcd:
    """Snapshot completo para gerar uma ECD anual.

    Construído pelo service a partir de:

    * ``EmpresaRepo`` → identificação
    * ``ContabilRepo`` → plano de contas
    * ``SaldosPeriodoRepo`` → saldos mensais (I150/I155) + balanço (J100) + DRE (J150)
    * ``ContabilRepo`` → lançamentos do exercício (I200/I250)
    """

    empresa: IdentificacaoEmpresaEcd
    ano_calendario: int
    inicio_exercicio: date  # geralmente 1º jan
    fim_exercicio: date  # geralmente 31 dez
    indicador_situacao_inicio: str = _SITUACAO_NORMAL
    indicador_situacao_fim: str = _SITUACAO_NORMAL
    numero_ordem_livro: str = "1"  # sequencial do livro G no ano
    plano_contas: Sequence[ContaPlano] = field(default_factory=tuple)
    saldos_periodicos: Sequence[SaldoPeriodico] = field(default_factory=tuple)
    lancamentos: Sequence[LancamentoEcd] = field(default_factory=tuple)
    saldos_resultado_antes_encerramento: Sequence[SaldoResultadoConta] = field(
        default_factory=tuple
    )
    balanco: Sequence[LinhaDemonstracao] = field(default_factory=tuple)
    dre: Sequence[LinhaDemonstracao] = field(default_factory=tuple)
    tipo_escrituracao: str = _TIPO_ESCRITURACAO_DEFAULT


@dataclass(frozen=True, slots=True)
class ArquivoEcdGerado:
    """Saída do gerador — bytes + hash + metadados auxiliares."""

    conteudo: bytes
    hash_sha256: str
    tamanho_bytes: int
    total_linhas: int
    leiaute_versao: str = _LEIAUTE_VERSAO
    algoritmo_versao: str = ALGORITMO_VERSAO


# ── Erros internos do gerador (puros) ───────────────────────────────────────


class _EntradaEcdInvalida(ValueError):
    """Falha de pré-condição na entrada — antes de qualquer linha gerada."""


# ── Validação de pré-condições ───────────────────────────────────────────────


def _validar_entrada(entrada: EntradaEcd) -> None:
    """Falha cedo em invariantes do leiaute para não gerar arquivo torto."""
    if len(entrada.empresa.cnpj) != 14 or not entrada.empresa.cnpj.isdigit():
        raise _EntradaEcdInvalida(
            "CNPJ deve ter 14 dígitos (somente números) para o registro 0000."
        )
    if len(entrada.empresa.codigo_municipio_ibge) != 7:
        raise _EntradaEcdInvalida(
            "Código IBGE do município deve ter 7 dígitos (registro 0030)."
        )
    if entrada.fim_exercicio < entrada.inicio_exercicio:
        raise _EntradaEcdInvalida(
            "fim_exercicio deve ser ≥ inicio_exercicio (registro 0000)."
        )
    if entrada.tipo_escrituracao not in {"G", "R", "A", "B", "Z"}:
        raise _EntradaEcdInvalida(
            f"tipo_escrituracao inválido: {entrada.tipo_escrituracao!r}"
        )
    # Cada lançamento: soma D == soma C == valor_total.
    for lanc in entrada.lancamentos:
        deb = sum(
            (p.valor for p in lanc.partidas if p.indicador_dc == "D"),
            Decimal("0"),
        )
        cre = sum(
            (p.valor for p in lanc.partidas if p.indicador_dc == "C"),
            Decimal("0"),
        )
        if deb != cre:
            raise _EntradaEcdInvalida(
                f"Lançamento {lanc.numero}: débitos ({deb}) ≠ créditos ({cre})."
            )
        if deb != lanc.valor_total:
            raise _EntradaEcdInvalida(
                f"Lançamento {lanc.numero}: valor_total ({lanc.valor_total}) "
                f"≠ soma das partidas ({deb})."
            )
    # Plano de contas: I050 referenciado em I155/I250 deve existir.
    codigos = {c.codigo for c in entrada.plano_contas}
    for sp in entrada.saldos_periodicos:
        for s in sp.saldos:
            if s.codigo_conta not in codigos:
                raise _EntradaEcdInvalida(
                    f"Saldo periódico I155 referencia conta {s.codigo_conta} "
                    f"ausente do plano (I050)."
                )
    for lanc in entrada.lancamentos:
        for p in lanc.partidas:
            if p.codigo_conta not in codigos:
                raise _EntradaEcdInvalida(
                    f"Partida do lançamento {lanc.numero} referencia conta "
                    f"{p.codigo_conta} ausente do plano (I050)."
                )


# ── Geração por bloco ────────────────────────────────────────────────────────


def _gerar_bloco_0(entrada: EntradaEcd) -> list[str]:
    e = entrada.empresa
    out: list[str] = []
    # 0000 — abertura do arquivo.
    out.append(
        linha(
            "0000",
            _LEIAUTE_VERSAO,
            entrada.indicador_situacao_inicio,
            "",  # NUM_REC — preenchido pelo PVA na transmissão
            entrada.inicio_exercicio,
            entrada.fim_exercicio,
            e.razao_social,
            e.cnpj,
            e.uf,
            e.inscricao_estadual or "",
            e.codigo_municipio_ibge,
            e.inscricao_municipal or "",
            entrada.indicador_situacao_fim,
            "0",  # IND_NIRE (não usamos NIRE no MVP)
            "0",  # IND_FIN_ESC (0 = original)
            "",  # COD_HASH_SUB (preenchido pelo PVA)
            e.indicador_pj,
            "N",  # IND_GRANDE_PORTE
            "0",  # TIP_ECD (0 = ECD original)
            "",  # COD_SCP
            "S",  # IDENT_MF (S = ME/EPP submete em todo caso)
            "N",  # IND_ESC_CONS
            "N",  # IND_CENTRALIZADA
            "N",  # IND_MUDANC_PC
            "",  # COD_PLAN_REF
            "S",  # IND_ESC_INTERMED (S = escriturado pelo titular)
        )
    )
    # 0001 — abertura do bloco 0.
    out.append(linha("0001", "0"))
    # 0007 — outras inscrições (vazio no MVP — sem inscrição extra).
    # ECD aceita zero ocorrências.
    # 0020 — escrituração descentralizada (zero ocorrências — single estab).
    # 0030 — dados cadastrais.
    out.append(
        linha(
            "0030",
            "1",  # COD_NAT (1 = atividade comercial)
            "1",  # IND_ATIV (1 = industrial/comercial; 2 = serviços; etc.)
            e.cep or "",
            "",  # TIP_LOG (placeholder — vamos exigir endereço completo numa
            #         sprint futura quando vier do BrasilAPI)
            "",  # LOG (logradouro)
            "",  # NUM (número)
            "",  # COMPL
            "",  # BAIRRO
            e.telefone or "",
            "",  # FAX
            e.email or "",
        )
    )
    # 0035 — identificação SCP (zero ocorrências — PME não opera por SCP).
    # 0150 — participantes (zero ocorrências no MVP — não amarra a
    # transações financeiras nesta versão).
    # 0990 — encerramento do bloco 0.
    out.append(linha("0990", len(out) + 1))
    return out


def _gerar_bloco_i(entrada: EntradaEcd) -> list[str]:
    out: list[str] = []
    # I001 — abertura do bloco I.
    out.append(linha("I001", "0"))
    # I010 — identificação da escrituração.
    out.append(linha("I010", entrada.tipo_escrituracao, _LEIAUTE_VERSAO))
    # I012 — código do livro (G principal).
    out.append(
        linha(
            "I012",
            entrada.numero_ordem_livro,
            "LIVRO DIARIO",
            entrada.tipo_escrituracao,
            "N",  # IND_TIPO_ESC_PRE (sem ECD anterior linkada)
            "",  # COD_HASH_AUX
        )
    )
    # I030 — termo de abertura do livro G.
    out.append(
        linha(
            "I030",
            "TERMO DE ABERTURA",
            entrada.numero_ordem_livro,
            "LIVRO DIARIO",
            len(entrada.lancamentos),
            entrada.empresa.razao_social,
            entrada.empresa.cnpj,
            "",  # NIRE (não obrigatório para SLU/empresário ME)
            "",  # DT_ARQ (registro na junta — não obrigatório nesta versão)
            "",  # DT_ARQ_CONV
        )
    )
    # I050 — plano de contas.
    for c in entrada.plano_contas:
        out.append(
            linha(
                "I050",
                entrada.inicio_exercicio,
                "01",  # COD_NAT (01 = contas patrimoniais ou resultado)
                c.tipo_conta,
                c.nivel,
                c.natureza,
                c.codigo,
                c.codigo_pai or "",
                c.descricao,
            )
        )
    # I051 — mapeamento referencial RFB (1 por conta analítica com mapping).
    for c in entrada.plano_contas:
        if c.codigo_ecd_referencial and c.tipo_conta == "A":
            out.append(
                linha(
                    "I051",
                    "",  # COD_CCUS (sem centro de custos no MVP)
                    "",  # COD_CTA_REF (mantemos vazio se for o próprio)
                    c.codigo_ecd_referencial,
                )
            )
    # I150 + I155 — saldos periódicos.
    for sp in entrada.saldos_periodicos:
        out.append(linha("I150", sp.inicio, sp.fim))
        for s in sp.saldos:
            out.append(
                linha(
                    "I155",
                    s.codigo_conta,
                    "",  # COD_CCUS
                    s.saldo_inicial,
                    s.indicador_saldo_inicial,
                    s.total_debitos,
                    s.total_creditos,
                    s.saldo_final,
                    s.indicador_saldo_final,
                )
            )
    # I200 + I250 — lançamentos.
    for lanc in entrada.lancamentos:
        out.append(
            linha(
                "I200",
                lanc.numero,
                lanc.data,
                lanc.valor_total,
                lanc.indicador_origem,
            )
        )
        for p in lanc.partidas:
            out.append(
                linha(
                    "I250",
                    p.codigo_conta,
                    "",  # COD_CCUS
                    p.valor,
                    p.indicador_dc,
                    p.historico,
                    "",  # COD_HIST_PAD (sem catálogo de históricos no MVP)
                )
            )
    # I350 + I355 — saldo de resultado antes do encerramento.
    if entrada.saldos_resultado_antes_encerramento:
        out.append(linha("I350", entrada.fim_exercicio))
        for resultado_conta in entrada.saldos_resultado_antes_encerramento:
            out.append(
                linha(
                    "I355",
                    resultado_conta.codigo_conta,
                    "",  # COD_CCUS
                    resultado_conta.valor,
                    resultado_conta.indicador_dc,
                )
            )
    # I990 — encerramento do bloco I.
    out.append(linha("I990", len(out) + 1))
    return out


def _gerar_bloco_j(entrada: EntradaEcd) -> list[str]:
    out: list[str] = []
    # J001 — abertura do bloco J.
    out.append(linha("J001", "0"))
    # J005 — identificação das demonstrações.
    out.append(
        linha(
            "J005",
            entrada.inicio_exercicio,
            entrada.fim_exercicio,
            "0",  # IND_DEM (0 = sem identificação especial)
            "DEMONSTRACOES DO EXERCICIO",
        )
    )
    # J100 — Balanço Patrimonial.
    for ix, ln in enumerate(entrada.balanco, start=1):
        out.append(
            linha(
                "J100",
                ln.codigo_aglutinacao,
                ln.nivel,
                ln.natureza,
                "",  # COD_CTA_SUP (vazio nesta versão MVP)
                ln.descricao,
                ln.valor,
                ln.natureza,  # IND_DC_BAL
                "0",  # NIRE (não usado)
                _formatar_ordem(ix),
            )
        )
    # J150 — DRE.
    for ix, ln in enumerate(entrada.dre, start=1):
        out.append(
            linha(
                "J150",
                _formatar_ordem(ix),
                ln.codigo_aglutinacao,
                ln.nivel,
                ln.natureza,
                "",  # COD_CTA_SUP
                ln.descricao,
                ln.valor,
                ln.natureza,  # IND_VL (D = subtrai do resultado; C = adiciona)
            )
        )
    # J990 — encerramento do bloco J.
    out.append(linha("J990", len(out) + 1))
    return out


def _formatar_ordem(n: int) -> str:
    """Ordem de apresentação 4 dígitos zero-padded (convenção do bloco J)."""
    return f"{n:04d}"


# ── API pública ──────────────────────────────────────────────────────────────


def gerar_ecd(entrada: EntradaEcd) -> ArquivoEcdGerado:
    """Gera o arquivo ECD completo (todos os blocos + encerramento + hash).

    Pipeline:

    1. Valida pré-condições (CNPJ, IBGE, lançamentos balanceados, etc.).
    2. Gera blocos 0, I, J em ordem.
    3. Gera bloco 9 com totalizadores reais (via ``gerar_bloco_9``).
    4. Codifica em ``latin-1`` e calcula SHA-256.

    Raises:
        _EntradaEcdInvalida: para qualquer falha de pré-condição. O service
            traduz para ``SemDadosParaSped`` ou propaga como ``ValueError``
            conforme a causa.
    """
    _validar_entrada(entrada)

    linhas: list[str] = []
    linhas.extend(_gerar_bloco_0(entrada))
    linhas.extend(_gerar_bloco_i(entrada))
    linhas.extend(_gerar_bloco_j(entrada))
    linhas.extend(gerar_bloco_9(linhas))

    conteudo = montar_arquivo(linhas)
    return ArquivoEcdGerado(
        conteudo=conteudo,
        hash_sha256=calcular_hash_sha256(conteudo),
        tamanho_bytes=len(conteudo),
        total_linhas=len(linhas),
    )
