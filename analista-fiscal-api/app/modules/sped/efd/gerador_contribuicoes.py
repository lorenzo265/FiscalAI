"""Gerador EFD-Contribuições — apuração mensal de PIS/Cofins (Sprint 17 PR1).

**Camada 1 (determinística).** Função pura, zero I/O. Recebe um snapshot
estruturado (``EntradaEfdContribuicoes``) e devolve o conteúdo do arquivo
``.txt`` SPED EFD-Contribuições pronto para download.

Escopo PR1 — empresas Lucro Presumido (regime **cumulativo**) com
operações típicas de comércio e prestação de serviços. Cobertura por
bloco:

* **Bloco 0** — abertura + identificação:
    * ``0000`` — abertura do arquivo (versão leiaute, CNPJ, período).
    * ``0001`` — abertura do bloco 0 (``IND_MOV`` ``0`` = com dados).
    * ``0100`` — dados do contabilista (placeholder mínimo).
    * ``0110`` — regime de apuração (cumulativo + escrituração consolidada).
    * ``0140`` — tabela de cadastro de estabelecimento.
    * ``0150`` — tabela de participantes (clientes + fornecedores únicos).
    * ``0190`` — unidades de medida (apenas ``UN`` no MVP).
    * ``0990`` — encerramento do bloco 0.
* **Bloco A** — operações com **serviços** (NFS-e):
    * ``A001`` — abertura (``IND_MOV`` reflete presença).
    * ``A010`` — identificação do estabelecimento.
    * ``A100`` — cabeçalho de documento (1 por NFS-e do mês).
    * ``A170`` — itens (1 por NFS-e; valores agregados de PIS/Cofins).
    * ``A990`` — encerramento.
* **Bloco C** — operações com **mercadorias** (NF-e modelo 55):
    * ``C001`` — abertura.
    * ``C010`` — estabelecimento.
    * ``C100`` — cabeçalho NF-e (1 por documento).
    * ``C170`` — itens (agregado por NF — granularidade por item fica
      para sprint futura; ver pendência).
    * ``C990`` — encerramento.
* **Bloco D** — serviços de transporte / comunicação (vazio na v1):
    * ``D001`` (``IND_MOV='1'`` = sem dados), ``D990``.
* **Bloco F** — demais documentos e operações (vazio na v1):
    * ``F001`` (``IND_MOV='1'``), ``F990``.
* **Bloco M** — apuração consolidada PIS/Cofins cumulativo:
    * ``M001`` — abertura.
    * ``M200`` — consolidação PIS do período (vlr total + a recolher).
    * ``M400`` — receitas isentas/não tributadas PIS (placeholder vazio).
    * ``M600`` — consolidação Cofins do período.
    * ``M800`` — receitas isentas/não tributadas Cofins (placeholder vazio).
    * ``M990`` — encerramento.
* **Bloco 1** — operações especiais (vazio na v1):
    * ``1001`` (``IND_MOV='1'``), ``1990``.
* **Bloco 9** — controle (computado por ``compartilhado.gerar_bloco_9``).

**Fora de escopo do PR1 (declarado §8.11):**

* Regime **não-cumulativo** (Lucro Real) — `0110.COD_INC_TRIB='2'` e bloco
  M100/M500 com créditos; deixa para iteração futura.
* Bloco **I** (instituições financeiras) e **P** (folha PIS R$10 mil).
* Granularidade por item de NF-e (C175 detalhado, NCM por linha).
* Retenções de PIS/Cofins na fonte (PJ→PJ) — sprint dedicada com
  EFD-Reinf (Sprint 11 já entregou Reinf; integração com EFD-Contrib
  fica para sprint posterior).

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

ALGORITMO_VERSAO = "sped.efd_contribuicoes.v3"
# Sprint 19.8 PR1 bump v2→v3 — adiciona stubs explícitos dos blocos I, P
# e D (entrada faltava). Sem mudanças funcionais quando ``itens`` e
# retenções vêm zerados.
#
# Sprint 19.7 PR3 bump v1→v2:
#   * #26 — granularidade por item em C170 quando ``DocumentoMercadoriaEfd.itens``
#     vem populado (default mantém o agregado v1 — backward-compat).
#   * #28 — retenções PJ→PJ na fonte: A100 emite VL_PIS_RET/VL_COFINS_RET
#     reais (v1 emitia ``d.valor_total`` placeholder, valor inválido).

# Versão do leiaute EFD-Contribuições — ADE Cofis 78/2024 publica a v1.36
# vigente a partir das competências 2024+. Atualizar junto com bump de
# ALGORITMO_VERSAO quando RFB publicar nova versão.
_LEIAUTE_VERSAO = "006"  # COD_VER do registro 0000

# Tipo de escrituração (registro 0000):
#   "0" = original | "1" = retificadora
_TIPO_ESCRITURACAO_ORIGINAL = "0"

# Indicador da natureza da pessoa jurídica (0000):
#   "00" = PJ em geral | "01" = SCP | "02" = entidade imune/isenta
_IND_NAT_PJ_GERAL = "00"

# Indicador do tipo de atividade preponderante (0000):
#   "0" = industrial / equiparado | "1" = comércio | "2" = serviços
#   "3" = atividade financeira | "4" = imobiliária | "9" = outras
_IND_ATIV_DEFAULT = "1"  # comércio

# Indicador de movimento dos blocos sem dados (0001/X001):
#   "0" = bloco com dados | "1" = bloco sem dados
_IND_MOV_COM_DADOS = "0"
_IND_MOV_SEM_DADOS = "1"

# Código de incidência tributária PIS/Cofins (registro 0110):
#   "1" = exclusivamente no regime não-cumulativo
#   "2" = exclusivamente no regime cumulativo
#   "3" = regimes não-cumulativo e cumulativo simultaneamente
_COD_INC_TRIB_CUMULATIVO = "2"

# Indicador do método de apropriação dos créditos (0110) — só relevante
# em não-cumulativo, mas o registro exige preenchimento:
#   "1" = apropriação direta | "2" = rateio proporcional (receita bruta)
_IND_APRO_CRED_NA_CUMULATIVO = ""

# Código do tipo de contribuição apurada (0110):
#   "1" = apuração da contribuição exclusivamente a alíquota básica
#   "2" = apuração da contribuição a alíquotas específicas
_COD_TIPO_CONT_BASICA = "1"

# Indicador de regime de caixa/competência (0110):
#   "1" = regime de caixa | "2" = regime de competência
_IND_REG_CUM_COMPETENCIA = "2"

# Indicador de modelo do documento fiscal (A100/C100):
#   "55" = NF-e modelo 55 | "65" = NFC-e | "01" = NF avulsa
#   "99" = NFS-e (no bloco A vai como string vazia + COD_SIT)
_MODELO_NFE = "55"
_MODELO_NFCE = "65"

# Situação do documento (A100/C100):
#   "00" = autorizado | "02" = cancelado | "06" = denegado
_COD_SIT_AUTORIZADO = "00"

# Indicador do tipo de operação (A100/C100):
#   "0" = entrada | "1" = saída
_IND_OPER_ENTRADA = "0"
_IND_OPER_SAIDA = "1"

# Indicador do emitente do documento (A100/C100):
#   "0" = emissão própria | "1" = terceiros
_IND_EMIT_PROPRIO = "0"
_IND_EMIT_TERCEIROS = "1"

# CST PIS/Cofins padrão para regime cumulativo (registros A170/C170/M-*):
#   "01" = operação tributável com alíquota básica
#   "06" = alíquota zero
#   "07" = isenta
#   "08" = sem incidência
#   "09" = suspensão
_CST_CUMULATIVO_TRIBUTAVEL = "01"

_ZERO = Decimal("0")


# ── DTOs de entrada ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdentificacaoEmpresaEfd:
    """Dados cadastrais para os registros 0000/0100/0140."""

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
    ind_ativ: str = _IND_ATIV_DEFAULT


@dataclass(frozen=True, slots=True)
class ParticipanteEfd:
    """Cliente ou fornecedor referenciado por documento fiscal (``0150``)."""

    codigo: str  # ID interno único na escrituração (CNPJ ou CPF é prático)
    nome: str
    pais: str = "01058"  # Brasil (tabela RFB)
    cnpj: str | None = None
    cpf: str | None = None
    inscricao_estadual: str | None = None
    municipio_ibge: str | None = None
    endereco: str | None = None


@dataclass(frozen=True, slots=True)
class ItemMercadoriaEfd:
    """Linha C170 individual — granularidade por item (Sprint 19.7 PR3 #26).

    Mapeia 1:1 contra ``documento_fiscal_item`` (Sprint 18 PR1). Quando
    ``DocumentoMercadoriaEfd.itens`` vem populado, o gerador emite **um
    C170 por item** preservando NCM/CFOP/CST por linha em vez de
    colapsar tudo num agregado ``MERC-GENERICO``.
    """

    n_item: int
    codigo_produto: str
    descricao: str
    quantidade: Decimal
    unidade: str  # ex: "UN", "KG"
    valor_total: Decimal
    valor_pis: Decimal
    valor_cofins: Decimal
    aliquota_pis: Decimal
    aliquota_cofins: Decimal
    cfop: str  # 4 dígitos — pode diferir do CFOP do cabeçalho
    ncm: str | None = None  # 8 dígitos
    cst_pis: str = _CST_CUMULATIVO_TRIBUTAVEL
    cst_cofins: str = _CST_CUMULATIVO_TRIBUTAVEL


@dataclass(frozen=True, slots=True)
class DocumentoServicoEfd:
    """Documento de serviço (NFS-e) → bloco A.

    Valores agregados no documento — granularidade por item fica para
    iteração futura. ``valor_pis`` / ``valor_cofins`` são o tributo
    destacado (apurado sobre a base do próprio doc).

    Sprint 19.7 PR3 (#28) — retenção PJ→PJ na fonte: novos campos
    ``valor_pis_retido_fonte`` / ``valor_cofins_retido_fonte`` (default
    ``Decimal('0')``) entram no A100 como ``VL_PIS_RET`` /
    ``VL_COFINS_RET``. Esses valores vêm de ``efd_reinf_evento``
    (R-4020 — Sprint 11 PR2): quando a empresa toma serviço de outra
    PJ sujeita a retenção, o tomador retém na fonte e recolhe via
    DARF; o prestador escritura o valor recebido líquido + a retenção
    sofrida.
    """

    chave: str | None  # chave 50 dígitos para NFS-e padrão ABRASF
    numero: str
    serie: str
    data_emissao: date
    codigo_participante: str  # FK lógico em ``ParticipanteEfd.codigo``
    valor_total: Decimal
    valor_servicos: Decimal  # base de cálculo para PIS/Cofins
    valor_pis: Decimal
    valor_cofins: Decimal
    aliquota_pis: Decimal  # ex: Decimal("0.65") = 0,65%
    aliquota_cofins: Decimal  # ex: Decimal("3.00") = 3,00%
    cancelado: bool = False
    cst_pis: str = _CST_CUMULATIVO_TRIBUTAVEL
    cst_cofins: str = _CST_CUMULATIVO_TRIBUTAVEL
    indicador_operacao: str = _IND_OPER_SAIDA
    # Sprint 19.7 PR3 #28 — retenções na fonte PJ→PJ.
    valor_pis_retido_fonte: Decimal = _ZERO
    valor_cofins_retido_fonte: Decimal = _ZERO
    # CSRF (CSLL+PIS+COFINS retidos consolidados — alíquota 4,65% PJ
    # contratante recolhe via DARF 5952). Quando aplicado individualmente,
    # cair em PIS/COFINS_retido_fonte específicos é mais comum em LP.
    valor_csll_retido_fonte: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class DocumentoMercadoriaEfd:
    """Documento de mercadoria (NF-e modelo 55 / NFC-e 65) → bloco C.

    Sprint 19.7 PR3 (#26) — granularidade por item via ``itens``. Quando
    a tupla vem populada (default vazia preserva backward-compat), o
    gerador emite um C170 por item com NCM/CFOP/CST reais; quando vazia,
    o gerador cai no comportamento v1 ("1 agregado por documento", CFOP
    do cabeçalho).
    """

    chave: str  # chave 44 dígitos
    numero: str
    serie: str
    modelo: str  # "55" ou "65"
    data_emissao: date
    codigo_participante: str
    valor_total: Decimal
    valor_mercadorias: Decimal  # base PIS/Cofins
    valor_pis: Decimal
    valor_cofins: Decimal
    aliquota_pis: Decimal
    aliquota_cofins: Decimal
    cfop: str  # 4 dígitos
    ncm: str | None = None  # 8 dígitos quando aplicável
    cst_pis: str = _CST_CUMULATIVO_TRIBUTAVEL
    cst_cofins: str = _CST_CUMULATIVO_TRIBUTAVEL
    indicador_operacao: str = _IND_OPER_SAIDA
    indicador_emitente: str = _IND_EMIT_PROPRIO
    cancelado: bool = False
    # Sprint 19.7 PR3 #26 — granularidade item-a-item.
    itens: Sequence[ItemMercadoriaEfd] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ApuracaoMensalPisCofins:
    """Snapshot do bloco M para o período.

    Valores já vêm somados da apuração persistida em ``apuracao_fiscal``
    (Sprint 11 PR1 — ``lp.pis.cumulativo.v1`` / ``lp.cofins.cumulativo.v1``).
    """

    base_calculo_pis: Decimal
    aliquota_pis: Decimal  # 0,65% como 0.65 (NÃO 0.0065 — RFB usa formato %)
    valor_pis_apurado: Decimal
    valor_pis_a_recolher: Decimal
    base_calculo_cofins: Decimal
    aliquota_cofins: Decimal  # 3,00% como 3.00
    valor_cofins_apurado: Decimal
    valor_cofins_a_recolher: Decimal


@dataclass(frozen=True, slots=True)
class EntradaEfdContribuicoes:
    """Snapshot completo para gerar a EFD-Contribuições do mês.

    Construído pelo service a partir de:

    * ``EmpresaRepo`` → identificação
    * ``DocumentosParaEfdRepo`` → NF-e / NFC-e / NFS-e do período
    * ``ApuracoesPisCofinsRepo`` → totais PIS + Cofins consolidados
    """

    empresa: IdentificacaoEmpresaEfd
    competencia_inicio: date  # 1º dia do mês
    competencia_fim: date  # último dia do mês
    apuracao: ApuracaoMensalPisCofins
    participantes: Sequence[ParticipanteEfd] = field(default_factory=tuple)
    servicos: Sequence[DocumentoServicoEfd] = field(default_factory=tuple)
    mercadorias: Sequence[DocumentoMercadoriaEfd] = field(default_factory=tuple)
    tipo_escrituracao: str = _TIPO_ESCRITURACAO_ORIGINAL
    cod_finalidade: str = "0"  # 0=original 1=retificadora
    nome_contabilista: str = ""
    cnpj_contabilista: str | None = None
    crc_contabilista: str | None = None
    email_contabilista: str | None = None


@dataclass(frozen=True, slots=True)
class ArquivoEfdContribuicoesGerado:
    """Saída do gerador — bytes + hash + metadados."""

    conteudo: bytes
    hash_sha256: str
    tamanho_bytes: int
    total_linhas: int
    leiaute_versao: str = _LEIAUTE_VERSAO
    algoritmo_versao: str = ALGORITMO_VERSAO


# ── Erros internos do gerador (puros) ───────────────────────────────────────


class _EntradaEfdInvalida(ValueError):
    """Falha de pré-condição na entrada — antes de qualquer linha gerada."""


# ── Validação de pré-condições ───────────────────────────────────────────────


def _validar_entrada(entrada: EntradaEfdContribuicoes) -> None:
    """Falha cedo em invariantes do leiaute para não gerar arquivo torto."""
    e = entrada.empresa
    if len(e.cnpj) != 14 or not e.cnpj.isdigit():
        raise _EntradaEfdInvalida(
            "CNPJ deve ter 14 dígitos (somente números) para o registro 0000."
        )
    if len(e.codigo_municipio_ibge) != 7:
        raise _EntradaEfdInvalida(
            "Código IBGE do município deve ter 7 dígitos (registro 0140)."
        )
    if entrada.competencia_fim < entrada.competencia_inicio:
        raise _EntradaEfdInvalida(
            "competencia_fim deve ser ≥ competencia_inicio (registro 0000)."
        )
    if (
        entrada.competencia_inicio.year != entrada.competencia_fim.year
        or entrada.competencia_inicio.month != entrada.competencia_fim.month
    ):
        raise _EntradaEfdInvalida(
            "EFD-Contribuições é mensal: competencia_inicio e "
            "competencia_fim devem ser do mesmo mês civil."
        )
    # Participantes referenciados por documentos devem existir em 0150.
    cods = {p.codigo for p in entrada.participantes}
    for serv in entrada.servicos:
        if serv.codigo_participante not in cods:
            raise _EntradaEfdInvalida(
                f"Documento de serviço {serv.numero}/{serv.serie} referencia "
                f"participante {serv.codigo_participante} ausente do 0150."
            )
    for merc in entrada.mercadorias:
        if merc.codigo_participante not in cods:
            raise _EntradaEfdInvalida(
                f"NF-e {merc.chave} referencia participante "
                f"{merc.codigo_participante} ausente do 0150."
            )
        # CFOP de 4 dígitos numéricos.
        if len(merc.cfop) != 4 or not merc.cfop.isdigit():
            raise _EntradaEfdInvalida(
                f"CFOP inválido em NF-e {merc.chave}: {merc.cfop!r}"
            )
        # Sprint 19.7 PR3 (#26) — valida CFOP de cada item quando granular.
        for it in merc.itens:
            if len(it.cfop) != 4 or not it.cfop.isdigit():
                raise _EntradaEfdInvalida(
                    f"CFOP inválido em item {it.n_item} de NF-e "
                    f"{merc.chave}: {it.cfop!r}"
                )
            if it.quantidade <= _ZERO:
                raise _EntradaEfdInvalida(
                    f"Item {it.n_item} de NF-e {merc.chave} com "
                    f"quantidade ≤ 0: {it.quantidade}"
                )


# ── Geração por bloco ────────────────────────────────────────────────────────


def _gerar_bloco_0(entrada: EntradaEfdContribuicoes) -> list[str]:
    e = entrada.empresa
    out: list[str] = []
    # 0000 — abertura do arquivo.
    out.append(
        linha(
            "0000",
            _LEIAUTE_VERSAO,
            entrada.tipo_escrituracao,
            entrada.cod_finalidade,
            entrada.competencia_inicio,
            entrada.competencia_fim,
            e.razao_social,
            e.cnpj,
            e.uf,
            e.codigo_municipio_ibge,
            e.inscricao_estadual or "",
            _IND_NAT_PJ_GERAL,
            e.ind_ativ,
        )
    )
    # 0001 — abertura do bloco 0 (com dados — sempre há 0140/0150 mínimos).
    out.append(linha("0001", _IND_MOV_COM_DADOS))
    # 0100 — dados do contabilista (campos mínimos; sem CRC opcional).
    out.append(
        linha(
            "0100",
            entrada.nome_contabilista or e.razao_social,
            entrada.cnpj_contabilista or "",
            entrada.crc_contabilista or "",
            entrada.cnpj_contabilista or "",
            e.cep or "",
            "",  # END (logradouro — placeholder)
            "",  # NUM
            "",  # COMPL
            "",  # BAIRRO
            e.telefone or "",
            "",  # FAX
            entrada.email_contabilista or e.email or "",
            e.codigo_municipio_ibge,
        )
    )
    # 0110 — regime de apuração (cumulativo + competência).
    out.append(
        linha(
            "0110",
            _COD_INC_TRIB_CUMULATIVO,
            _IND_APRO_CRED_NA_CUMULATIVO,
            _COD_TIPO_CONT_BASICA,
            _IND_REG_CUM_COMPETENCIA,
        )
    )
    # 0140 — cadastro do estabelecimento (uma matriz no MVP).
    out.append(
        linha(
            "0140",
            "001",  # COD_EST sequencial (matriz)
            e.nome_fantasia or e.razao_social,
            e.cnpj,
            e.uf,
            e.inscricao_estadual or "",
            e.codigo_municipio_ibge,
            e.inscricao_municipal or "",
            "",  # SUFRAMA
        )
    )
    # 0150 — participantes (clientes + fornecedores).
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
    # 0190 — unidade de medida padrão (UN).
    out.append(linha("0190", "UN", "UNIDADE"))
    # 0990 — encerramento do bloco 0.
    out.append(linha("0990", len(out) + 1))
    return out


def _gerar_bloco_a(entrada: EntradaEfdContribuicoes) -> list[str]:
    """Bloco A — operações com **serviços** (NFS-e)."""
    out: list[str] = []
    tem_dados = bool(entrada.servicos)
    # A001 — abertura.
    out.append(
        linha(
            "A001",
            _IND_MOV_COM_DADOS if tem_dados else _IND_MOV_SEM_DADOS,
        )
    )
    if tem_dados:
        e = entrada.empresa
        # A010 — identificação do estabelecimento (CNPJ matriz).
        out.append(linha("A010", e.cnpj))
        for d in entrada.servicos:
            # A100 — cabeçalho NFS-e.
            cod_sit = "02" if d.cancelado else _COD_SIT_AUTORIZADO
            out.append(
                linha(
                    "A100",
                    d.indicador_operacao,
                    _IND_EMIT_PROPRIO,
                    d.codigo_participante,
                    "99",  # COD_SIT_DOC NFS-e (genérico)
                    "",  # SER
                    d.serie,
                    "",  # SUB
                    d.numero,
                    d.chave or "",
                    d.data_emissao,
                    d.data_emissao,  # DT_EXE_SERV (assumimos = emissão)
                    d.valor_total,
                    cod_sit,
                    "",  # CHV_NFSE_RPS — opcional
                    d.valor_servicos,  # VL_BC_PIS
                    d.valor_pis,
                    d.valor_servicos,  # VL_BC_COFINS
                    d.valor_cofins,
                    # Sprint 19.7 PR3 (#28) — retenções reais PJ→PJ
                    # vindas de R-4020 (EFD-Reinf). v1 emitia valor_total
                    # como placeholder, valor inválido para a RFB.
                    d.valor_pis_retido_fonte,    # VL_PIS_RET
                    d.valor_cofins_retido_fonte,  # VL_COFINS_RET
                    d.valor_csll_retido_fonte,    # VL_CSLL_RET
                )
            )
            # A170 — itens do documento (1 agregado por NFS-e na v1).
            out.append(
                linha(
                    "A170",
                    "1",  # NUM_ITEM
                    "SVC-GENERICO",  # COD_ITEM (placeholder)
                    d.numero,  # DESCR_COMPL
                    d.valor_servicos,
                    "0",  # VL_DESC
                    "0",  # NAT_BC_CRED — não aplicável em cumulativo
                    "0",  # IND_ORIG_CRED — não aplicável
                    d.cst_pis,
                    d.valor_servicos,
                    d.aliquota_pis,
                    d.valor_pis,
                    d.cst_cofins,
                    d.valor_servicos,
                    d.aliquota_cofins,
                    d.valor_cofins,
                    "",  # COD_CTA — sem amarração contábil
                )
            )
    # A990 — encerramento.
    out.append(linha("A990", len(out) + 1))
    return out


def _gerar_bloco_c(entrada: EntradaEfdContribuicoes) -> list[str]:
    """Bloco C — operações com **mercadorias** (NF-e/NFC-e)."""
    out: list[str] = []
    tem_dados = bool(entrada.mercadorias)
    # C001 — abertura.
    out.append(
        linha(
            "C001",
            _IND_MOV_COM_DADOS if tem_dados else _IND_MOV_SEM_DADOS,
        )
    )
    if tem_dados:
        e = entrada.empresa
        # C010 — identificação do estabelecimento.
        out.append(linha("C010", e.cnpj, "0"))
        for d in entrada.mercadorias:
            cod_sit = "02" if d.cancelado else _COD_SIT_AUTORIZADO
            # C100 — cabeçalho NF-e/NFC-e.
            out.append(
                linha(
                    "C100",
                    d.indicador_operacao,
                    d.indicador_emitente,
                    d.codigo_participante,
                    d.modelo,
                    cod_sit,
                    d.serie,
                    d.numero,
                    d.chave,
                    d.data_emissao,
                    d.data_emissao,  # DT_E_S (mesma data)
                    d.valor_total,
                    "0",  # IND_PGTO (0 = à vista)
                    "0",  # VL_DESC
                    "0",  # VL_ABAT_NT
                    d.valor_mercadorias,  # VL_MERC
                    "0",  # IND_FRT
                    "0",  # VL_FRT
                    "0",  # VL_SEG
                    "0",  # VL_OUT_DA
                    "0",  # VL_BC_ICMS
                    "0",  # VL_ICMS — bloco específico de PIS/Cofins não acumula ICMS aqui
                    "0",  # VL_BC_ICMS_ST
                    "0",  # VL_ICMS_ST
                    "0",  # VL_IPI
                    d.valor_mercadorias,  # VL_PIS (base)
                    d.valor_mercadorias,  # VL_COFINS (base)
                )
            )
            # C170 — itens do documento.
            # Sprint 19.7 PR3 (#26): se ``d.itens`` está populado, emite
            # um C170 por item preservando NCM/CFOP/CST reais. Caso
            # contrário, fall-back para o "1 agregado" da v1 (compat).
            if d.itens:
                for it in d.itens:
                    out.append(
                        linha(
                            "C170",
                            it.n_item,
                            it.codigo_produto,
                            it.descricao,
                            it.quantidade,
                            it.unidade,
                            it.valor_total,  # VL_ITEM
                            "0",  # VL_DESC
                            "N",  # IND_MOV
                            "00",  # CST_ICMS (genérico em bloco PIS/Cofins)
                            it.cfop,
                            "0",  # COD_NAT
                            "0", "0", "0",      # VL_BC_ICMS / ALIQ / VL_ICMS
                            "0", "0", "0",      # ST trio
                            "N",                # IND_APUR
                            "00",               # CST_IPI
                            "",                 # COD_ENQ
                            "0", "0", "0",      # VL_BC_IPI / ALIQ / VL_IPI
                            it.cst_pis,
                            it.valor_total,     # VL_BC_PIS
                            it.aliquota_pis,
                            "0", "0",
                            it.valor_pis,
                            it.cst_cofins,
                            it.valor_total,     # VL_BC_COFINS
                            it.aliquota_cofins,
                            "0", "0",
                            it.valor_cofins,
                            "",                 # COD_CTA
                        )
                    )
            else:
                out.append(
                    linha(
                        "C170",
                        "1",  # NUM_ITEM
                        "MERC-GENERICO",  # COD_ITEM
                        d.numero,  # DESCR_COMPL
                        "1",  # QTD
                        "UN",  # UNID
                        d.valor_mercadorias,  # VL_ITEM
                        "0",  # VL_DESC
                        "N",  # IND_MOV
                        "00",  # CST_ICMS
                        d.cfop,
                        "0",  # COD_NAT
                        "0", "0", "0",
                        "0", "0", "0",
                        "N",
                        "00",
                        "",
                        "0", "0", "0",
                        d.cst_pis,
                        d.valor_mercadorias,
                        d.aliquota_pis,
                        "0", "0",
                        d.valor_pis,
                        d.cst_cofins,
                        d.valor_mercadorias,
                        d.aliquota_cofins,
                        "0", "0",
                        d.valor_cofins,
                        "",
                    )
                )
    # C990 — encerramento.
    out.append(linha("C990", len(out) + 1))
    return out


def _gerar_bloco_vazio(prefixo: str) -> list[str]:
    """Bloco com apenas abertura ``X001`` (IND_MOV=1) + encerramento ``X990``."""
    out: list[str] = []
    out.append(linha(f"{prefixo}001", _IND_MOV_SEM_DADOS))
    out.append(linha(f"{prefixo}990", len(out) + 1))
    return out


def _gerar_bloco_m(entrada: EntradaEfdContribuicoes) -> list[str]:
    """Bloco M — consolidação PIS/Cofins (regime cumulativo)."""
    out: list[str] = []
    # M001 — abertura (sempre com dados — apuração mensal é obrigatória).
    out.append(linha("M001", _IND_MOV_COM_DADOS))

    ap = entrada.apuracao
    # M200 — consolidação PIS do período.
    out.append(
        linha(
            "M200",
            ap.valor_pis_apurado,  # VL_TOT_CONT_NC_PER (zero em cumulativo)
            _ZERO,  # VL_TOT_CRED_DESC
            _ZERO,  # VL_TOT_CRED_DESC_ANT
            ap.valor_pis_apurado,  # VL_TOT_CONT_NC_DEV
            _ZERO,  # VL_RET_NC
            ap.valor_pis_a_recolher,  # VL_OUT_DED_NC
            ap.valor_pis_a_recolher,  # VL_CONT_NC_REC
            ap.valor_pis_apurado,  # VL_TOT_CONT_CUM_PER
            _ZERO,  # VL_RET_CUM
            _ZERO,  # VL_OUT_DED_CUM
            ap.valor_pis_a_recolher,  # VL_CONT_CUM_REC
            ap.valor_pis_a_recolher,  # VL_TOT_CONT_REC
        )
    )
    # M400 — receitas isentas/não tributadas PIS (placeholder vazio).
    out.append(
        linha(
            "M400",
            "04",  # CST_PIS (04 = alíquota zero — placeholder isenta)
            _ZERO,  # VL_TOT_REC
            "",  # COD_CTA
            "",  # DESC_COMPL
        )
    )
    # M600 — consolidação Cofins do período (mesmo layout que M200).
    out.append(
        linha(
            "M600",
            ap.valor_cofins_apurado,
            _ZERO,
            _ZERO,
            ap.valor_cofins_apurado,
            _ZERO,
            ap.valor_cofins_a_recolher,
            ap.valor_cofins_a_recolher,
            ap.valor_cofins_apurado,
            _ZERO,
            _ZERO,
            ap.valor_cofins_a_recolher,
            ap.valor_cofins_a_recolher,
        )
    )
    # M800 — receitas isentas/não tributadas Cofins (placeholder vazio).
    out.append(
        linha(
            "M800",
            "04",
            _ZERO,
            "",
            "",
        )
    )
    # M990 — encerramento.
    out.append(linha("M990", len(out) + 1))
    return out


# ── API pública ──────────────────────────────────────────────────────────────


def gerar_efd_contribuicoes(
    entrada: EntradaEfdContribuicoes,
) -> ArquivoEfdContribuicoesGerado:
    """Gera o arquivo EFD-Contribuições mensal completo.

    Pipeline:

    1. Valida pré-condições (CNPJ, IBGE, mês civil, participantes, CFOP).
    2. Gera blocos 0, A, C, D (vazio), F (vazio), M, 1 (vazio).
    3. Gera bloco 9 com totalizadores reais (via ``gerar_bloco_9``).
    4. Codifica em ``latin-1`` e calcula SHA-256.

    Raises:
        _EntradaEfdInvalida: para qualquer falha de pré-condição. O service
            traduz para ``SemDadosParaSped`` / ``ValueError`` conforme a
            causa.
    """
    _validar_entrada(entrada)

    linhas: list[str] = []
    linhas.extend(_gerar_bloco_0(entrada))
    linhas.extend(_gerar_bloco_a(entrada))
    linhas.extend(_gerar_bloco_c(entrada))
    # Sprint 19.8 PR1 (#29) — Bloco D (CT-e/MDF-e/DCE) stub IND_MOV=1
    # até cliente com transporte/comunicação aparecer. Trigger no runbook.
    linhas.extend(_gerar_bloco_vazio("D"))
    linhas.extend(_gerar_bloco_vazio("F"))
    linhas.extend(_gerar_bloco_m(entrada))
    # Sprint 19.8 PR1 (#27) — Bloco I (instituições financeiras) e Bloco P
    # (PIS sobre folha — entidades imunes/isentas com faturamento R$10k/mês)
    # ficam stubs até primeiro cliente desses perfis. Layout do leiaute
    # exige bloco abertura+encerramento mesmo quando sem dados.
    linhas.extend(_gerar_bloco_vazio("I"))
    linhas.extend(_gerar_bloco_vazio("P"))
    linhas.extend(_gerar_bloco_vazio("1"))
    linhas.extend(gerar_bloco_9(linhas))

    conteudo = montar_arquivo(linhas)
    return ArquivoEfdContribuicoesGerado(
        conteudo=conteudo,
        hash_sha256=calcular_hash_sha256(conteudo),
        tamanho_bytes=len(conteudo),
        total_linhas=len(linhas),
    )
