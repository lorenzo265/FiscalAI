"""Calculadora ICMS mensal — apuração débito × crédito.

Camada 1 (determinística). Função pura, zero I/O.

Fundamento legal:
  * LC 87/1996 (Lei Kandir) — regulamento nacional do ICMS.
  * CF art. 155 §2º I — não-cumulatividade: compensa o que foi cobrado nas
    operações anteriores.
  * Convênio ICMS 142/2018 — alíquotas interestaduais (4%/7%/12%).
  * Resolução do Senado nº 22/1989 — alíquota interestadual padrão.
  * Resolução do Senado nº 13/2012 — 4% para mercadorias importadas.

Modelo simplificado para PME:

  débito  = soma de (base × alíquota) das saídas tributadas
  crédito = soma de (base × alíquota) das entradas com direito a crédito
            (regra geral: insumos e mercadorias para revenda; bens de uso
             e consumo SEM direito; ativo imobilizado 1/48 ao mês)
  saldo   = débito − crédito − saldo_credor_anterior + ajustes_devedores
          − ajustes_credores

  Se saldo > 0 → ICMS a recolher (DARE/GNRE)
  Se saldo < 0 → saldo credor a transportar (carryover)
  Se saldo = 0 → nada a recolher, sem credito a transportar

Alíquotas interestaduais (helper ``aliquota_interestadual``):
  * Origem Sul/Sudeste (exceto ES) → destino N/NE/CO + ES: 7%
  * Demais combinações entre estados: 12%
  * Mercadoria importada (qualquer origem→destino): 4%
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from enum import StrEnum

getcontext().prec = 28

ALGORITMO_VERSAO = "icms.mensal.v1"

_CENTAVO = Decimal("0.01")
_ZERO = Decimal("0")

# UFs que pagam alíquota interestadual reduzida quando ORIGEM é S/SE (exceto ES)
_UFS_N_NE_CO_E_ES = frozenset({
    # Norte
    "AC", "AM", "AP", "PA", "RO", "RR", "TO",
    # Nordeste
    "AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE",
    # Centro-Oeste
    "DF", "GO", "MT", "MS",
    # Espírito Santo (exceção do Sudeste para fins interestaduais)
    "ES",
})
_UFS_S_SE_SEM_ES = frozenset({"MG", "RJ", "SP", "PR", "RS", "SC"})


class TipoOrigem(StrEnum):
    NACIONAL = "nacional"
    IMPORTADA = "importada"


@dataclass(frozen=True, slots=True)
class ResultadoIcmsMensal:
    """Snapshot persistido em ``apuracao_fiscal`` (tipo='icms')."""

    competencia_inicio_mes: str  # YYYY-MM-01 em ISO
    uf: str
    aliquota_interna: Decimal
    debito: Decimal
    credito: Decimal
    saldo_credor_anterior: Decimal
    ajustes_devedores: Decimal
    ajustes_credores: Decimal
    saldo_apurado: Decimal  # débito − crédito − saldo_anterior + dev − cred
    icms_a_recolher: Decimal  # max(0, saldo_apurado)
    saldo_credor_a_transportar: Decimal  # max(0, -saldo_apurado)
    algoritmo_versao: str = ALGORITMO_VERSAO


def _quantizar(v: Decimal) -> Decimal:
    return v.quantize(_CENTAVO, rounding=ROUND_HALF_EVEN)


def aliquota_interestadual(
    uf_origem: str,
    uf_destino: str,
    *,
    origem: TipoOrigem = TipoOrigem.NACIONAL,
) -> Decimal:
    """Retorna a alíquota interestadual aplicável.

    Resolução do Senado 22/1989 + 13/2012.
    """
    if not _uf_valida(uf_origem) or not _uf_valida(uf_destino):
        raise ValueError(
            f"UFs inválidas: origem={uf_origem!r}, destino={uf_destino!r}"
        )
    if uf_origem == uf_destino:
        raise ValueError(
            f"alíquota_interestadual aplicada a operação interna ({uf_origem})"
        )
    if origem is TipoOrigem.IMPORTADA:
        return Decimal("0.0400")
    if uf_origem in _UFS_S_SE_SEM_ES and uf_destino in _UFS_N_NE_CO_E_ES:
        return Decimal("0.0700")
    return Decimal("0.1200")


def _uf_valida(uf: str) -> bool:
    return uf in _UFS_S_SE_SEM_ES or uf in _UFS_N_NE_CO_E_ES


def calcular_icms_mensal(
    competencia: str,
    uf: str,
    aliquota_interna: Decimal,
    debito: Decimal,
    credito: Decimal,
    *,
    saldo_credor_anterior: Decimal = _ZERO,
    ajustes_devedores: Decimal = _ZERO,
    ajustes_credores: Decimal = _ZERO,
) -> ResultadoIcmsMensal:
    """Apura ICMS mensal pelo regime não-cumulativo (LC 87/1996).

    Args:
        competencia: ISO YYYY-MM-01.
        uf: UF da empresa.
        aliquota_interna: alíquota da UF (vem de ``aliquota_icms_uf`` SCD).
        debito: soma dos débitos do mês (vendas tributadas).
        credito: soma dos créditos do mês (entradas com direito).
        saldo_credor_anterior: trazido do mês anterior.
        ajustes_devedores: estornos de crédito, débitos extra-livro.
        ajustes_credores: créditos extemporâneos, restituições.

    Returns:
        ResultadoIcmsMensal.

    Raises:
        ValueError: parâmetros inválidos.
    """
    if not _uf_valida(uf):
        raise ValueError(f"UF inválida: {uf!r}")
    if aliquota_interna < _ZERO or aliquota_interna > Decimal("1"):
        raise ValueError(
            f"aliquota_interna fora de [0, 1]: {aliquota_interna}"
        )
    for nome, v in (
        ("debito", debito),
        ("credito", credito),
        ("saldo_credor_anterior", saldo_credor_anterior),
        ("ajustes_devedores", ajustes_devedores),
        ("ajustes_credores", ajustes_credores),
    ):
        if v < _ZERO:
            raise ValueError(f"{nome} não pode ser negativo: {v}")

    saldo_apurado = (
        debito - credito - saldo_credor_anterior
        + ajustes_devedores - ajustes_credores
    )
    saldo_apurado_q = _quantizar(saldo_apurado)

    if saldo_apurado_q > _ZERO:
        a_recolher = saldo_apurado_q
        credor_transportar = _ZERO
    else:
        a_recolher = _ZERO
        credor_transportar = _quantizar(-saldo_apurado_q)

    return ResultadoIcmsMensal(
        competencia_inicio_mes=competencia,
        uf=uf,
        aliquota_interna=aliquota_interna,
        debito=_quantizar(debito),
        credito=_quantizar(credito),
        saldo_credor_anterior=_quantizar(saldo_credor_anterior),
        ajustes_devedores=_quantizar(ajustes_devedores),
        ajustes_credores=_quantizar(ajustes_credores),
        saldo_apurado=saldo_apurado_q,
        icms_a_recolher=a_recolher,
        saldo_credor_a_transportar=credor_transportar,
    )
