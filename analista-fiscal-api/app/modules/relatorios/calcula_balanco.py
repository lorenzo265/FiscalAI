"""Balanço Patrimonial — estrutura Lei 6.404/1976 art. 178.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 6.404/1976 art. 178 — estrutura do Balanço Patrimonial.
  * NBC TG 26 (R5) item 60 — classificação ativo/passivo Circulante/Não
    Circulante por critério de realização/exigibilidade em até 12 meses.
  * IN RFB 1.700/2017 — DRE auxiliar LP (referência cruzada — Sprint 12 PR3).

Estrutura aplicada (compatível com plano referencial RFB usado na Sprint 9):

  ATIVO
    Circulante       (1.1 — Disponibilidades, Clientes, Estoques)
    Não Circulante   (1.2 — Imobilizado, Investimentos)
  ──────────────────────────────────────────────────────────────
  PASSIVO + PATRIMÔNIO LÍQUIDO
    Passivo Circulante       (2.1 — Fornecedores, Obrig. Trab., Encargos, Impostos)
    Passivo Não Circulante   (2.2 — Empréstimos LP, debêntures)
    Patrimônio Líquido       (3.x — Capital Social, Lucros/Prejuízos)
  ──────────────────────────────────────────────────────────────

  INVARIANTE: ATIVO_total = PASSIVO_total + PL_total

Convenção de sinal: o caller passa `saldo_final` já signed pela natureza
(positivo = posição alinhada). Contas retificadoras (1.2.3.99 Depreciação
Acumulada — natureza C dentro de Ativo) entram NEGATIVAS no Ativo Não
Circulante (subtraem do bruto).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "balanco.lei6404.v1"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")


# ── Códigos / prefixos alinhados ao plano_referencial.py ───────────────────


_COD_ATIVO = "1"
_COD_ATIVO_CIRC = "1.1"
_COD_ATIVO_NAO_CIRC = "1.2"
_COD_PASSIVO_CIRC = "2.1"
_COD_PASSIVO_NAO_CIRC = "2.2"
_COD_PL = "3"


@dataclass(frozen=True, slots=True)
class SaldoConta:
    """Saldo final de uma conta numa data — input do algoritmo.

    O caller (service) é responsável por buscar a linha mais recente de
    ``saldo_conta_mes`` com ``competencia <= data_referencia``. Contas
    retificadoras (natureza diferente do tipo) entram com `saldo_final`
    NEGATIVO se o saldo aumenta na direção retificadora.
    """

    codigo: str
    descricao: str
    natureza: str  # 'D' | 'C'
    tipo: str  # 'ativo' | 'passivo' | 'patrimonio_liquido'
    saldo_final: Decimal


@dataclass(frozen=True, slots=True)
class LinhaBalanco:
    """Item do balanço com label, valor e contas detalhadas."""

    rotulo: str
    valor: Decimal
    contas: tuple[tuple[str, str, Decimal], ...] = ()  # (codigo, desc, saldo)


@dataclass(frozen=True, slots=True)
class ResultadoBalanco:
    """Snapshot persistido em ``relatorio_gerado.payload`` (tipo='balanco')."""

    ativo_circulante: LinhaBalanco
    ativo_nao_circulante: LinhaBalanco
    ativo_total: LinhaBalanco
    passivo_circulante: LinhaBalanco
    passivo_nao_circulante: LinhaBalanco
    patrimonio_liquido: LinhaBalanco
    passivo_mais_pl_total: LinhaBalanco
    fecha: bool  # ATIVO == PASSIVO + PL ?
    diferenca: Decimal  # ATIVO - (PASSIVO + PL); deve ser 0
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def _eh_prefixo(codigo: str, prefixo: str) -> bool:
    if codigo == prefixo:
        return True
    return codigo.startswith(prefixo + ".")


def _consolidar(
    saldos: list[SaldoConta], prefixo: str, rotulo: str
) -> LinhaBalanco:
    """Soma saldos cujo código começa com ``prefixo`` (boundary de ponto)."""
    total = _ZERO
    contas: list[tuple[str, str, Decimal]] = []
    for s in saldos:
        if not _eh_prefixo(s.codigo, prefixo):
            continue
        if s.saldo_final == _ZERO:
            continue
        total += s.saldo_final
        contas.append((s.codigo, s.descricao, _quantizar(s.saldo_final)))
    return LinhaBalanco(
        rotulo=rotulo,
        valor=_quantizar(total),
        contas=tuple(contas),
    )


def calcular_balanco(saldos: list[SaldoConta]) -> ResultadoBalanco:
    """Monta o Balanço Patrimonial a partir dos saldos finais na data.

    Args:
        saldos: saldos finais das contas analíticas (não sintéticas) na
            data de referência. Cada um vem ``signed`` pela natureza —
            positivo significa posição alinhada (Ativo+ = bens; Passivo+ =
            obrigações; PL+ = patrimônio).

    Returns:
        ResultadoBalanco. Inclui flag ``fecha`` para o invariante
        ATIVO = PASSIVO + PL; em caso de não-fechamento, ``diferenca``
        mostra o desvio (geralmente indica que falta encerrar o exercício
        para zerar Resultado do Exercício em Lucros Acumulados, ou faltam
        partidas dobradas — caller deve investigar).
    """
    ativo_circ = _consolidar(saldos, _COD_ATIVO_CIRC, "Ativo Circulante")
    ativo_nao_circ = _consolidar(
        saldos, _COD_ATIVO_NAO_CIRC, "Ativo Não Circulante",
    )
    ativo_total = LinhaBalanco(
        rotulo="ATIVO TOTAL",
        valor=_quantizar(ativo_circ.valor + ativo_nao_circ.valor),
    )

    passivo_circ = _consolidar(
        saldos, _COD_PASSIVO_CIRC, "Passivo Circulante",
    )
    passivo_nao_circ = _consolidar(
        saldos, _COD_PASSIVO_NAO_CIRC, "Passivo Não Circulante",
    )
    pl = _consolidar(saldos, _COD_PL, "Patrimônio Líquido")
    passivo_mais_pl = LinhaBalanco(
        rotulo="PASSIVO + PL TOTAL",
        valor=_quantizar(passivo_circ.valor + passivo_nao_circ.valor + pl.valor),
    )

    diferenca = _quantizar(ativo_total.valor - passivo_mais_pl.valor)
    fecha = diferenca == _ZERO

    return ResultadoBalanco(
        ativo_circulante=ativo_circ,
        ativo_nao_circulante=ativo_nao_circ,
        ativo_total=ativo_total,
        passivo_circulante=passivo_circ,
        passivo_nao_circulante=passivo_nao_circ,
        patrimonio_liquido=pl,
        passivo_mais_pl_total=passivo_mais_pl,
        fecha=fecha,
        diferenca=diferenca,
    )
