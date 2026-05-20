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
from decimal import Decimal
from typing import Literal
from uuid import UUID

ALGORITMO_VERSAO = "lancador-auto-2026.05"


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


@dataclass(frozen=True, slots=True)
class TransacaoFatoView:
    """Subset de ``TransacaoBancaria`` (somente CONFIRMED)."""

    id: UUID
    valor: Decimal  # signed
    tipo: Literal["CREDIT", "DEBIT"]
    data_transacao: date
    descricao: str | None


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
        # Empresa compra: D Despesa a classificar / C Fornecedor
        partidas = (
            PartidaCandidata(conta_id=contas.outras_despesas, tipo="D", valor=valor),
            PartidaCandidata(conta_id=contas.fornecedores, tipo="C", valor=valor),
        )
        historico = f"NF entrada {nf.numero}"

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
    """Transação bancária CONFIRMED → lançamento simples banco × resultado.

    CREDIT (entrada): D Banco / C Outras Receitas (fallback — match com NF
    fica para iteração futura via conciliacao_match).
    DEBIT (saída):    D Outras Despesas / C Banco.
    """
    competencia = date(tx.data_transacao.year, tx.data_transacao.month, 1)
    valor_abs = tx.valor.copy_abs()
    descricao_curta = (tx.descricao or "")[:200]

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
