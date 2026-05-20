"""Algoritmo puro de pontuação banco × NF (Sprint 7 PR3).

Zero I/O — recebe dataclasses imutáveis e devolve ``ScoreMatch``. Golden-test
friendly. Determinístico — mesmos inputs sempre geram o mesmo score.

Regras (versão ``conc-2026.05``):

  Sinal compatível obrigatório:
    * Transação CREDIT (entrada) ↔ NF direcao='saida' (cliente paga a empresa)
    * Transação DEBIT  (saída)   ↔ NF direcao='entrada' (empresa paga fornecedor)
    Se incompatível, score = 0 e nenhum critério adicional é avaliado.

  Critérios cumulativos quando sinal bate:
    * Valor exato (Δ absoluto ≤ R$ 0,01):  +60
    * Valor próximo (Δ ≤ R$ 5,00):         +30  (mutuamente exclusivo com exato)
    * Data idêntica:                       +25
    * Data ±1 dia:                         +20  (mutuamente exclusivo)
    * Data ±5 dias:                        +10  (mutuamente exclusivo)
    * CNPJ da contraparte na descrição:    +15
    * Diferença de valor > R$ 50:          NÃO pontua nem em "próximo"

  Score final: soma, clampado a [0, 100].

Limiares (no service):
    ≥ 80  → AUTO
    50-79 → SUGERIDA
    <50   → ignorado (não persiste match)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ALGORITMO_VERSAO = "conc-2026.05"

# Limiares de classificação (também usados pelo service).
LIMIAR_AUTO = 80
LIMIAR_SUGERIDA = 50

# Constantes de pontuação.
_PT_VALOR_EXATO = 60
_PT_VALOR_PROXIMO = 30
_PT_DATA_EXATA = 25
_PT_DATA_1_DIA = 20
_PT_DATA_5_DIAS = 10
_PT_CNPJ_DESCRICAO = 15

# Tolerâncias.
_DELTA_VALOR_EXATO = Decimal("0.01")
_DELTA_VALOR_PROXIMO = Decimal("5.00")
_DELTA_VALOR_DIVERGENTE = Decimal("50.00")


@dataclass(frozen=True, slots=True)
class TransacaoView:
    """Subset imutável de ``TransacaoBancaria`` usado pelo algoritmo."""

    id: object
    valor: Decimal  # signed: > 0 entrada, < 0 saída
    tipo: str  # CREDIT | DEBIT
    data_transacao: date
    descricao: str | None


@dataclass(frozen=True, slots=True)
class DocumentoView:
    """Subset imutável de ``DocumentoFiscal`` usado pelo algoritmo."""

    id: object
    direcao: str  # entrada | saida
    valor_total: Decimal
    emitida_em_data: date
    cnpj_emitente: str
    cnpj_destinatario: str | None


@dataclass(frozen=True, slots=True)
class ScoreMatch:
    """Resultado da pontuação — inclui breakdown auditável."""

    pontos: int
    breakdown: list[str] = field(default_factory=list)
    sinal_compativel: bool = True
    delta_valor_centavos: int | None = None
    delta_dias: int | None = None
    versao: str = ALGORITMO_VERSAO

    @property
    def sugere_match(self) -> bool:
        return self.pontos >= LIMIAR_SUGERIDA

    @property
    def auto_match(self) -> bool:
        return self.pontos >= LIMIAR_AUTO


def pontuar_match(transacao: TransacaoView, documento: DocumentoView) -> ScoreMatch:
    """Calcula o score determinístico para um par (transação, NF).

    Returns:
        ScoreMatch com pontos, breakdown legível e métricas auxiliares.
    """
    if not _sinal_compativel(transacao, documento):
        return ScoreMatch(
            pontos=0,
            breakdown=["sinal_incompativel"],
            sinal_compativel=False,
        )

    breakdown: list[str] = []
    pontos = 0

    # Valor — usa absolutos porque transação DEBIT é negativa.
    abs_tx = transacao.valor.copy_abs()
    delta_valor = (abs_tx - documento.valor_total).copy_abs()
    delta_centavos = int((delta_valor * 100).to_integral_value())

    if delta_valor <= _DELTA_VALOR_EXATO:
        pontos += _PT_VALOR_EXATO
        breakdown.append(f"valor_exato:+{_PT_VALOR_EXATO}")
    elif delta_valor <= _DELTA_VALOR_PROXIMO:
        pontos += _PT_VALOR_PROXIMO
        breakdown.append(f"valor_proximo({delta_valor}):+{_PT_VALOR_PROXIMO}")
    elif delta_valor > _DELTA_VALOR_DIVERGENTE:
        # Valor distante demais — encerra cedo sem pontuar nada.
        return ScoreMatch(
            pontos=0,
            breakdown=[f"valor_divergente(delta={delta_valor})"],
            sinal_compativel=True,
            delta_valor_centavos=delta_centavos,
        )

    # Data.
    delta_dias_abs = abs((transacao.data_transacao - documento.emitida_em_data).days)
    if delta_dias_abs == 0:
        pontos += _PT_DATA_EXATA
        breakdown.append(f"data_exata:+{_PT_DATA_EXATA}")
    elif delta_dias_abs <= 1:
        pontos += _PT_DATA_1_DIA
        breakdown.append(f"data_1_dia:+{_PT_DATA_1_DIA}")
    elif delta_dias_abs <= 5:
        pontos += _PT_DATA_5_DIAS
        breakdown.append(f"data_{delta_dias_abs}_dias:+{_PT_DATA_5_DIAS}")

    # CNPJ da contraparte na descrição.
    contraparte = _cnpj_contraparte(transacao, documento)
    if contraparte and _cnpj_na_descricao(contraparte, transacao.descricao):
        pontos += _PT_CNPJ_DESCRICAO
        breakdown.append(f"cnpj_contraparte:+{_PT_CNPJ_DESCRICAO}")

    pontos = max(0, min(pontos, 100))
    return ScoreMatch(
        pontos=pontos,
        breakdown=breakdown,
        sinal_compativel=True,
        delta_valor_centavos=delta_centavos,
        delta_dias=delta_dias_abs,
    )


# ── helpers privados ─────────────────────────────────────────────────────────


def _sinal_compativel(tx: TransacaoView, doc: DocumentoView) -> bool:
    """CREDIT ↔ saida (cliente paga empresa); DEBIT ↔ entrada (empresa paga fornecedor)."""
    if tx.tipo == "CREDIT":
        return doc.direcao == "saida"
    if tx.tipo == "DEBIT":
        return doc.direcao == "entrada"
    return False


def _cnpj_contraparte(tx: TransacaoView, doc: DocumentoView) -> str | None:
    """Para NF de saída, contraparte é o destinatário; para entrada, o emitente."""
    if doc.direcao == "saida":
        return doc.cnpj_destinatario
    if doc.direcao == "entrada":
        return doc.cnpj_emitente
    return None


_RE_NAO_DIGITO = re.compile(r"\D+")


def _cnpj_na_descricao(cnpj: str, descricao: str | None) -> bool:
    """Procura o CNPJ (14 dígitos) na descrição, ignorando pontuação.

    Normaliza ambos para apenas dígitos e faz substring match.
    """
    if not descricao:
        return False
    cnpj_digits = _RE_NAO_DIGITO.sub("", cnpj)
    if len(cnpj_digits) != 14:
        return False
    desc_digits = _RE_NAO_DIGITO.sub("", descricao)
    return cnpj_digits in desc_digits
