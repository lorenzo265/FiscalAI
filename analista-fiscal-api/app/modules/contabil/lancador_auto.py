"""Motor de lançamentos contábeis automáticos (Sprint 9 PR2).

Zero I/O. Determinístico. Converte um *fato persistido* (NF, transação
bancária, depreciação, provisão) em um conjunto de partidas dobradas
prontas para virar :class:`LancamentoContabil`.

Conversões cobertas:

  ┌──────────────────┬──────────────────────┬──────────────────────────────┐
  │ Fato             │ Débito               │ Crédito                      │
  ├──────────────────┼──────────────────────┼──────────────────────────────┤
  │ NF saída         │ Clientes             │ Receita Serviços/Vendas      │
  │ NF entrada       │ Outras Despesas      │ Fornecedores                 │
  │ Trans. CREDIT    │ Banco                │ Outras Receitas              │
  │ Trans. DEBIT     │ Outras Despesas      │ Banco                        │
  │ Depreciação      │ Despesa Depreciação  │ Depreciação Acumulada        │
  │ Provisão férias  │ Despesa com Pessoal  │ Provisão de Férias           │
  │ Provisão 13      │ Despesa com Pessoal  │ Provisão 13º Salário         │
  │ INSS provisão    │ Encargos Sociais     │ INSS a Recolher              │
  │ FGTS provisão    │ Encargos Sociais     │ FGTS a Recolher              │
  └──────────────────┴──────────────────────┴──────────────────────────────┘

Linhas de provisão com ``valor=0`` (SN/MEI sem INSS) são puladas — não viram
lançamento (não há fato contábil).

Princípio §8.8 — LLM nunca escreve fato. Aqui é Python puro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal
from uuid import UUID

from app.modules.contabil.classificador_cfop import (
    classificar_conta_debito_entrada,
)

ALGORITMO_VERSAO = "lancador-auto-2026.07"
# Sprint 19.7 PR4 (#6) — quando transação CONFIRMED tem match com NF
# (``ConciliacaoMatch`` em status AUTO/MANUAL), `gerar_partidas_de_transacao`
# substitui a contra-partida genérica (`outras_receitas`/`outras_despesas`)
# por baixa de duplicata: CREDIT × NF saída → C `clientes`; DEBIT × NF
# entrada → D `fornecedores`. Sem match, comportamento v06 preservado.

ALGORITMO_VERSAO_IMPOSTOS = "lancador-impostos-2026.01"
# Sprint (lançador de impostos) — ApuracaoFiscal → LancamentoContabil.
# Fecha o ciclo: imposto calculado → passivo fiscal (2.1.4.x) + despesa
# (5.1.05 Impostos sobre Receita ou 5.3.01 Provisão IRPJ/CSLL).


# ── Views imutáveis dos fatos ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class NfFatoView:
    """Subset de ``DocumentoFiscal``."""

    id: UUID
    tipo: str  # 'nfe' | 'nfse' | etc.
    direcao: Literal["saida", "entrada"]
    valor_total: Decimal
    emitida_em: datetime
    numero: str
    cfop: str | None = None  # usado pelo classificador na NF entrada


@dataclass(frozen=True, slots=True)
class MatchDocumentoFatoView:
    """Match conciliação consumido pelo lançamento (Sprint 19.7 PR4 #6).

    Subset de ``ConciliacaoMatch`` + dados da NF casada — suficiente
    pro lançador escolher a contra-partida correta sem importar o
    módulo de conciliação (evita ciclo).
    """

    documento_id: UUID
    documento_tipo: Literal["nfe", "nfse"]
    documento_direcao: Literal["saida", "entrada"]
    documento_numero: str


@dataclass(frozen=True, slots=True)
class TransacaoFatoView:
    """Subset de ``TransacaoBancaria`` (somente CONFIRMED)."""

    id: UUID
    valor: Decimal  # signed
    tipo: Literal["CREDIT", "DEBIT"]
    data_transacao: date
    descricao: str | None
    # Sprint 19.7 PR4 (#6) — match conciliação opcional. Quando presente,
    # lançamento substitui contra-partida genérica por baixa de duplicata.
    match: MatchDocumentoFatoView | None = None


@dataclass(frozen=True, slots=True)
class DepreciacaoFatoView:
    """Subset de ``DepreciacaoMensal``."""

    id: UUID
    competencia: date
    valor_depreciado: Decimal


@dataclass(frozen=True, slots=True)
class ProvisaoFatoView:
    """Subset de ``ProvisaoMensal``."""

    id: UUID
    competencia: date
    tipo: str  # ferias|13_salario|inss_ferias|inss_13|fgts_ferias|fgts_13
    valor_provisao: Decimal


@dataclass(frozen=True, slots=True)
class FolhaFatoView:
    """Subset de ``FolhaMensal`` — Sprint 19.7 PR1 (#10).

    Totais consolidados da folha fechada. Algoritmo lê só esses totais
    (não itera holerites individualmente — o consolidado já cumpre o
    fato contábil mensal §8.2).

    Mapeamento ``ProvisaoFatoView`` já cobre encargos sobre férias/13º;
    aqui cobrimos a folha mensal "ordinária" (salários + INSS + IRRF +
    FGTS dos funcionários ativos no mês).
    """

    id: UUID
    competencia: date
    total_proventos: Decimal  # salário bruto consolidado
    total_inss_empregado: Decimal  # retenção empregado (passivo)
    total_irrf: Decimal  # IRRF retido na fonte (passivo)
    total_fgts_empregador: Decimal  # FGTS 8% pago pela empresa (despesa)


# ── Resultado ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PartidaCandidata:
    conta_id: UUID
    tipo: Literal["D", "C"]
    valor: Decimal


@dataclass(frozen=True, slots=True)
class LancamentoCandidato:
    """Resultado: lançamento pronto para persistir."""

    historico: str
    data_lancamento: date
    competencia: date
    origem_tipo: str
    origem_id: UUID
    partidas: tuple[PartidaCandidata, ...] = field(default_factory=tuple)
    versao: str = ALGORITMO_VERSAO

    @property
    def total(self) -> Decimal:
        return sum(
            (p.valor for p in self.partidas if p.tipo == "D"),
            start=Decimal("0"),
        )


# ── Lookup das contas ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ContasAuto:
    """Lookup das contas analíticas que o motor automático usa.

    Mapeia os códigos do plano referencial RFB (CODIGOS_PADRAO_LANCAMENTO_AUTO)
    para os UUIDs das contas reais da empresa. Construído uma vez por lote no
    service, passado às funções puras.
    """

    clientes: UUID
    fornecedores: UUID
    banco: UUID
    receita_servicos: UUID
    receita_vendas: UUID
    outras_receitas: UUID  # fallback para transações bancárias sem match
    outras_despesas: UUID  # NF entrada e transações DEBIT sem match
    despesa_depreciacao: UUID
    depreciacao_acumulada: UUID
    despesa_pessoal: UUID
    encargos_sociais: UUID
    provisao_ferias: UUID
    provisao_13: UUID
    inss_recolher: UUID
    fgts_recolher: UUID
    irrf_funcionarios_recolher: UUID  # Sprint 19.7 PR1 (#10) — IRRF retido folha
    salarios_pagar: UUID  # Sprint 19.7 PR1 (#10) — passivo "líquido a pagar"
    estoques: UUID  # NF entrada compra-revenda/industrialização
    imobilizado: UUID  # NF entrada bem para ativo imobilizado
    despesa_servicos: UUID  # NF entrada serviço (comunicação, sub-empreitada)

    def conta_por_chave(self, chave: str) -> UUID:
        """Resolve chave de ``CODIGOS_PADRAO_LANCAMENTO_AUTO`` → UUID.

        Usado pelo classificador CFOP para indireção dinâmica. Para chaves
        desconhecidas (futuras), faz fallback explícito em ``outras_despesas``.
        """
        # Mapa estático para evitar getattr() — mantém mypy strict feliz.
        if chave == "estoques":
            return self.estoques
        if chave == "imobilizado":
            return self.imobilizado
        if chave == "despesa_servicos":
            return self.despesa_servicos
        if chave == "outras_despesas":
            return self.outras_despesas
        # Chave nova ou inválida — degrada para fallback determinístico.
        return self.outras_despesas


# ── Conversores puros — um por tipo de fato ─────────────────────────────────


def gerar_partidas_de_nfe(
    nf: NfFatoView, contas: ContasAuto
) -> LancamentoCandidato:
    """NF autorizada → lançamento. Saída = receita; entrada = fornecedor."""
    data = nf.emitida_em.date() if isinstance(nf.emitida_em, datetime) else nf.emitida_em
    competencia = date(data.year, data.month, 1)
    valor = nf.valor_total

    if nf.direcao == "saida":
        # Cliente paga empresa: D Clientes / C Receita
        conta_receita = (
            contas.receita_servicos if nf.tipo.lower() == "nfse" else contas.receita_vendas
        )
        partidas = (
            PartidaCandidata(conta_id=contas.clientes, tipo="D", valor=valor),
            PartidaCandidata(conta_id=conta_receita, tipo="C", valor=valor),
        )
        historico = f"Receita NF {nf.numero} (NF saída)"
    else:
        # Empresa compra: D <classificado por CFOP> / C Fornecedor.
        # Classificador determinístico — fallback explícito em "outras_despesas".
        chave_debito = classificar_conta_debito_entrada(nf.cfop)
        conta_debito = contas.conta_por_chave(chave_debito)
        partidas = (
            PartidaCandidata(conta_id=conta_debito, tipo="D", valor=valor),
            PartidaCandidata(conta_id=contas.fornecedores, tipo="C", valor=valor),
        )
        sufixo = f" ({chave_debito})" if chave_debito != "outras_despesas" else ""
        historico = f"NF entrada {nf.numero}{sufixo}"

    return LancamentoCandidato(
        historico=historico,
        data_lancamento=data,
        competencia=competencia,
        origem_tipo="nfe",
        origem_id=nf.id,
        partidas=partidas,
    )


def gerar_partidas_de_transacao(
    tx: TransacaoFatoView, contas: ContasAuto
) -> LancamentoCandidato:
    """Transação bancária CONFIRMED → lançamento banco × resultado/duplicata.

    Sprint 19.7 PR4 (#6) — quando ``tx.match`` está preenchido com NF
    casada, contra-partida vira **baixa de duplicata** (não receita/despesa
    diretas — a receita/despesa já foi reconhecida na emissão da NF):

      * CREDIT × NF saída → D Banco / C Clientes (recebimento de cliente).
      * DEBIT × NF entrada → D Fornecedores / C Banco (pagamento a fornecedor).
      * Mismatch direcional (CREDIT × NF entrada, DEBIT × NF saída) cai no
        fluxo sem-match (fallback) — match desses pares é improvável e o
        score do conciliador já filtra a maioria.

    Sem match, comportamento v06 preservado:
      * CREDIT (entrada): D Banco / C Outras Receitas.
      * DEBIT (saída):    D Outras Despesas / C Banco.
    """
    competencia = date(tx.data_transacao.year, tx.data_transacao.month, 1)
    valor_abs = tx.valor.copy_abs()
    descricao_curta = (tx.descricao or "")[:200]

    # Sprint 19.7 PR4 #6 — baixa de duplicata quando match dirige.
    match_baixa = _match_baixa_duplicata(tx)
    if match_baixa is not None and tx.match is not None:
        if tx.tipo == "CREDIT":
            partidas = (
                PartidaCandidata(conta_id=contas.banco, tipo="D", valor=valor_abs),
                PartidaCandidata(conta_id=contas.clientes, tipo="C", valor=valor_abs),
            )
            historico = (
                f"Recebimento NF {tx.match.documento_numero} — {descricao_curta}"
            )
        else:
            partidas = (
                PartidaCandidata(
                    conta_id=contas.fornecedores, tipo="D", valor=valor_abs
                ),
                PartidaCandidata(conta_id=contas.banco, tipo="C", valor=valor_abs),
            )
            historico = (
                f"Pagamento NF {tx.match.documento_numero} — {descricao_curta}"
            )
        return LancamentoCandidato(
            historico=historico,
            data_lancamento=tx.data_transacao,
            competencia=competencia,
            origem_tipo="transacao",
            origem_id=tx.id,
            partidas=partidas,
        )

    # Fluxo sem-match — fallback determinístico (comportamento v06).
    if tx.tipo == "CREDIT":
        partidas = (
            PartidaCandidata(conta_id=contas.banco, tipo="D", valor=valor_abs),
            PartidaCandidata(conta_id=contas.outras_receitas, tipo="C", valor=valor_abs),
        )
        historico = f"Entrada bancária — {descricao_curta}"
    else:
        partidas = (
            PartidaCandidata(conta_id=contas.outras_despesas, tipo="D", valor=valor_abs),
            PartidaCandidata(conta_id=contas.banco, tipo="C", valor=valor_abs),
        )
        historico = f"Saída bancária — {descricao_curta}"

    return LancamentoCandidato(
        historico=historico,
        data_lancamento=tx.data_transacao,
        competencia=competencia,
        origem_tipo="transacao",
        origem_id=tx.id,
        partidas=partidas,
    )


def _match_baixa_duplicata(tx: TransacaoFatoView) -> MatchDocumentoFatoView | None:
    """Retorna o match somente se a direção bate com baixa de duplicata.

    Sprint 19.7 PR4 #6 — guarda direcional pra evitar contas incorretas:
      * CREDIT × NF saída → OK (cliente paga).
      * DEBIT × NF entrada → OK (empresa paga fornecedor).
      * Outras combinações → ``None`` (cai no fluxo sem-match).
    """
    if tx.match is None:
        return None
    if tx.tipo == "CREDIT" and tx.match.documento_direcao == "saida":
        return tx.match
    if tx.tipo == "DEBIT" and tx.match.documento_direcao == "entrada":
        return tx.match
    return None


def gerar_partidas_de_depreciacao(
    depr: DepreciacaoFatoView, contas: ContasAuto
) -> LancamentoCandidato | None:
    """Depreciação mensal → D Despesa / C Depreciação Acumulada.

    Retorna ``None`` se ``valor_depreciado`` for zero (mês sem depreciação real,
    por exemplo o mês da aquisição) — não há fato contábil.
    """
    if depr.valor_depreciado <= Decimal("0"):
        return None

    competencia = date(depr.competencia.year, depr.competencia.month, 1)
    partidas = (
        PartidaCandidata(
            conta_id=contas.despesa_depreciacao,
            tipo="D",
            valor=depr.valor_depreciado,
        ),
        PartidaCandidata(
            conta_id=contas.depreciacao_acumulada,
            tipo="C",
            valor=depr.valor_depreciado,
        ),
    )
    return LancamentoCandidato(
        historico=f"Depreciação mensal {competencia:%Y-%m}",
        data_lancamento=competencia,
        competencia=competencia,
        origem_tipo="depreciacao",
        origem_id=depr.id,
        partidas=partidas,
    )


# Mapa interno: tipo da provisão → (conta débito, conta crédito).
_MAPA_PROVISAO: dict[str, str] = {
    "ferias": "ferias",
    "13_salario": "13",
    "inss_ferias": "inss",
    "inss_13": "inss",
    "fgts_ferias": "fgts",
    "fgts_13": "fgts",
}


def gerar_partidas_de_provisao(
    prov: ProvisaoFatoView, contas: ContasAuto
) -> LancamentoCandidato | None:
    """Provisão trabalhista → lançamento.

    Retorna None quando ``valor_provisao=0`` (SN/MEI com INSS dispensado).

    Mapeamento:
      ferias        → D Despesa Pessoal      / C Provisão de Férias
      13_salario    → D Despesa Pessoal      / C Provisão 13º
      inss_ferias   → D Encargos Sociais     / C INSS a Recolher
      inss_13       → D Encargos Sociais     / C INSS a Recolher
      fgts_ferias   → D Encargos Sociais     / C FGTS a Recolher
      fgts_13       → D Encargos Sociais     / C FGTS a Recolher
    """
    if prov.valor_provisao <= Decimal("0"):
        return None

    competencia = date(prov.competencia.year, prov.competencia.month, 1)
    grupo = _MAPA_PROVISAO.get(prov.tipo)
    if grupo is None:
        return None

    if grupo == "ferias":
        d_conta = contas.despesa_pessoal
        c_conta = contas.provisao_ferias
        historico = f"Provisão de férias {competencia:%Y-%m}"
    elif grupo == "13":
        d_conta = contas.despesa_pessoal
        c_conta = contas.provisao_13
        historico = f"Provisão 13º salário {competencia:%Y-%m}"
    elif grupo == "inss":
        d_conta = contas.encargos_sociais
        c_conta = contas.inss_recolher
        sufixo = "férias" if "ferias" in prov.tipo else "13º"
        historico = f"INSS s/ provisão de {sufixo} {competencia:%Y-%m}"
    else:  # fgts
        d_conta = contas.encargos_sociais
        c_conta = contas.fgts_recolher
        sufixo = "férias" if "ferias" in prov.tipo else "13º"
        historico = f"FGTS s/ provisão de {sufixo} {competencia:%Y-%m}"

    partidas = (
        PartidaCandidata(conta_id=d_conta, tipo="D", valor=prov.valor_provisao),
        PartidaCandidata(conta_id=c_conta, tipo="C", valor=prov.valor_provisao),
    )
    return LancamentoCandidato(
        historico=historico,
        data_lancamento=competencia,
        competencia=competencia,
        origem_tipo="provisao",
        origem_id=prov.id,
        partidas=partidas,
    )


# ── Apuração fiscal → lançamento de imposto ─────────────────────────────────


@dataclass(frozen=True, slots=True)
class ApuracaoFatoView:
    """Subset imutável de ``ApuracaoFiscal`` usado pelo lançador de impostos.

    Criado pelo ``lote_impostos`` após extrair o valor via
    ``_valor_apuracao()``. A extração ocorre no service (que tem I/O);
    este dataclass e a função pura abaixo são zero-I/O e testáveis.
    """

    id: UUID
    competencia: date   # primeiro dia do mês (DATE no banco)
    tipo: str           # das | irpj | csll | pis | cofins | iss | icms
    valor: Decimal      # valor a recolher, já quantizado (0.01 ROUND_HALF_EVEN)


@dataclass(frozen=True, slots=True)
class ContasImpostos:
    """UUIDs das 9 contas analíticas necessárias para o lançador de impostos.

    Resolvidas por ``resolver_contas_impostos()`` no service a partir das
    chaves simbólicas em ``_CHAVES_IMPOSTOS``. Separadas de ``ContasAuto``
    para que a ausência destas contas (empresas antigas) não quebre os
    outros lotes (nfe/transacao/etc.).
    """

    das_recolher: UUID           # 2.1.4.01 DAS Simples Nacional
    icms_recolher: UUID          # 2.1.4.02 ICMS a Recolher
    iss_recolher: UUID           # 2.1.4.03 ISS a Recolher
    pis_recolher: UUID           # 2.1.4.04 PIS a Recolher
    cofins_recolher: UUID        # 2.1.4.05 COFINS a Recolher
    irpj_recolher: UUID          # 2.1.4.06 IRPJ a Recolher
    csll_recolher: UUID          # 2.1.4.07 CSLL a Recolher
    impostos_sobre_receita: UUID # 5.1.05 Impostos sobre Receita (débito)
    provisao_irpj_csll: UUID     # 5.3.01 Provisão IRPJ/CSLL (débito)


# Tipos cujo lançamento é D 5.1.05 / C <passivo>
_TIPOS_IMPOSTOS_RECEITA = frozenset({"das", "icms", "iss", "pis", "cofins"})
# Tipos cujo lançamento é D 5.3.01 / C <passivo>
_TIPOS_PROVISAO_RESULTADO = frozenset({"irpj", "csll"})

_CENTAVO = Decimal("0.01")


def gerar_partidas_de_apuracao(
    ap: ApuracaoFatoView,
    contas: ContasImpostos,
) -> LancamentoCandidato | None:
    """ApuracaoFiscal → lançamento contábil de imposto apurado.

    Mapa débito / crédito:

      das / icms / iss / pis / cofins:
        D 5.1.05 Impostos sobre Receita  /  C 2.1.4.0x <tributo> a Recolher

      irpj / csll:
        D 5.3.01 Provisão IRPJ/CSLL      /  C 2.1.4.06/07 <tributo> a Recolher

      dctf / efd_contrib:
        Retorna None — são declarações acessórias, sem movimento de imposto.

      valor ≤ 0:
        Retorna None — sem imposto a lançar (saldo credor ou base zero).

    Princípio §8.8 — zero I/O, puro Python.

    Args:
        ap: snapshot do fato ApuracaoFiscal já persistido.
        contas: UUIDs resolvidos das 9 contas de imposto.

    Returns:
        LancamentoCandidato pronto para persistência ou None quando não há
        fato contábil (dctf/efd_contrib ou valor ≤ 0).
    """
    # Declarações acessórias — sem movimento de caixa/resultado.
    if ap.tipo in ("dctf", "efd_contrib"):
        return None

    valor = ap.valor.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)
    if valor <= Decimal("0"):
        return None

    competencia = date(ap.competencia.year, ap.competencia.month, 1)
    tipo_upper = ap.tipo.upper()

    # Resolve conta crédito (passivo fiscal) por tipo.
    if ap.tipo == "das":
        conta_credito = contas.das_recolher
    elif ap.tipo == "icms":
        conta_credito = contas.icms_recolher
    elif ap.tipo == "iss":
        conta_credito = contas.iss_recolher
    elif ap.tipo == "pis":
        conta_credito = contas.pis_recolher
    elif ap.tipo == "cofins":
        conta_credito = contas.cofins_recolher
    elif ap.tipo == "irpj":
        conta_credito = contas.irpj_recolher
    elif ap.tipo == "csll":
        conta_credito = contas.csll_recolher
    else:
        # Tipo inesperado não modelado — sem lançamento (defensivo).
        return None

    # Resolve conta débito (despesa/provisão) por grupo.
    if ap.tipo in _TIPOS_IMPOSTOS_RECEITA:
        conta_debito = contas.impostos_sobre_receita
    else:
        # irpj / csll
        conta_debito = contas.provisao_irpj_csll

    comp_str = f"{ap.competencia.year}-{ap.competencia.month:02d}"
    historico = f"{tipo_upper} apurado {comp_str}"

    partidas = (
        PartidaCandidata(conta_id=conta_debito, tipo="D", valor=valor),
        PartidaCandidata(conta_id=conta_credito, tipo="C", valor=valor),
    )
    return LancamentoCandidato(
        historico=historico,
        data_lancamento=competencia,
        competencia=competencia,
        origem_tipo="apuracao",
        origem_id=ap.id,
        partidas=partidas,
        versao=ALGORITMO_VERSAO_IMPOSTOS,
    )


def gerar_partidas_de_folha(
    folha: FolhaFatoView, contas: ContasAuto
) -> LancamentoCandidato | None:
    """Sprint 19.7 PR1 (#10) — folha fechada → lançamento contábil.

    Modelo de partidas (5 partidas):

      D 5.1.02 Despesa com Pessoal       (total_proventos)
        C 2.1.2.01 Salários a Pagar       (líquido a pagar)
        C 2.1.3.01 INSS a Recolher        (INSS retido empregado)
        C 2.1.3.03 IRRF Funcionários a Recolher (IRRF retido)

      D 5.1.03 Encargos Sociais          (FGTS empregador 8%)
        C 2.1.3.02 FGTS a Recolher        (FGTS retido p/ depósito)

    O total dos débitos (Despesa Pessoal + Encargos) = total dos créditos
    (Salários + INSS + IRRF + FGTS). Partidas dobradas §8.4 cravadas.

    ``valor_liquido_pagar = total_proventos - total_inss - total_irrf``.

    Retorna ``None`` se ``total_proventos=0`` (folha sem funcionários
    ativos no mês — sem fato contábil).
    """
    if folha.total_proventos <= Decimal("0"):
        return None

    competencia = date(folha.competencia.year, folha.competencia.month, 1)
    liquido_pagar = (
        folha.total_proventos - folha.total_inss_empregado - folha.total_irrf
    )

    partidas: tuple[PartidaCandidata, ...] = (
        # Bloco 1 — folha bruta = salário líquido + retenções (passivos)
        PartidaCandidata(
            conta_id=contas.despesa_pessoal,
            tipo="D",
            valor=folha.total_proventos,
        ),
        PartidaCandidata(
            conta_id=contas.salarios_pagar,
            tipo="C",
            valor=liquido_pagar,
        ),
        PartidaCandidata(
            conta_id=contas.inss_recolher,
            tipo="C",
            valor=folha.total_inss_empregado,
        ),
        PartidaCandidata(
            conta_id=contas.irrf_funcionarios_recolher,
            tipo="C",
            valor=folha.total_irrf,
        ),
        # Bloco 2 — encargo empregador FGTS
        PartidaCandidata(
            conta_id=contas.encargos_sociais,
            tipo="D",
            valor=folha.total_fgts_empregador,
        ),
        PartidaCandidata(
            conta_id=contas.fgts_recolher,
            tipo="C",
            valor=folha.total_fgts_empregador,
        ),
    )
    historico = f"Folha mensal {competencia:%Y-%m}"
    return LancamentoCandidato(
        historico=historico,
        data_lancamento=competencia,
        competencia=competencia,
        origem_tipo="folha",
        origem_id=folha.id,
        partidas=partidas,
    )
