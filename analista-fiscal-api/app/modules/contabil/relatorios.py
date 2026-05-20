"""Funções puras para balancete e razão (Sprint 9 PR3).

Zero I/O. Decimal-safe. Determinístico.

Conceitos:

  Saldo da conta = saldo_inicial + (D total - C total) × sinal_da_natureza
    * Conta de natureza D (Ativo, Despesa): saldo positivo = mais débito que
      crédito. Saldo aumenta com débitos.
    * Conta de natureza C (Passivo, PL, Receita): saldo positivo = mais crédito
      que débito. Saldo aumenta com créditos.

  No balancete tradicional, o saldo é sempre exibido em valor absoluto e
  classificado pela posição (devedor / credor). Aqui usamos signed: saldo
  positivo = posição alinhada à natureza; negativo = inversão (típico em
  contas retificadoras como "Depreciação Acumulada" antes do encerramento
  anual).

  ``consolidar_balancete`` recebe uma lista de movimentações pré-agregadas
  por conta. O caller (service) é responsável pelo SELECT que faz o
  GROUP BY no DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

ALGORITMO_VERSAO = "balancete-2026.05"


@dataclass(frozen=True, slots=True)
class MovimentacaoConta:
    """Agregado de movimentação por conta para um período.

    O caller (service) faz a query SUM agregando ``partida_lancamento``.
    """

    conta_id: object
    codigo: str
    descricao: str
    natureza: str  # 'D' | 'C'
    tipo: str
    nivel: int
    saldo_inicial: Decimal
    total_debitos: Decimal
    total_creditos: Decimal


@dataclass(frozen=True, slots=True)
class LinhaBalancete:
    """Linha do balancete pronta para serializar."""

    conta_id: object
    codigo: str
    descricao: str
    natureza: str
    tipo: str
    nivel: int
    saldo_inicial: Decimal
    total_debitos: Decimal
    total_creditos: Decimal
    saldo_final: Decimal


@dataclass(frozen=True, slots=True)
class LancamentoRazaoView:
    """Lançamento + partida da conta consultada, para razão."""

    lancamento_id: object
    data_lancamento: object  # date
    historico: str
    tipo: str  # 'D' ou 'C' da partida nessa conta
    valor: Decimal


@dataclass(frozen=True, slots=True)
class LinhaRazao:
    """Linha do razão de uma conta — inclui saldo corrente acumulado."""

    lancamento_id: object
    data_lancamento: object
    historico: str
    debito: Decimal
    credito: Decimal
    saldo_corrente: Decimal


# ── consolidar_balancete ────────────────────────────────────────────────────


def calcular_saldo_final(
    natureza: str,
    saldo_inicial: Decimal,
    total_debitos: Decimal,
    total_creditos: Decimal,
) -> Decimal:
    """Saldo final = saldo_inicial + delta_pela_natureza.

    Natureza D: delta = D - C (débitos somam).
    Natureza C: delta = C - D (créditos somam).
    """
    if natureza == "D":
        return saldo_inicial + (total_debitos - total_creditos)
    elif natureza == "C":
        return saldo_inicial + (total_creditos - total_debitos)
    raise ValueError(f"natureza inválida: {natureza!r}")


def consolidar_balancete(
    movimentacoes: list[MovimentacaoConta],
) -> list[LinhaBalancete]:
    """Aplica ``calcular_saldo_final`` a cada conta e ordena por código."""
    linhas = [
        LinhaBalancete(
            conta_id=m.conta_id,
            codigo=m.codigo,
            descricao=m.descricao,
            natureza=m.natureza,
            tipo=m.tipo,
            nivel=m.nivel,
            saldo_inicial=m.saldo_inicial,
            total_debitos=m.total_debitos,
            total_creditos=m.total_creditos,
            saldo_final=calcular_saldo_final(
                m.natureza, m.saldo_inicial, m.total_debitos, m.total_creditos
            ),
        )
        for m in movimentacoes
    ]
    return sorted(linhas, key=lambda l: l.codigo)


# ── consolidar_razao ────────────────────────────────────────────────────────


def consolidar_razao(
    natureza: str,
    saldo_inicial: Decimal,
    lancamentos: list[LancamentoRazaoView],
) -> list[LinhaRazao]:
    """Calcula saldo corrente da conta após cada lançamento.

    A lista deve vir já ordenada por (data_lancamento, criado_em).
    """
    saldo = saldo_inicial
    linhas: list[LinhaRazao] = []
    for lanc in lancamentos:
        if lanc.tipo == "D":
            debito = lanc.valor
            credito = Decimal("0")
            saldo = saldo + lanc.valor if natureza == "D" else saldo - lanc.valor
        else:  # 'C'
            debito = Decimal("0")
            credito = lanc.valor
            saldo = saldo + lanc.valor if natureza == "C" else saldo - lanc.valor

        linhas.append(
            LinhaRazao(
                lancamento_id=lanc.lancamento_id,
                data_lancamento=lanc.data_lancamento,
                historico=lanc.historico,
                debito=debito,
                credito=credito,
                saldo_corrente=saldo,
            )
        )
    return linhas
