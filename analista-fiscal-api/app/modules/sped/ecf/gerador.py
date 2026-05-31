"""Gerador ECF — Escrituração Contábil Fiscal Lucro Presumido (Sprint 16 PR2).

**Camada 1 (determinística).** Função pura, zero I/O. Recebe um snapshot
estruturado (``EntradaEcf``) e devolve o conteúdo do arquivo ``.txt``
SPED ECF pronto para download.

Layout pipe-delimited igual ao ECD — reusa ``compartilhado.linha`` +
``compartilhado.gerar_bloco_9``. Lista de blocos OBRIGATÓRIOS no arquivo
ECF (todos precisam de abertura/encerramento, mesmo vazios):

  0 → C → E → J → K → L → M → N → P → Q → T → U → V → W → X → Y → 9

Para Lucro Presumido, blocos preenchidos com dados são 0, J, K, P, Y.
Os demais emitem apenas ``X001`` (com ``IND_DAD='1'`` quando aplicável)
+ ``X990`` (totalizador = 2).
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

ALGORITMO_VERSAO = "sped.ecf.v1"

# Versão do leiaute ECF — ADE Cofis 51/2024 define v10 vigente a partir
# do ano-calendário 2024. Atualizar junto com bump de ALGORITMO_VERSAO.
_LEIAUTE_VERSAO = "0010"

# Tabela do leiaute — situação inicial do exercício:
#   "0" = regular | "1" = abertura | "2" = resultante de cisão/fusão | etc.
_SITUACAO_REGULAR = "0"

# Forma de tributação (registro 0010):
#   "1" Lucro Real | "2" Lucro Real / Arbitrado |
#   "3" Lucro Presumido / Real | "4" Lucro Presumido |
#   "5" Imune do IRPJ | "6" Isenta do IRPJ |
#   "7" Lucro Arbitrado | "8" Lucro Real / Arbitrado / Presumido
_FORMA_TRIB_LP = "4"
_FORMA_TRIB_LP_REAL = "3"
_FORMA_TRIB_MAP = {
    "lucro_presumido": _FORMA_TRIB_LP,
    "lucro_real": "1",
    "lucro_presumido_real": _FORMA_TRIB_LP_REAL,
}

# Forma de apuração (registro 0010):
#   "A" = Anual (Lucro Real estimativa) | "T" = Trimestral
_FORMA_APUR_TRIMESTRAL = "T"


# ── DTOs de entrada ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdentificacaoEmpresaEcf:
    """Dados cadastrais para os registros 0000/0030."""

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


@dataclass(frozen=True, slots=True)
class EcdVinculada:
    """Identificação da ECD do mesmo ano (registro C040)."""

    hash_ecd: str  # SHA-256 do arquivo ECD aceito pela RFB
    num_recibo_ecd: str | None
    data_recibo: date | None


@dataclass(frozen=True, slots=True)
class ContaPlanoEcf:
    """Linha do plano de contas final (registro J050)."""

    codigo: str
    descricao: str
    natureza: str  # 'D' | 'C'
    nivel: int
    tipo_conta: str  # 'S' sintética / 'A' analítica
    codigo_pai: str | None
    codigo_ecd_referencial: str | None  # registro J051


@dataclass(frozen=True, slots=True)
class SaldoContaTrimestre:
    """Linha do K155 — saldo final de cada conta no fim do trimestre."""

    codigo_conta: str
    saldo_inicial: Decimal
    indicador_saldo_inicial: str  # 'D' | 'C'
    debitos: Decimal
    creditos: Decimal
    saldo_final: Decimal
    indicador_saldo_final: str  # 'D' | 'C'


@dataclass(frozen=True, slots=True)
class ApuracaoTrimestralLp:
    """Apuração consolidada de um trimestre Lucro Presumido.

    Construída pelo service a partir das ``ApuracaoFiscal`` (tipo='irpj'
    e tipo='csll') do trimestre + dados de discriminação de receita.
    """

    inicio: date
    fim: date
    numero_trimestre: int  # 1..4
    receita_bruta: Decimal
    percentual_presuncao_irpj: Decimal  # ex.: 0.0800 = 8%
    percentual_presuncao_csll: Decimal  # ex.: 0.1200 = 12%
    base_presumida_irpj: Decimal
    base_presumida_csll: Decimal
    ganhos_capital: Decimal
    receitas_aplicacoes: Decimal
    outras_adicoes_irpj: Decimal
    outras_adicoes_csll: Decimal
    base_total_irpj: Decimal
    base_total_csll: Decimal
    limite_adicional_irpj: Decimal
    irpj_normal: Decimal  # 15% × base
    irpj_adicional: Decimal  # 10% × excedente
    irpj_total: Decimal  # bruto antes de IRRF
    irrf_a_compensar: Decimal
    irrf_consumido: Decimal
    irpj_devido: Decimal  # líquido
    csll_devida: Decimal


@dataclass(frozen=True, slots=True)
class InformacoesGerais:
    """Bloco Y — campos genéricos exigidos pela ECF.

    MVP: apenas Y540 (discriminação de receita por atividade) e Y600 (sócios).
    Demais (Y570 DCTF, Y620 admin, Y671 estoque, etc.) ficam como pendência
    consciente — exigem dados de outros módulos (eventos eSocial, estoque).
    """

    discriminacao_receita: tuple[
        tuple[str, Decimal], ...
    ] = ()  # (cnae_ou_codigo_atividade, valor_anual)
    socios: tuple[
        tuple[str, str, Decimal], ...
    ] = ()  # (cpf_cnpj, nome, percentual_capital)


@dataclass(frozen=True, slots=True)
class EntradaEcf:
    """Snapshot completo para gerar uma ECF anual."""

    empresa: IdentificacaoEmpresaEcf
    ano_calendario: int
    inicio_exercicio: date  # geralmente 1º jan
    fim_exercicio: date  # geralmente 31 dez
    forma_tributacao: str = _FORMA_TRIB_LP  # '4' = Lucro Presumido
    ecd_vinculada: EcdVinculada | None = None  # None = C040 vazio
    plano_contas: Sequence[ContaPlanoEcf] = field(default_factory=tuple)
    saldos_por_trimestre: Sequence[
        tuple[int, tuple[SaldoContaTrimestre, ...]]
    ] = field(default_factory=tuple)  # (numero_trimestre, saldos)
    apuracoes_trimestrais: Sequence[ApuracaoTrimestralLp] = field(
        default_factory=tuple
    )
    informacoes_gerais: InformacoesGerais = field(
        default_factory=InformacoesGerais
    )


@dataclass(frozen=True, slots=True)
class ArquivoEcfGerado:
    """Saída do gerador — bytes + hash + metadados."""

    conteudo: bytes
    hash_sha256: str
    tamanho_bytes: int
    total_linhas: int
    leiaute_versao: str = _LEIAUTE_VERSAO
    algoritmo_versao: str = ALGORITMO_VERSAO


# ── Erros internos do gerador ────────────────────────────────────────────────


class _EntradaEcfInvalida(ValueError):
    """Falha de pré-condição da entrada — antes de qualquer linha gerada."""


# ── Validação de pré-condições ───────────────────────────────────────────────


def _validar_entrada(entrada: EntradaEcf) -> None:
    if len(entrada.empresa.cnpj) != 14 or not entrada.empresa.cnpj.isdigit():
        raise _EntradaEcfInvalida(
            "CNPJ deve ter 14 dígitos (somente números) para o registro 0000."
        )
    if len(entrada.empresa.codigo_municipio_ibge) != 7:
        raise _EntradaEcfInvalida(
            "Código IBGE do município deve ter 7 dígitos (registro 0030)."
        )
    if entrada.fim_exercicio < entrada.inicio_exercicio:
        raise _EntradaEcfInvalida(
            "fim_exercicio deve ser ≥ inicio_exercicio (registro 0000)."
        )
    if entrada.forma_tributacao not in {"1", "2", "3", "4", "5", "6", "7", "8"}:
        raise _EntradaEcfInvalida(
            f"forma_tributacao inválida: {entrada.forma_tributacao!r}"
        )
    # LP exige 4 trimestres se ano cheio; permitimos menos só para situação
    # especial (não-MVP). Apurações com numero_trimestre fora de 1..4 quebram.
    seen: set[int] = set()
    for ap in entrada.apuracoes_trimestrais:
        if ap.numero_trimestre < 1 or ap.numero_trimestre > 4:
            raise _EntradaEcfInvalida(
                f"numero_trimestre fora de [1,4]: {ap.numero_trimestre}"
            )
        if ap.numero_trimestre in seen:
            raise _EntradaEcfInvalida(
                f"Trimestre {ap.numero_trimestre} duplicado em apuracoes."
            )
        seen.add(ap.numero_trimestre)
        if ap.fim < ap.inicio:
            raise _EntradaEcfInvalida(
                f"Trimestre {ap.numero_trimestre}: fim < inicio."
            )
    # Plano de contas referenciado em K155.
    codigos = {c.codigo for c in entrada.plano_contas}
    for _, saldos in entrada.saldos_por_trimestre:
        for s in saldos:
            if s.codigo_conta not in codigos:
                raise _EntradaEcfInvalida(
                    f"Saldo K155 referencia conta {s.codigo_conta} "
                    f"ausente do plano (J050)."
                )


# ── Geração por bloco ────────────────────────────────────────────────────────


def _gerar_bloco_0(entrada: EntradaEcf) -> list[str]:
    e = entrada.empresa
    out: list[str] = []
    # 0000 — abertura do arquivo.
    # Layout ECF v10: |0000|LECF|0|CNPJ|NOME|IND_SIT_ESP|...|DT_INI|DT_FIN|...
    out.append(
        linha(
            "0000",
            "LECF",  # COD_VER (literal)
            _LEIAUTE_VERSAO,
            e.cnpj,
            e.razao_social,
            _SITUACAO_REGULAR,  # IND_SIT_ESP
            "",  # SIT_ESP_VERSAO_ANT (vazio se 0)
            "",  # PAT_REM_INI (PAT remanescente — vazio se 0)
            entrada.inicio_exercicio,
            entrada.fim_exercicio,
            "N",  # IND_FIN_ESC (N = original; S = retificadora)
            "",  # NUM_REC_ANTERIOR (preenchido pelo PVA na retificação)
            "0",  # TIP_ECF (0 = ECF original; 1 = situação especial)
            "",  # COD_SCP (sem SCP)
            "N",  # IND_GR_PER (não grupo)
            entrada.forma_tributacao,  # FORMA_TRIB
            _FORMA_APUR_TRIMESTRAL,  # FORMA_APUR (T = trimestral)
        )
    )
    # 0001 — abertura do bloco 0.
    out.append(linha("0001", "0"))
    # 0010 — parâmetros de tributação.
    hash_ecd = entrada.ecd_vinculada.hash_ecd if entrada.ecd_vinculada else ""
    out.append(
        linha(
            "0010",
            "1",  # OPT_REFIS (1 = não optante)
            "1",  # OPT_PAES
            entrada.forma_tributacao,  # FORMA_TRIB_PER_ANT
            _FORMA_APUR_TRIMESTRAL,  # APUR_CSLL
            "N",  # ATIV_RURAL
            "N",  # TIP_ESC_PRE (sem escrita prévia)
            "N",  # IND_REC_REC_BRU_ANT (sem rec rec bruta ant)
            "",  # COD_QUALIF_PJ
            "N",  # IND_ADMIN_HABILIT (placeholder)
            "N",  # IND_ATIV_INCORPOR (sem RET)
            "N",  # IND_INTERV_ESTATAL
            "N",  # IND_INF_DEFICIT
            "N",  # IND_AUMEN_PAT
            "N",  # IND_INF_PJ_COMP
        )
    )
    # 0020 — parâmetros complementares.
    out.append(
        linha(
            "0020",
            "N",  # IND_PJ_HABILITADA_PERT (PERT)
            "N",  # IND_AVALIA_GERAL
            "N",  # IND_REC_FUNCESP (FUNCESP)
            "N",  # IND_TRANSF_CTRL
        )
    )
    # 0030 — dados cadastrais.
    out.append(
        linha(
            "0030",
            "1",  # COD_NAT (1 = comercial/industrial)
            "1",  # IND_ATIV
            e.cep or "",
            "",  # TIP_LOG
            "",  # LOG (logradouro)
            "",  # NUM
            "",  # COMPL
            "",  # BAIRRO
            e.telefone or "",
            "",  # FAX
            e.email or "",
        )
    )
    # 0930 — identificação do signatário (não exigido em MVP — futuro).
    # 0990 — encerramento bloco 0.
    out.append(linha("0990", len(out) + 1))
    return out


def _gerar_bloco_c(entrada: EntradaEcf) -> list[str]:
    """Bloco C — recuperação da ECD vinculada do mesmo ano."""
    out: list[str] = []
    tem_dados = entrada.ecd_vinculada is not None
    out.append(linha("C001", "0" if tem_dados else "1"))
    if tem_dados:
        ecd = entrada.ecd_vinculada
        # C040 — identificação da ECD.
        out.append(
            linha(
                "C040",
                ecd.hash_ecd if ecd else "",
                ecd.num_recibo_ecd if ecd else "",
                ecd.data_recibo if ecd else "",
            )
        )
    out.append(linha("C990", len(out) + 1))
    return out


def _gerar_bloco_vazio(reg_abertura: str, reg_encerramento: str) -> list[str]:
    """Bloco sem dados — abertura ``IND_DAD='1'`` + encerramento totalizador."""
    out = [linha(reg_abertura, "1")]
    out.append(linha(reg_encerramento, len(out) + 1))
    return out


def _gerar_bloco_e() -> list[str]:
    """Bloco E — incentivos fiscais (zero ocorrências MVP)."""
    return _gerar_bloco_vazio("E001", "E990")


def _gerar_bloco_j(entrada: EntradaEcf) -> list[str]:
    """Bloco J — plano de contas final + mapeamento referencial."""
    out: list[str] = []
    tem_dados = bool(entrada.plano_contas)
    out.append(linha("J001", "0" if tem_dados else "1"))
    # J050 — plano de contas.
    for c in entrada.plano_contas:
        out.append(
            linha(
                "J050",
                entrada.inicio_exercicio,  # DT_ALT (vigência)
                "01",  # COD_NAT (01 = patrimoniais/resultado)
                c.tipo_conta,  # IND_CTA ('S'/'A')
                c.nivel,
                c.natureza,
                c.codigo,
                c.codigo_pai or "",
                c.descricao,
            )
        )
    # J051 — mapeamento referencial RFB (1 por conta analítica com mapping).
    for c in entrada.plano_contas:
        if c.codigo_ecd_referencial and c.tipo_conta == "A":
            out.append(
                linha(
                    "J051",
                    "",  # COD_CCUS
                    c.codigo,  # COD_CTA
                    c.codigo_ecd_referencial,
                )
            )
    # J100 — centros de custos (zero ocorrências MVP).
    # J990 — encerramento.
    out.append(linha("J990", len(out) + 1))
    return out


def _gerar_bloco_k(entrada: EntradaEcf) -> list[str]:
    """Bloco K — saldos contábeis por período de apuração trimestral.

    Para LP trimestral, há 4 períodos (1 por trimestre). Cada K030 abre um
    período; K155 lista os saldos finais; K156 (não implementado MVP) seria
    o mapeamento — em LP usamos J051 que já vincula.
    """
    out: list[str] = []
    tem_dados = bool(entrada.saldos_por_trimestre)
    out.append(linha("K001", "0" if tem_dados else "1"))
    for numero_trimestre, saldos in entrada.saldos_por_trimestre:
        inicio, fim = _datas_do_trimestre(entrada.ano_calendario, numero_trimestre)
        # K030 — identificação do período.
        out.append(
            linha(
                "K030",
                inicio,
                fim,
                _FORMA_APUR_TRIMESTRAL,  # PER_APUR
                "1",  # IND_FIN_ESC (1 = original)
            )
        )
        # K155 — saldo final por conta.
        for s in saldos:
            out.append(
                linha(
                    "K155",
                    s.codigo_conta,
                    "",  # COD_CCUS
                    s.saldo_inicial,
                    s.indicador_saldo_inicial,
                    s.debitos,
                    s.creditos,
                    s.saldo_final,
                    s.indicador_saldo_final,
                )
            )
    # K990 — encerramento bloco K.
    out.append(linha("K990", len(out) + 1))
    return out


def _gerar_bloco_l() -> list[str]:
    """Bloco L — Lucro Real LALUR (zero em LP)."""
    return _gerar_bloco_vazio("L001", "L990")


def _gerar_bloco_m() -> list[str]:
    """Bloco M — LALUR-A (Lucro Real). Zero em LP."""
    return _gerar_bloco_vazio("M001", "M990")


def _gerar_bloco_n() -> list[str]:
    """Bloco N — Cálculo IRPJ/CSLL Lucro Real (zero em LP)."""
    return _gerar_bloco_vazio("N001", "N990")


def _gerar_bloco_p(entrada: EntradaEcf) -> list[str]:
    """Bloco P — Lucro Presumido. Núcleo da apuração.

    Registros:

    * **P001** — abertura.
    * **P010** — identificação dos períodos (1 por trimestre).
    * **P030** — atividade preponderante por período (placeholder simples).
    * **P100** — receitas do período com base de presunção.
    * **P130** — discriminação por atividade (mesmo conteúdo do Y540).
    * **P200** — apuração do IRPJ trimestral.
    * **P300** — apuração da CSLL trimestral.
    * **P400** — base de cálculo do IRPJ apurada.
    * **P500** — base de cálculo da CSLL apurada.
    * **P990** — encerramento.
    """
    out: list[str] = []
    tem_dados = bool(entrada.apuracoes_trimestrais)
    out.append(linha("P001", "0" if tem_dados else "1"))
    for ap in entrada.apuracoes_trimestrais:
        # P010 — identificação do período.
        out.append(
            linha(
                "P010",
                ap.inicio,
                ap.fim,
            )
        )
        # P030 — atividade preponderante do período (simplificado: 01 comércio).
        out.append(
            linha(
                "P030",
                "01",  # IND_NIRE (placeholder)
                "01",  # IND_ATIV (comercial)
            )
        )
        # P100 — receitas com presunção.
        out.append(
            linha(
                "P100",
                ap.receita_bruta,
                ap.percentual_presuncao_irpj,
                ap.base_presumida_irpj,
                ap.ganhos_capital,
                ap.receitas_aplicacoes,
                ap.outras_adicoes_irpj,
                ap.base_total_irpj,
            )
        )
        # P130 — discriminação por atividade (cópia do Y540 — manter coerente).
        # MVP: emitimos uma linha agregada com a receita bruta + presunção IRPJ.
        out.append(
            linha(
                "P130",
                "01",  # COD_ATIV (01 = comercial)
                ap.receita_bruta,
                ap.percentual_presuncao_irpj,
                ap.base_presumida_irpj,
            )
        )
        # P200 — apuração do IRPJ trimestral.
        out.append(
            linha(
                "P200",
                ap.base_total_irpj,
                ap.limite_adicional_irpj,
                ap.irpj_normal,
                ap.irpj_adicional,
                ap.irpj_total,
                ap.irrf_consumido,
                ap.irpj_devido,
            )
        )
        # P300 — apuração da CSLL trimestral.
        out.append(
            linha(
                "P300",
                ap.receita_bruta,
                ap.percentual_presuncao_csll,
                ap.base_presumida_csll,
                ap.outras_adicoes_csll,
                ap.base_total_csll,
                ap.csll_devida,
            )
        )
        # P400 — base de cálculo do IRPJ apurada (resumo).
        out.append(
            linha(
                "P400",
                ap.base_total_irpj,
                ap.irpj_total,
            )
        )
        # P500 — base de cálculo da CSLL apurada (resumo).
        out.append(
            linha(
                "P500",
                ap.base_total_csll,
                ap.csll_devida,
            )
        )
    # P990 — encerramento.
    out.append(linha("P990", len(out) + 1))
    return out


def _gerar_bloco_q() -> list[str]:
    """Bloco Q — Lucro Arbitrado (zero em LP)."""
    return _gerar_bloco_vazio("Q001", "Q990")


def _gerar_bloco_t() -> list[str]:
    """Bloco T — Imune/Isenta (zero em LP)."""
    return _gerar_bloco_vazio("T001", "T990")


def _gerar_bloco_u() -> list[str]:
    """Bloco U — Lucros no Exterior (zero MVP)."""
    return _gerar_bloco_vazio("U001", "U990")


def _gerar_bloco_v() -> list[str]:
    """Bloco V — Incentivos AC (zero MVP)."""
    return _gerar_bloco_vazio("V001", "V990")


def _gerar_bloco_w() -> list[str]:
    """Bloco W — Intervenção Estatal (zero MVP)."""
    return _gerar_bloco_vazio("W001", "W990")


def _gerar_bloco_x() -> list[str]:
    """Bloco X — Demonstrações/Operações Especiais (zero MVP)."""
    return _gerar_bloco_vazio("X001", "X990")


def _gerar_bloco_y(entrada: EntradaEcf) -> list[str]:
    """Bloco Y — Informações Gerais (Y540 receita + Y600 sócios)."""
    out: list[str] = []
    info = entrada.informacoes_gerais
    tem_dados = bool(info.discriminacao_receita or info.socios)
    out.append(linha("Y001", "0" if tem_dados else "1"))
    # Y540 — discriminação da receita por atividade.
    for codigo_ativ, valor in info.discriminacao_receita:
        out.append(linha("Y540", codigo_ativ, valor))
    # Y600 — identificação dos sócios e administradores.
    for cpf_cnpj, nome, pct in info.socios:
        out.append(
            linha(
                "Y600",
                cpf_cnpj,
                nome,
                pct,
            )
        )
    out.append(linha("Y990", len(out) + 1))
    return out


# ── Helpers ──────────────────────────────────────────────────────────────────


def _datas_do_trimestre(ano: int, numero: int) -> tuple[date, date]:
    """Retorna (1º dia, último dia) do trimestre do ano civil."""
    mes_inicio = 3 * (numero - 1) + 1
    mes_fim = mes_inicio + 2
    if mes_fim == 12:
        fim = date(ano, 12, 31)
    else:
        # 1º dia do mês seguinte − 1.
        from datetime import timedelta
        proximo_inicio = date(ano, mes_fim + 1, 1)
        fim = proximo_inicio - timedelta(days=1)
    return date(ano, mes_inicio, 1), fim


# ── API pública ──────────────────────────────────────────────────────────────


def gerar_ecf(entrada: EntradaEcf) -> ArquivoEcfGerado:
    """Gera o arquivo ECF completo (todos os blocos + encerramento + hash).

    Pipeline:

    1. Valida pré-condições (CNPJ, IBGE, períodos coerentes, trimestres
       únicos, plano vs saldos).
    2. Gera blocos 0 → C → E → J → K → L → M → N → P → Q → T → U → V →
       W → X → Y em ordem.
    3. Gera bloco 9 com totalizadores (via ``gerar_bloco_9``).
    4. Codifica em ``latin-1`` e calcula SHA-256.
    """
    _validar_entrada(entrada)

    linhas: list[str] = []
    linhas.extend(_gerar_bloco_0(entrada))
    linhas.extend(_gerar_bloco_c(entrada))
    linhas.extend(_gerar_bloco_e())
    linhas.extend(_gerar_bloco_j(entrada))
    linhas.extend(_gerar_bloco_k(entrada))
    linhas.extend(_gerar_bloco_l())
    linhas.extend(_gerar_bloco_m())
    linhas.extend(_gerar_bloco_n())
    linhas.extend(_gerar_bloco_p(entrada))
    linhas.extend(_gerar_bloco_q())
    linhas.extend(_gerar_bloco_t())
    linhas.extend(_gerar_bloco_u())
    linhas.extend(_gerar_bloco_v())
    linhas.extend(_gerar_bloco_w())
    linhas.extend(_gerar_bloco_x())
    linhas.extend(_gerar_bloco_y(entrada))
    linhas.extend(gerar_bloco_9(linhas))

    conteudo = montar_arquivo(linhas)
    return ArquivoEcfGerado(
        conteudo=conteudo,
        hash_sha256=calcular_hash_sha256(conteudo),
        tamanho_bytes=len(conteudo),
        total_linhas=len(linhas),
    )
