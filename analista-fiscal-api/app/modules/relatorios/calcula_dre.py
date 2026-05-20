"""Demonstração do Resultado do Exercício — DRE estruturada.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * Lei 6.404/1976 art. 187 — estrutura mínima da DRE.
  * NBC TG 26 (R5) — apresentação das demonstrações contábeis.
  * IN RFB 1.700/2017 — DRE auxiliar para LP (Sprint 12 PR3).

Estrutura aplicada (compatível com plano referencial RFB usado na Sprint 9):

  RECEITA OPERACIONAL BRUTA         = Σ saldos contas 4.*  (exceto outras)
  (-) Impostos sobre Receita        = saldo 5.1.05
  ───────────────────────────────────────────────────
  RECEITA LÍQUIDA
  (-) CMV / CSV                     = saldo 5.1.01
  ───────────────────────────────────────────────────
  LUCRO BRUTO
  (-) Despesas com Pessoal          = saldo 5.1.02 + 5.1.03
  (-) Outras Despesas Operacionais  = saldo 5.1.99 + outras 5.x não classificadas
  ───────────────────────────────────────────────────
  EBITDA
  (-) Depreciação / Amortização     = saldo 5.1.04
  ───────────────────────────────────────────────────
  EBIT (= LAIR neste MVP — sem contas financeiras separadas)
  (+/-) Resultado Financeiro        = 0 (placeholder até plano ser expandido)
  ───────────────────────────────────────────────────
  LAIR (Lucro Antes do IR/CSLL)
  (-) IRPJ + CSLL                   = input externo (vem de apuracao_fiscal)
  ───────────────────────────────────────────────────
  LUCRO LÍQUIDO DO EXERCÍCIO

Convenção de sinal: receitas são positivas (saldo natureza C);
despesas/deduções entram positivas e o algoritmo SUBTRAI no nível certo.

Algoritmo puro — caller passa:
  * lista de ``SaldoConta`` (código + saldo_final no período),
  * ``irpj_csll_apurado`` (Decimal — soma de IRPJ + CSLL das apurações
    do período).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 28

ALGORITMO_VERSAO = "dre.estruturada.v1"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")


# ── Códigos de mapeamento (alinhados ao plano_referencial.py) ──────────────


_COD_RECEITA_RAIZ = "4"
_COD_DESPESAS_RAIZ = "5"
_COD_IMPOSTOS_RECEITA = "5.1.05"
_COD_CMV = "5.1.01"
_COD_DESPESAS_PESSOAL = ("5.1.02", "5.1.03")
_COD_DEPRECIACAO = "5.1.04"


@dataclass(frozen=True, slots=True)
class SaldoConta:
    """Saldo agregado de uma conta no período — input do algoritmo."""

    codigo: str
    descricao: str
    saldo_final: Decimal  # já signed pela natureza (positivo na natureza padrão)


@dataclass(frozen=True, slots=True)
class LinhaDre:
    """Uma linha do DRE com label e valor calculado."""

    rotulo: str
    valor: Decimal
    detalhes: tuple[str, ...] = ()  # códigos de contas que somaram


@dataclass(frozen=True, slots=True)
class ResultadoDre:
    """Snapshot persistido em ``relatorio_gerado.payload`` (tipo='dre')."""

    receita_bruta: LinhaDre
    deducoes: LinhaDre
    receita_liquida: LinhaDre
    cmv: LinhaDre
    lucro_bruto: LinhaDre
    despesas_pessoal: LinhaDre
    outras_despesas: LinhaDre
    ebitda: LinhaDre
    depreciacao: LinhaDre
    ebit: LinhaDre
    resultado_financeiro: LinhaDre
    lair: LinhaDre
    irpj_csll: LinhaDre
    lucro_liquido: LinhaDre
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def _eh_prefixo(codigo: str, prefixo: str) -> bool:
    """True se ``codigo`` começa com ``prefixo`` no boundary de ponto.

    Evita match indevido (ex.: "5.1.05" não casa com "5.1.0").
    """
    if codigo == prefixo:
        return True
    return codigo.startswith(prefixo + ".")


def _somar_prefixo(
    saldos: list[SaldoConta],
    prefixo: str,
    *,
    excluir: tuple[str, ...] = (),
) -> tuple[Decimal, tuple[str, ...]]:
    """Soma saldos cujo código começa com ``prefixo``, excluindo prefixos dados."""
    total = _ZERO
    codigos_usados: list[str] = []
    for s in saldos:
        if not _eh_prefixo(s.codigo, prefixo):
            continue
        if any(_eh_prefixo(s.codigo, e) for e in excluir):
            continue
        # Pula sintéticas (caller passa só analíticas — mas defensivo).
        if s.saldo_final == _ZERO:
            continue
        total += s.saldo_final
        codigos_usados.append(s.codigo)
    return total, tuple(codigos_usados)


def _somar_codigos(
    saldos: list[SaldoConta], codigos: tuple[str, ...]
) -> tuple[Decimal, tuple[str, ...]]:
    """Soma saldos de códigos exatos listados."""
    total = _ZERO
    usados: list[str] = []
    for s in saldos:
        if s.codigo in codigos and s.saldo_final != _ZERO:
            total += s.saldo_final
            usados.append(s.codigo)
    return total, tuple(usados)


def _codigo_exato(
    saldos: list[SaldoConta], codigo: str
) -> tuple[Decimal, tuple[str, ...]]:
    total, usados = _somar_codigos(saldos, (codigo,))
    return total, usados


def calcular_dre(
    saldos: list[SaldoConta],
    *,
    irpj_csll_apurado: Decimal = _ZERO,
    resultado_financeiro: Decimal = _ZERO,
) -> ResultadoDre:
    """Calcula DRE estruturada para um período.

    Args:
        saldos: saldos finais das contas analíticas no período (vem do
            consolidador do balancete). Receitas em valor positivo (saldo
            natureza C); despesas em valor positivo (saldo natureza D).
        irpj_csll_apurado: IRPJ + CSLL apurados via ``apuracao_fiscal``
            no período (Sprint 11 PR1). Não é lido das contas porque
            o plano referencial atual não tem 'Despesa de IR' separada.
        resultado_financeiro: receitas − despesas financeiras no período.
            Como o plano referencial não tem essas contas no MVP, default 0.

    Returns:
        ResultadoDre estruturado pronto para serialização.

    Raises:
        ValueError: se ``irpj_csll_apurado`` < 0 (tributo nunca é negativo).
    """
    if irpj_csll_apurado < _ZERO:
        raise ValueError(
            f"irpj_csll_apurado não pode ser negativo: {irpj_csll_apurado}"
        )

    # ── Receitas ─────────────────────────────────────────────────────────
    receita_bruta_v, receita_codigos = _somar_prefixo(saldos, _COD_RECEITA_RAIZ)
    receita_bruta = LinhaDre(
        rotulo="Receita Operacional Bruta",
        valor=_quantizar(receita_bruta_v),
        detalhes=receita_codigos,
    )

    deducoes_v, deducoes_codigos = _codigo_exato(saldos, _COD_IMPOSTOS_RECEITA)
    deducoes = LinhaDre(
        rotulo="(-) Impostos sobre Receita",
        valor=_quantizar(deducoes_v),
        detalhes=deducoes_codigos,
    )

    receita_liquida = LinhaDre(
        rotulo="Receita Líquida",
        valor=_quantizar(receita_bruta.valor - deducoes.valor),
    )

    # ── Custos + Lucro Bruto ─────────────────────────────────────────────
    cmv_v, cmv_codigos = _codigo_exato(saldos, _COD_CMV)
    cmv = LinhaDre(
        rotulo="(-) CMV / CSV",
        valor=_quantizar(cmv_v),
        detalhes=cmv_codigos,
    )
    lucro_bruto = LinhaDre(
        rotulo="Lucro Bruto",
        valor=_quantizar(receita_liquida.valor - cmv.valor),
    )

    # ── Despesas Operacionais ────────────────────────────────────────────
    pessoal_v, pessoal_codigos = _somar_codigos(saldos, _COD_DESPESAS_PESSOAL)
    despesas_pessoal = LinhaDre(
        rotulo="(-) Despesas com Pessoal e Encargos",
        valor=_quantizar(pessoal_v),
        detalhes=pessoal_codigos,
    )

    # Outras = todo 5.x exceto CMV, Pessoal, Encargos, Depreciação, Impostos.
    outras_v, outras_codigos = _somar_prefixo(
        saldos, _COD_DESPESAS_RAIZ,
        excluir=(
            _COD_CMV,
            *_COD_DESPESAS_PESSOAL,
            _COD_DEPRECIACAO,
            _COD_IMPOSTOS_RECEITA,
        ),
    )
    outras_despesas = LinhaDre(
        rotulo="(-) Outras Despesas Operacionais",
        valor=_quantizar(outras_v),
        detalhes=outras_codigos,
    )

    ebitda = LinhaDre(
        rotulo="EBITDA",
        valor=_quantizar(
            lucro_bruto.valor - despesas_pessoal.valor - outras_despesas.valor
        ),
    )

    # ── EBIT ──────────────────────────────────────────────────────────────
    depreciacao_v, depreciacao_codigos = _codigo_exato(saldos, _COD_DEPRECIACAO)
    depreciacao = LinhaDre(
        rotulo="(-) Depreciação / Amortização",
        valor=_quantizar(depreciacao_v),
        detalhes=depreciacao_codigos,
    )
    ebit = LinhaDre(
        rotulo="EBIT (Resultado Operacional)",
        valor=_quantizar(ebitda.valor - depreciacao.valor),
    )

    # ── LAIR + Lucro Líquido ─────────────────────────────────────────────
    rf = LinhaDre(
        rotulo="(+/-) Resultado Financeiro",
        valor=_quantizar(resultado_financeiro),
    )
    lair = LinhaDre(
        rotulo="LAIR (Lucro Antes do IRPJ/CSLL)",
        valor=_quantizar(ebit.valor + rf.valor),
    )
    irpj_csll = LinhaDre(
        rotulo="(-) IRPJ + CSLL",
        valor=_quantizar(irpj_csll_apurado),
    )
    lucro_liquido = LinhaDre(
        rotulo="LUCRO LÍQUIDO DO EXERCÍCIO",
        valor=_quantizar(lair.valor - irpj_csll.valor),
    )

    return ResultadoDre(
        receita_bruta=receita_bruta,
        deducoes=deducoes,
        receita_liquida=receita_liquida,
        cmv=cmv,
        lucro_bruto=lucro_bruto,
        despesas_pessoal=despesas_pessoal,
        outras_despesas=outras_despesas,
        ebitda=ebitda,
        depreciacao=depreciacao,
        ebit=ebit,
        resultado_financeiro=rf,
        lair=lair,
        irpj_csll=irpj_csll,
        lucro_liquido=lucro_liquido,
    )
