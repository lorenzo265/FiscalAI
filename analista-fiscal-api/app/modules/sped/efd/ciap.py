"""CIAP — Controle de Crédito de ICMS do Ativo Permanente (Sprint 19.6 PR1).

**Camada 1 (determinística), §8.4.** Função pura: recebe lista de bens
imobilizados + período, devolve snapshot com saldo inicial, parcelas
apropriadas e movimentos G125. Sem I/O — testável em isolamento.

Base legal: LC 87/1996 art. 20 §5º (com redação da LC 102/2000):

  > "Para efeito de aplicação do disposto no § 5º, o crédito relativo
  > ao bem do ativo permanente será apropriado à razão de 1/48 (um
  > quarenta e oito avos) por mês".

Regra:

  * Aquisição em ``data_aquisicao`` com ``icms_aquisicao_destacado``
    conhecido.
  * Parcela mensal = ICMS / 48 (mesma fórmula 4 anos).
  * Apropriação começa no mês da aquisição (parcela 1).
  * Parcelas finalizam no mês 48 após aquisição (parcela 48 = último).
  * Bem **baixado** mid-CIAP: para de apropriar a partir do mês da baixa.
  * Bem com ``icms_aquisicao_destacado IS NULL`` → fora do CIAP
    (cadastro legado ou aquisição sem ICMS destacado).

Out-of-scope desta entrega (sprint dedicada futura quando primeiro
cliente CIAP-relevante aparecer):

  * Estorno proporcional por saída isenta (G126 / G130).
  * Reapropriação após retorno de baixa indevida.
  * CIAP de bem usado em produção parcialmente isenta.
  * Apuração para empresas em **regime cumulativo** (sem crédito).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

_ZERO = Decimal("0")
_QUANTIZE = Decimal("0.01")
_QUARENTA_E_OITO = Decimal("48")


@dataclass(frozen=True, slots=True)
class BemCiap:
    """Snapshot puro de um bem ativo para o CIAP — sem I/O.

    Caller monta a partir de ``BemImobilizado`` (filtrando bens com
    ``icms_aquisicao_destacado`` preenchido e ativos no período).
    """

    bem_id: str  # COD_IND_BEM (id ou código interno)
    descricao: str
    data_aquisicao: date
    icms_aquisicao_destacado: Decimal
    data_baixa: date | None = None


@dataclass(frozen=True, slots=True)
class MovimentoCiap:
    """Linha do registro G125 — movimento de apropriação no período."""

    bem_id: str
    data_movimento: date  # último dia do período
    tipo_movimento: str  # "IM" (imobilização período) | "IA" (baixa)
    valor_imob_icms_op: Decimal  # ICMS apropriado na operação
    num_parcela: int  # 1..48
    valor_parcela: Decimal  # ICMS / 48


@dataclass(frozen=True, slots=True)
class SnapshotCiap:
    """Saída do cálculo CIAP — alimenta o gerador EFD ICMS-IPI bloco G."""

    saldo_inicial_icms: Decimal  # SALDO_IN_ICMS do G110
    soma_parcelas_periodo: Decimal  # SOM_PARC do G110
    saldo_final_icms: Decimal  # SALDO_FN_ICMS do G110 (= inicial - parcelas)
    movimentos: tuple[MovimentoCiap, ...] = field(default_factory=tuple)

    @property
    def tem_movimentos(self) -> bool:
        return bool(self.movimentos)


def _diferenca_em_meses(inicio: date, fim: date) -> int:
    """Quantos meses calendário decorreram (inclusivo).

    Mês de aquisição = parcela 1. Mês seguinte = parcela 2. Etc.
    Se ``inicio > fim`` retorna 0 (bem adquirido depois do período).
    """
    if inicio > fim:
        return 0
    return (fim.year - inicio.year) * 12 + (fim.month - inicio.month) + 1


def calcular_apropriacao_ciap(
    bens: Sequence[BemCiap],
    *,
    periodo_inicio: date,
    periodo_fim: date,
) -> SnapshotCiap:
    """Calcula apropriação CIAP do período.

    Para cada bem ativo:

    1. Determinar ``parcela_atual`` = nº da parcela que cai DENTRO do período.
       - Bem adquirido em 2024-03 e período 2025-06: parcela_atual = 16
         (mar/2024=1, abr=2, ..., jun/2025=16).
    2. Se ``parcela_atual`` ∈ [1, 48] e bem não foi baixado antes do
       período: gera G125 com tipo IM (imobilização período) +
       ``num_parcela=parcela_atual`` + ``valor_parcela=ICMS/48``.
    3. ``SOM_PARC`` = soma de todas as parcelas apropriadas no período.
    4. ``SALDO_IN_ICMS`` = soma de ``ICMS - (parcelas_apropriadas_antes
       * ICMS/48)`` para cada bem ativo no início do período.
    5. ``SALDO_FN_ICMS`` = ``SALDO_IN_ICMS - SOM_PARC``.

    Período tem que ser um mês civil completo. Para apurações
    bimestrais/trimestrais (raríssimas em ICMS), expandir lógica
    iterando mês a mês — fora de escopo deste MVP.
    """
    saldo_inicial = _ZERO
    soma_parcelas = _ZERO
    movimentos: list[MovimentoCiap] = []

    for bem in bens:
        icms = bem.icms_aquisicao_destacado
        if icms <= _ZERO:
            # Bem com ICMS zerado — esquisito, mas defensivo.
            continue

        parcela_mensal = (icms / _QUARENTA_E_OITO).quantize(
            _QUANTIZE, rounding=ROUND_HALF_EVEN
        )

        # Parcelas apropriadas ANTES do período (estado no início).
        # Se bem foi baixado, congela no mês da baixa.
        ate_inicio = _diferenca_em_meses(bem.data_aquisicao, periodo_inicio)
        # Subtrai 1 para excluir o próprio mês inicial (queremos "antes").
        parcelas_apropriadas_antes = max(0, min(48, ate_inicio - 1))
        if bem.data_baixa is not None:
            ate_baixa = _diferenca_em_meses(bem.data_aquisicao, bem.data_baixa)
            parcelas_apropriadas_antes = min(
                parcelas_apropriadas_antes, ate_baixa
            )

        saldo_bem_inicio = icms - (
            parcela_mensal * Decimal(parcelas_apropriadas_antes)
        )
        if saldo_bem_inicio < _ZERO:
            saldo_bem_inicio = _ZERO
        saldo_inicial += saldo_bem_inicio

        # Parcela do período (1..48). Se já passou de 48 ou bem foi
        # baixado, não apropria.
        parcela_atual = _diferenca_em_meses(bem.data_aquisicao, periodo_fim)
        if parcela_atual < 1 or parcela_atual > 48:
            continue
        if (
            bem.data_baixa is not None
            and bem.data_baixa < periodo_inicio
        ):
            continue

        soma_parcelas += parcela_mensal
        movimentos.append(
            MovimentoCiap(
                bem_id=bem.bem_id,
                data_movimento=periodo_fim,
                tipo_movimento="IM",
                valor_imob_icms_op=icms,
                num_parcela=parcela_atual,
                valor_parcela=parcela_mensal,
            )
        )

    saldo_final = saldo_inicial - soma_parcelas
    if saldo_final < _ZERO:
        saldo_final = _ZERO

    return SnapshotCiap(
        saldo_inicial_icms=saldo_inicial.quantize(
            _QUANTIZE, rounding=ROUND_HALF_EVEN
        ),
        soma_parcelas_periodo=soma_parcelas.quantize(
            _QUANTIZE, rounding=ROUND_HALF_EVEN
        ),
        saldo_final_icms=saldo_final.quantize(
            _QUANTIZE, rounding=ROUND_HALF_EVEN
        ),
        movimentos=tuple(movimentos),
    )


__all__ = [
    "BemCiap",
    "MovimentoCiap",
    "SnapshotCiap",
    "calcular_apropriacao_ciap",
]
