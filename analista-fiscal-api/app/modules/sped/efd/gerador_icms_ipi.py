"""Gerador EFD ICMS-IPI — apuração mensal de ICMS e IPI (Sprint 17 PR2).

**Camada 1 (determinística).** Função pura, zero I/O. Recebe um snapshot
estruturado (``EntradaEfdIcmsIpi``) e devolve o conteúdo do arquivo
``.txt`` SPED EFD ICMS-IPI pronto para download.

Escopo PR2 — empresas com inscrição estadual (comércio LP/SN ou
indústria). Cobertura por bloco:

* **Bloco 0** — abertura + identificação:
    * ``0000`` — abertura (versão leiaute, CNPJ, IE, período).
    * ``0001`` — abertura do bloco 0 (``IND_MOV`` ``0`` = com dados).
    * ``0005`` — dados complementares da entidade.
    * ``0100`` — dados do contabilista (placeholder mínimo).
    * ``0150`` — tabela de participantes (clientes + fornecedores únicos).
    * ``0190`` — unidades de medida (apenas ``UN`` no MVP).
    * ``0200`` — tabela de identificação do item (placeholder vazio v1).
    * ``0990`` — encerramento.
* **Bloco C** — documentos de mercadoria (NF-e modelo 55 / NFC-e 65):
    * ``C001`` — abertura.
    * ``C100`` — cabeçalho do documento.
    * ``C170`` — itens (agregado por NF na v1 — granularidade por item
      em sprint futura, ver pendência).
    * ``C190`` — analítico por CST/CFOP/alíquota (1 linha por combinação
      única do C100/C170 — fundamental para amarração E110).
    * ``C990`` — encerramento.
* **Bloco D** — documentos de serviço de transporte/comunicação:
    * ``D001`` (``IND_MOV='1'`` vazio na v1), ``D990``.
* **Bloco E** — apuração ICMS e IPI:
    * ``E001`` — abertura.
    * ``E100`` — período de apuração ICMS.
    * ``E110`` — apuração consolidada do ICMS (débitos, créditos, saldo).
    * ``E116`` — obrigações ICMS a recolher (1 linha por DARE/GNRE).
    * ``E200`` — período de apuração IPI (só se houver IPI no mês).
    * ``E210`` — apuração consolidada IPI.
    * ``E990`` — encerramento.
* **Bloco G** — CIAP (controle do ativo permanente):
    * ``G001`` (``IND_MOV='1'`` vazio na v1 — pendência), ``G990``.
* **Bloco H** — inventário anual:
    * ``H001`` (``IND_MOV='1'`` vazio na v1 — H010 é anual, sprint
      dedicada), ``H990``.
* **Bloco 1** — outras informações:
    * ``1001`` (``IND_MOV='1'``), ``1990``.
* **Bloco 9** — controle (computado por ``compartilhado.gerar_bloco_9``).

**Fora de escopo do PR2 (declarado §8.11):**

* **Bloco K** — controle de produção / estoque (indústria) — Fase 5 backlog.
* **Bloco B** — escrituração e apuração do ISS (somente RJ/SP) — sprint
  dedicada quando esses municípios passarem a exigir EFD ICMS-IPI com bloco B.
* **CIAP** (G110/G125/etc.) — apuração 1/48 do ICMS dos bens do ativo
  imobilizado. Reusa cadastro da Sprint 8 quando vier.
* **Inventário H010** — escrituração anual (31/12) com saldos por item.
* **CBS/IBS** — pendência #23, sprint dedicada quando RFB publicar
  leiaute integrado.

ALGORITMO_VERSAO bump em qualquer mudança que altere o conteúdo gerado.
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
from app.modules.sped.efd.ciap import SnapshotCiap

# Auditoria 2026-06-04 bump (#8): E110 VL_SLD_APURADO corrigido.
ALGORITMO_VERSAO = "sped.efd_icms_ipi.v4"
# Auditoria 2026-06-04 bump v3→v4 — FIX #8: E110 campo VL_SLD_APURADO
# (campo 10/índice 9) recebia ``valor_icms_a_recolher`` (duplicando o campo
# VL_ICMS_RECOLHER). Corrigido para refletir o saldo apurado real:
#   débitos − créditos − saldo_credor_anterior
# (positivo = saldo devedor; negativo = saldo credor, que vai em
# VL_SLD_CREDOR_TRANSPORTAR). O PVA recalcula aritmeticamente e acusava
# inconsistência quando créditos > débitos.
#
# Sprint 19.6 PR1 bump (#31): Bloco G CIAP real (antes era vazio).
# Sprint 19.8 PR1 — bump v2→v3: bloco B agora emitido (stub IND_MOV=1)
# para cobertura completa do leiaute.

# Versão do leiaute EFD ICMS-IPI — Ajuste SINIEF 02/2009 + Guia Prático
# v3.1.7 (vigente 2024+). Atualizar com bump de ALGORITMO_VERSAO quando
# COTEPE/ICMS publicar nova versão.
_LEIAUTE_VERSAO = "017"  # COD_VER do registro 0000

# Finalidade do arquivo (registro 0000):
#   "0" = remessa do arquivo original | "1" = remessa substituta
_FINALIDADE_ORIGINAL = "0"

# Indicador da atividade (0000):
#   "0" = industrial / equiparado | "1" = comércio e demais atividades
_IND_ATIV_DEFAULT = "1"

# Indicador de movimento dos blocos (X001):
_IND_MOV_COM_DADOS = "0"
_IND_MOV_SEM_DADOS = "1"

# Perfil de apresentação do arquivo (0000):
#   "A" = perfil completo (default — exigido por contribuintes maiores)
#   "B" = perfil intermediário | "C" = perfil simplificado (PME)
_PERFIL_DEFAULT = "A"

# Indicador do tipo de operação (C100):
#   "0" = entrada | "1" = saída
_IND_OPER_ENTRADA = "0"
_IND_OPER_SAIDA = "1"

# Indicador do emitente (C100):
#   "0" = emissão própria | "1" = terceiros
_IND_EMIT_PROPRIO = "0"

# Situação do documento (C100):
#   "00" = autorizado | "02" = cancelado | "04" = denegado
_COD_SIT_AUTORIZADO = "00"
_COD_SIT_CANCELADO = "02"

# CST ICMS A/B (registros C170/C190):
#   "00" = tributada integralmente
#   "10" = tributada com cobrança ST
#   "40" = isenta | "41" = não tributada | "60" = ICMS ST cobrado anteriormente
#   Tabela 4.3.1 do leiaute (com prefixo de origem 0..8 no C170: ex. "000")
_CST_TRIB_INTEGRAL = "000"
_CST_ISENTA = "040"

# Indicador de tipo do frete (C100):
#   "0" = sem frete | "1" = por conta do emitente
_IND_FRT_SEM = "9"

# Indicador de movimento físico (C170):
#   "0" = sim (movimentou estoque) | "1" = não
_IND_MOV_FISICO_SIM = "0"

_ZERO = Decimal("0")


# ── DTOs de entrada ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdentificacaoEmpresaEfdIcms:
    """Dados cadastrais para os registros 0000/0005."""

    cnpj: str  # 14 dígitos
    razao_social: str
    nome_fantasia: str | None
    uf: str  # 2 letras
    municipio: str | None
    codigo_municipio_ibge: str  # 7 dígitos
    inscricao_estadual: str  # NÃO NULL — EFD ICMS-IPI exige IE
    cep: str | None = None
    email: str | None = None
    telefone: str | None = None
    inscricao_municipal: str | None = None
    suframa: str | None = None
    ind_ativ: str = _IND_ATIV_DEFAULT
    perfil: str = _PERFIL_DEFAULT


@dataclass(frozen=True, slots=True)
class ParticipanteIcms:
    """Participante referenciado por documento (``0150``)."""

    codigo: str
    nome: str
    pais: str = "01058"  # Brasil
    cnpj: str | None = None
    cpf: str | None = None
    inscricao_estadual: str | None = None
    municipio_ibge: str | None = None
    endereco: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentoIcmsEfd:
    """Documento de mercadoria → blocos C100/C170/C190.

    Granularidade agregada por documento na v1 (1 item por NF). Sprint
    futura quebra por item real do XML — ver pendência.
    """

    chave: str  # chave 44 dígitos
    numero: str
    serie: str
    modelo: str  # "55" (NF-e) ou "65" (NFC-e)
    data_emissao: date
    codigo_participante: str
    valor_total: Decimal
    valor_mercadorias: Decimal  # base de cálculo ICMS quando tributada
    valor_icms: Decimal
    aliquota_icms: Decimal  # 18.00 = 18% (formato % do SPED)
    valor_ipi: Decimal = _ZERO
    cfop: str = "5102"  # 4 dígitos
    cst_icms: str = _CST_TRIB_INTEGRAL  # 3 dígitos: origem + CST
    ncm: str | None = None
    indicador_operacao: str = _IND_OPER_SAIDA
    indicador_emitente: str = _IND_EMIT_PROPRIO
    cancelado: bool = False


@dataclass(frozen=True, slots=True)
class ApuracaoMensalIcms:
    """Snapshot do bloco E para ICMS.

    Valores vêm da ``ApuracaoFiscal`` da Sprint 11 PR2
    (``icms.mensal.v1``).
    """

    valor_total_debitos: Decimal  # débitos do mês (saídas tributadas)
    valor_total_creditos: Decimal  # créditos (entradas com direito)
    saldo_credor_anterior: Decimal
    ajustes_devedores: Decimal
    ajustes_credores: Decimal
    valor_icms_a_recolher: Decimal  # max(0, saldo_apurado)
    saldo_credor_a_transportar: Decimal  # max(0, -saldo_apurado)


@dataclass(frozen=True, slots=True)
class ObrigacaoIcmsRecolher:
    """Uma linha do ``E116`` (DARE/GNRE a recolher).

    No MVP geramos uma única linha consolidada por mês — sub-rotações
    por crédito fiscal entram em sprint futura.
    """

    codigo_obrigacao: str  # ex.: "000" (ICMS próprio)
    valor: Decimal
    data_vencimento: date
    codigo_receita: str = "100099"  # placeholder genérico


@dataclass(frozen=True, slots=True)
class ApuracaoMensalIpi:
    """Snapshot do bloco E para IPI (registros E200/E210).

    Opcional — só preenchemos blocos E200/E210 quando ``preenchido=True``.
    Não há cálculo dedicado de IPI nesta sprint — o caller passa totais
    já consolidados (saídas vs entradas com direito a crédito IPI).
    """

    preenchido: bool
    valor_total_debitos: Decimal = _ZERO
    valor_total_creditos: Decimal = _ZERO
    saldo_credor_anterior: Decimal = _ZERO
    valor_ipi_a_recolher: Decimal = _ZERO
    saldo_credor_a_transportar: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class EntradaEfdIcmsIpi:
    """Snapshot completo para gerar a EFD ICMS-IPI do mês."""

    empresa: IdentificacaoEmpresaEfdIcms
    competencia_inicio: date
    competencia_fim: date
    apuracao_icms: ApuracaoMensalIcms
    participantes: Sequence[ParticipanteIcms] = field(default_factory=tuple)
    documentos: Sequence[DocumentoIcmsEfd] = field(default_factory=tuple)
    obrigacoes_a_recolher: Sequence[ObrigacaoIcmsRecolher] = field(
        default_factory=tuple
    )
    apuracao_ipi: ApuracaoMensalIpi = field(
        default_factory=lambda: ApuracaoMensalIpi(preenchido=False)
    )
    # Sprint 19.6 PR1 (#31) — CIAP. Default vazio (bloco G fica vazio
    # com IND_MOV='1' como na v1). Quando preenchido, gera G110+G125.
    ciap: SnapshotCiap | None = None
    finalidade: str = _FINALIDADE_ORIGINAL
    nome_contabilista: str = ""
    cnpj_contabilista: str | None = None
    crc_contabilista: str | None = None
    email_contabilista: str | None = None


@dataclass(frozen=True, slots=True)
class ArquivoEfdIcmsIpiGerado:
    """Saída do gerador — bytes + hash + metadados."""

    conteudo: bytes
    hash_sha256: str
    tamanho_bytes: int
    total_linhas: int
    leiaute_versao: str = _LEIAUTE_VERSAO
    algoritmo_versao: str = ALGORITMO_VERSAO


# ── Erros internos do gerador (puros) ───────────────────────────────────────


class _EntradaEfdIcmsInvalida(ValueError):
    """Falha de pré-condição na entrada — antes de qualquer linha gerada."""


# ── Validação de pré-condições ───────────────────────────────────────────────


def _validar_entrada(entrada: EntradaEfdIcmsIpi) -> None:
    """Falha cedo em invariantes do leiaute."""
    e = entrada.empresa
    if len(e.cnpj) != 14 or not e.cnpj.isdigit():
        raise _EntradaEfdIcmsInvalida(
            "CNPJ deve ter 14 dígitos (somente números) para o registro 0000."
        )
    if not e.inscricao_estadual:
        raise _EntradaEfdIcmsInvalida(
            "Inscrição estadual é obrigatória na EFD ICMS-IPI (registro 0000)."
        )
    if len(e.codigo_municipio_ibge) != 7:
        raise _EntradaEfdIcmsInvalida(
            "Código IBGE do município deve ter 7 dígitos (registro 0005)."
        )
    if entrada.competencia_fim < entrada.competencia_inicio:
        raise _EntradaEfdIcmsInvalida(
            "competencia_fim deve ser ≥ competencia_inicio (registro 0000)."
        )
    if (
        entrada.competencia_inicio.year != entrada.competencia_fim.year
        or entrada.competencia_inicio.month != entrada.competencia_fim.month
    ):
        raise _EntradaEfdIcmsInvalida(
            "EFD ICMS-IPI é mensal: competencia_inicio e competencia_fim "
            "devem ser do mesmo mês civil."
        )
    cods = {p.codigo for p in entrada.participantes}
    for doc in entrada.documentos:
        if doc.codigo_participante not in cods:
            raise _EntradaEfdIcmsInvalida(
                f"NF-e {doc.chave} referencia participante "
                f"{doc.codigo_participante} ausente do 0150."
            )
        if len(doc.cfop) != 4 or not doc.cfop.isdigit():
            raise _EntradaEfdIcmsInvalida(
                f"CFOP inválido em NF-e {doc.chave}: {doc.cfop!r}"
            )
        if len(doc.cst_icms) != 3 or not doc.cst_icms.isdigit():
            raise _EntradaEfdIcmsInvalida(
                f"CST ICMS inválido em NF-e {doc.chave}: {doc.cst_icms!r} "
                "(esperado 3 dígitos: origem + CST)."
            )


# ── Geração por bloco ────────────────────────────────────────────────────────


def _gerar_bloco_0(entrada: EntradaEfdIcmsIpi) -> list[str]:
    e = entrada.empresa
    out: list[str] = []
    # 0000 — abertura do arquivo.
    out.append(
        linha(
            "0000",
            _LEIAUTE_VERSAO,
            entrada.finalidade,
            entrada.competencia_inicio,
            entrada.competencia_fim,
            e.razao_social,
            e.cnpj,
            "",  # CPF (PJ não usa)
            e.uf,
            e.inscricao_estadual,
            e.codigo_municipio_ibge,
            e.inscricao_municipal or "",
            e.suframa or "",
            e.ind_ativ,
            e.perfil,
        )
    )
    # 0001 — abertura do bloco 0.
    out.append(linha("0001", _IND_MOV_COM_DADOS))
    # 0005 — dados complementares.
    out.append(
        linha(
            "0005",
            e.nome_fantasia or e.razao_social,
            e.cep or "",
            "",  # END (logradouro)
            "",  # NUM
            "",  # COMPL
            "",  # BAIRRO
            e.telefone or "",
            "",  # FAX
            e.email or "",
        )
    )
    # 0100 — dados do contabilista.
    out.append(
        linha(
            "0100",
            entrada.nome_contabilista or e.razao_social,
            entrada.cnpj_contabilista or "",
            entrada.crc_contabilista or "",
            entrada.cnpj_contabilista or "",
            e.cep or "",
            "",  # END
            "",  # NUM
            "",  # COMPL
            "",  # BAIRRO
            e.telefone or "",
            "",  # FAX
            entrada.email_contabilista or e.email or "",
            e.codigo_municipio_ibge,
        )
    )
    # 0150 — participantes.
    for p in entrada.participantes:
        out.append(
            linha(
                "0150",
                p.codigo,
                p.nome,
                p.pais,
                p.cnpj or "",
                p.cpf or "",
                p.inscricao_estadual or "",
                p.municipio_ibge or "",
                "",  # SUFRAMA
                p.endereco or "",
                "",  # NUM
                "",  # COMPL
                "",  # BAIRRO
            )
        )
    # 0190 — unidade de medida.
    out.append(linha("0190", "UN", "UNIDADE"))
    # 0200 — itens (placeholder vazio v1).
    # 0990 — encerramento do bloco 0.
    out.append(linha("0990", len(out) + 1))
    return out


def _gerar_bloco_c(entrada: EntradaEfdIcmsIpi) -> list[str]:
    """Bloco C — documentos de mercadoria (NF-e/NFC-e)."""
    out: list[str] = []
    tem_dados = bool(entrada.documentos)
    # C001 — abertura.
    out.append(
        linha(
            "C001",
            _IND_MOV_COM_DADOS if tem_dados else _IND_MOV_SEM_DADOS,
        )
    )
    if tem_dados:
        for doc in entrada.documentos:
            cod_sit = _COD_SIT_CANCELADO if doc.cancelado else _COD_SIT_AUTORIZADO
            # C100 — cabeçalho.
            out.append(
                linha(
                    "C100",
                    doc.indicador_operacao,
                    doc.indicador_emitente,
                    doc.codigo_participante,
                    doc.modelo,
                    cod_sit,
                    doc.serie,
                    doc.numero,
                    doc.chave,
                    doc.data_emissao,
                    doc.data_emissao,  # DT_E_S
                    doc.valor_total,
                    "0",  # IND_PGTO (0 = à vista)
                    "0",  # VL_DESC
                    "0",  # VL_ABAT_NT
                    doc.valor_mercadorias,  # VL_MERC
                    _IND_FRT_SEM,
                    "0",  # VL_FRT
                    "0",  # VL_SEG
                    "0",  # VL_OUT_DA
                    doc.valor_mercadorias,  # VL_BC_ICMS
                    doc.valor_icms,
                    "0",  # VL_BC_ICMS_ST
                    "0",  # VL_ICMS_ST
                    "0",  # VL_IPI
                    "0",  # VL_PIS
                    "0",  # VL_COFINS
                    "0",  # VL_PIS_ST
                    "0",  # VL_COFINS_ST
                )
            )
            # C170 — item agregado (1 por NF na v1).
            out.append(
                linha(
                    "C170",
                    "1",  # NUM_ITEM
                    "MERC-GENERICO",  # COD_ITEM
                    doc.numero,  # DESCR_COMPL
                    "1",  # QTD
                    "UN",  # UNID
                    doc.valor_mercadorias,  # VL_ITEM
                    "0",  # VL_DESC
                    _IND_MOV_FISICO_SIM,
                    doc.cst_icms,
                    doc.cfop,
                    "0",  # COD_NAT
                    doc.valor_mercadorias,  # VL_BC_ICMS
                    doc.aliquota_icms,
                    doc.valor_icms,
                    "0",  # VL_BC_ICMS_ST
                    "0",  # ALIQ_ST
                    "0",  # VL_ICMS_ST
                    "N",  # IND_APUR (N = anual; M = mensal — para IPI)
                    "00",  # CST_IPI
                    "",  # COD_ENQ
                    "0",  # VL_BC_IPI
                    "0",  # ALIQ_IPI
                    doc.valor_ipi,
                    "01",  # CST_PIS (placeholder — bloco C do EFD ICMS não foca em PIS)
                    "0",  # VL_BC_PIS
                    "0",  # ALIQ_PIS
                    "0",  # QUANT_BC_PIS
                    "0",  # ALIQ_PIS_QUANT
                    "0",  # VL_PIS
                    "01",  # CST_COFINS
                    "0",  # VL_BC_COFINS
                    "0",  # ALIQ_COFINS
                    "0",  # QUANT_BC_COFINS
                    "0",  # ALIQ_COFINS_QUANT
                    "0",  # VL_COFINS
                    "",  # COD_CTA
                )
            )
            # C190 — analítico por CST/CFOP/alíquota (1 por combinação).
            out.append(
                linha(
                    "C190",
                    doc.cst_icms,
                    doc.cfop,
                    doc.aliquota_icms,
                    doc.valor_total,
                    doc.valor_mercadorias,  # VL_BC_ICMS
                    doc.valor_icms,
                    "0",  # VL_BC_ICMS_ST
                    "0",  # VL_ICMS_ST
                    "0",  # VL_RED_BC
                    doc.valor_ipi,
                    "",  # COD_OBS
                )
            )
    # C990 — encerramento.
    out.append(linha("C990", len(out) + 1))
    return out


def _gerar_bloco_e(entrada: EntradaEfdIcmsIpi) -> list[str]:
    """Bloco E — apuração ICMS e (opcionalmente) IPI."""
    out: list[str] = []
    # E001 — abertura.
    out.append(linha("E001", _IND_MOV_COM_DADOS))

    # E100 — período de apuração ICMS.
    out.append(
        linha(
            "E100",
            entrada.competencia_inicio,
            entrada.competencia_fim,
        )
    )
    ap = entrada.apuracao_icms
    # E110 — apuração consolidada do ICMS.
    #
    # VL_SLD_APURADO = VL_TOT_DEBITOS − VL_TOT_CREDITOS − VL_SLD_CREDOR_ANT
    # (fórmula simplificada quando ajustes = 0; positivo = saldo devedor,
    #  negativo = saldo credor). O PVA recalcula esse campo aritmeticamente
    #  e rejeita o arquivo quando diverge do declarado.
    #
    # Bug anterior (v3): VL_SLD_APURADO recebia ``valor_icms_a_recolher``
    # (sempre ≥ 0), ignorando o saldo credor e duplicando o VL_ICMS_RECOLHER.
    # Em meses com créditos > débitos o PVA detectava inconsistência aritmética.
    _saldo_apurado = (
        ap.valor_total_debitos
        - ap.valor_total_creditos
        - ap.saldo_credor_anterior
    )
    out.append(
        linha(
            "E110",
            ap.valor_total_debitos,         # VL_TOT_DEBITOS
            "0",                            # VL_AJ_DEBITOS
            "0",                            # VL_TOT_AJ_DEBITOS
            "0",                            # VL_ESTORNOS_CRED
            ap.valor_total_creditos,        # VL_TOT_CREDITOS
            "0",                            # VL_AJ_CREDITOS
            "0",                            # VL_TOT_AJ_CREDITOS
            "0",                            # VL_ESTORNOS_DEB
            ap.saldo_credor_anterior,       # VL_SLD_CREDOR_ANT
            _saldo_apurado,                 # VL_SLD_APURADO (★ corrigido)
            ap.ajustes_devedores,           # VL_TOT_DED
            ap.valor_icms_a_recolher,       # VL_ICMS_RECOLHER
            ap.saldo_credor_a_transportar,  # VL_SLD_CREDOR_TRANSPORTAR
            "0",                            # DEB_ESP
        )
    )
    # E116 — uma linha por obrigação a recolher.
    for obg in entrada.obrigacoes_a_recolher:
        out.append(
            linha(
                "E116",
                obg.codigo_obrigacao,
                obg.valor,
                obg.data_vencimento,
                obg.codigo_receita,
                "",  # NUM_PROC
                "",  # IND_PROC
                "",  # PROC
                "",  # TXT_COMPL
                entrada.competencia_inicio,  # MES_REF
            )
        )

    # E200/E210 — apuração IPI (opcional).
    ipi = entrada.apuracao_ipi
    if ipi.preenchido:
        out.append(
            linha(
                "E200",
                "0",  # COD_INC (0 = mensal)
                entrada.competencia_inicio,
                entrada.competencia_fim,
            )
        )
        out.append(
            linha(
                "E210",
                "0",  # IND_APUR (0 = mensal)
                ipi.valor_total_debitos,
                "0",  # VL_AJ_DEBITOS
                "0",  # VL_TOT_AJ_DEBITOS
                ipi.valor_total_creditos,
                "0",  # VL_AJ_CREDITOS
                "0",  # VL_TOT_AJ_CREDITOS
                ipi.saldo_credor_anterior,
                ipi.valor_ipi_a_recolher,  # VL_SLD_DEV
                "0",  # VL_DED
                ipi.valor_ipi_a_recolher,  # VL_IPI_RECOLHER
                ipi.saldo_credor_a_transportar,  # VL_SLD_CRED_FIM
            )
        )

    # E990 — encerramento.
    out.append(linha("E990", len(out) + 1))
    return out


def _gerar_bloco_g(entrada: EntradaEfdIcmsIpi) -> list[str]:
    """Bloco G — CIAP (Sprint 19.6 PR1 #31).

    Quando ``entrada.ciap`` é None ou snapshot vazio (sem movimentos +
    saldos zero), bloco vai como vazio (``IND_MOV='1'``). Quando há
    movimento ou saldo, emite G001 → G110 (1 linha consolidada do
    período) → G125 (1 linha por bem com apropriação no período) → G990.

    Estrutura G110 (Ajuste SINIEF 02/2009 + Guia Prático v3.1.7):
      DT_INI | DT_FIN | SALDO_IN_ICMS | SOM_PARC | VL_TRIB_OC |
      ICMS_OC | VL_TOT_TRIB | IND_PER_SAI | ICMS_DESEMB_OC | SALDO_FN_ICMS

    Campos de "saídas com isenção" (VL_TRIB_OC, ICMS_OC, IND_PER_SAI,
    etc.) ficam zerados — apuração proporcional por isenção é
    out-of-scope desta entrega (vide ciap.py).

    Estrutura G125:
      COD_IND_BEM | DT_MOV | TIPO_MOV | VL_IMOB_ICMS_OP |
      VL_IMOB_ICMS_ST | VL_IMOB_ICMS_FRT | VL_IMOB_ICMS_DIF |
      NUM_PARC | VL_PARC_PASS
    """
    ciap = entrada.ciap
    tem_dados = (
        ciap is not None
        and (ciap.tem_movimentos or ciap.saldo_inicial_icms > Decimal("0"))
    )
    out: list[str] = []
    out.append(linha("G001", _IND_MOV_COM_DADOS if tem_dados else _IND_MOV_SEM_DADOS))
    if tem_dados and ciap is not None:
        # G110 — saldo CIAP do período (1 linha consolidada).
        out.append(
            linha(
                "G110",
                entrada.competencia_inicio,
                entrada.competencia_fim,
                ciap.saldo_inicial_icms,  # SALDO_IN_ICMS
                ciap.soma_parcelas_periodo,  # SOM_PARC
                "0",  # VL_TRIB_OC — out-of-scope (saídas tributáveis específicas)
                "0",  # ICMS_OC — out-of-scope (ICMS sobre saídas específicas)
                "0",  # VL_TOT_TRIB — out-of-scope
                "0",  # IND_PER_SAI — out-of-scope (índice de saídas isentas)
                "0",  # ICMS_DESEMB_OC — out-of-scope (desembaraço)
                ciap.saldo_final_icms,  # SALDO_FN_ICMS
            )
        )
        # G125 — uma linha por movimento (bem apropriado no período).
        for mov in ciap.movimentos:
            out.append(
                linha(
                    "G125",
                    mov.bem_id,  # COD_IND_BEM
                    mov.data_movimento,  # DT_MOV
                    mov.tipo_movimento,  # TIPO_MOV (IM = imobilização período)
                    mov.valor_imob_icms_op,  # VL_IMOB_ICMS_OP
                    "0",  # VL_IMOB_ICMS_ST — out-of-scope (sub. tributária)
                    "0",  # VL_IMOB_ICMS_FRT — out-of-scope (frete)
                    "0",  # VL_IMOB_ICMS_DIF — out-of-scope (diferencial)
                    mov.num_parcela,  # NUM_PARC (1..48)
                    mov.valor_parcela,  # VL_PARC_PASS = ICMS / 48
                )
            )
    out.append(linha("G990", len(out) + 1))
    return out


def _gerar_bloco_vazio(prefixo: str) -> list[str]:
    """Bloco com apenas abertura ``X001`` (IND_MOV=1) + encerramento ``X990``."""
    out: list[str] = []
    out.append(linha(f"{prefixo}001", _IND_MOV_SEM_DADOS))
    out.append(linha(f"{prefixo}990", len(out) + 1))
    return out


# ── API pública ──────────────────────────────────────────────────────────────


def gerar_efd_icms_ipi(
    entrada: EntradaEfdIcmsIpi,
) -> ArquivoEfdIcmsIpiGerado:
    """Gera o arquivo EFD ICMS-IPI mensal completo.

    Pipeline:

    1. Valida pré-condições (CNPJ, IE, IBGE, mês civil, participantes, CFOP, CST).
    2. Gera blocos 0, C, D (vazio), E, G (vazio), H (vazio), 1 (vazio).
    3. Gera bloco 9 com totalizadores reais (via ``gerar_bloco_9``).
    4. Codifica em ``latin-1`` e calcula SHA-256.

    Raises:
        _EntradaEfdIcmsInvalida: para qualquer falha de pré-condição.
    """
    _validar_entrada(entrada)

    linhas: list[str] = []
    linhas.extend(_gerar_bloco_0(entrada))
    # Sprint 19.8 PR1 (#30) — Bloco B (ISS RJ/SP) stub IND_MOV=1. Quando
    # primeiro cliente RJ/SP com ISS escriturado no EFD ICMS-IPI aparecer,
    # trocar pelo bloco real (B001/B020/B025/B030/B100/B470/B500/B990).
    # Hoje ISS vai em DAS/PGDAS para SN ou em DARF municipal para LP.
    linhas.extend(_gerar_bloco_vazio("B"))
    linhas.extend(_gerar_bloco_c(entrada))
    # Sprint 19.8 PR1 (#29) — Bloco D (CT-e/MDF-e/DCE) permanece stub até
    # cliente com transporte/comunicação aparecer. Trigger documentado em
    # `docs/pendencias/runbook-ativacao-externos.md`.
    linhas.extend(_gerar_bloco_vazio("D"))
    linhas.extend(_gerar_bloco_e(entrada))
    linhas.extend(_gerar_bloco_g(entrada))
    # Sprint 19.8 PR1 (#32) — Bloco H (inventário anual H010) é
    # escrituração 31/12 com saldos por item. Stub `IND_MOV=1` até módulo
    # de estoque entrar; alternativa: emitir só H010 derivado do
    # `documento_fiscal_item` somado por NCM. Trigger no runbook.
    linhas.extend(_gerar_bloco_vazio("H"))
    linhas.extend(_gerar_bloco_vazio("1"))
    linhas.extend(gerar_bloco_9(linhas))

    conteudo = montar_arquivo(linhas)
    return ArquivoEfdIcmsIpiGerado(
        conteudo=conteudo,
        hash_sha256=calcular_hash_sha256(conteudo),
        tamanho_bytes=len(conteudo),
        total_linhas=len(linhas),
    )
