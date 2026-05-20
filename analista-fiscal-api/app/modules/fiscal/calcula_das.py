"""Calculadora DAS — Simples Nacional.

Camada 1 (determinística). Função pura, zero I/O.
Fonte: LC 123/2006 + LC 155/2016 + Resolução CGSN 140/2018.

Princípio §8.4: golden tests são a barreira de merge.
Princípio §8.8: LLM nunca chama este módulo para escrever — apenas lê resultados.

v2 (Fase 1.4 do plano de remediação):
- Sublimite estadual de ICMS/ISS (LC 123 art. 19): quando RBT12 > sublimite, ICMS/ISS
  saem do DAS e devem ser apurados pelo regime normal estadual/municipal.
- Teto federal R$4.800.000 (LC 123 art. 3º II): acima disso a empresa deve ser
  desenquadrada do SN — função levanta ``EmpresaForaSimplesNacional``.
- Esta versão NÃO calcula o "DAS sem ICMS/ISS" (exige decomposição por tributo na
  tabela CGSN, pendência da Fase 5). Em vez disso, calcula o DAS cheio e sinaliza
  via flag ``sublimite_excedido`` que o cliente deve recolher ICMS/ISS por fora —
  o frontend deve mostrar aviso e o contador deve agir.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

from app.shared.exceptions import EmpresaForaSimplesNacional

getcontext().prec = 28

ALGORITMO_VERSAO = "sn.das.v2"

_CENT = Decimal("0.01")
_ALIQ_DISPLAY = Decimal("0.0001")
_ZERO = Decimal("0")
_FATOR_R_MINIMO = Decimal("0.28")  # Resolução CGSN 140/2018 art. 26 §1º
_TETO_FEDERAL = Decimal("4800000.00")  # LC 123/2006 art. 3º II
_SUBLIMITE_PADRAO = Decimal("3600000.00")  # LC 123/2006 art. 19 §1º (default)


@dataclass(frozen=True, slots=True)
class FaixaDAS:
    """Uma linha da tabela Simples Nacional (SCD Type 2 — vem do banco)."""

    faixa: int  # 1 a 6
    rbt12_ate: Decimal  # limite superior inclusivo (ex: 180_000)
    aliquota_nominal: Decimal  # fração: 0.0400 = 4,00%
    parcela_deduzir: Decimal  # valor a deduzir antes de dividir por RBT12


@dataclass(frozen=True, slots=True)
class ResultadoDAS:
    """Resultado imutável do cálculo DAS — persiste em apuracao_fiscal.output_jsonb."""

    anexo: str  # anexo declarado na empresa ("I"…"V")
    anexo_efetivo: str  # pode diferir por resolução do Fator R
    faixa: int
    rbt12_usado: Decimal
    aliquota_nominal: Decimal
    parcela_deduzir: Decimal
    aliquota_efetiva: Decimal  # quantizada em 4 casas para exibição
    receita_mes: Decimal
    valor: Decimal  # DAS a recolher — quantizado em 2 casas (centavos)
    fator_r: Decimal | None
    algoritmo_versao: str
    # ── v2: sublimite ──────────────────────────────────────────────────
    uf: str | None  # UF declarada da empresa (informativa, copiada do input)
    sublimite_aplicado: Decimal  # qual sublimite estadual foi considerado
    sublimite_excedido: bool  # True ⇒ ICMS/ISS devem sair do DAS e ir por fora
    # Nota: quando sublimite_excedido=True, o `valor` retornado segue sendo o DAS
    # cheio (com ICMS/ISS embutidos), porque a decomposição por tributo da tabela
    # CGSN ainda não está no schema. O caller deve mostrar aviso explícito
    # ("ICMS/ISS devem ser apurados pelo regime normal estadual/municipal").


def resolver_anexo_fator_r(anexo: str, fator_r: Decimal) -> str:
    """Resolve Anexo III ou V com base no Fator R (art. 26 Res. CGSN 140/2018).

    Retorna o anexo efetivo: "III" se fator_r >= 28%, "V" caso contrário.
    Apenas válido quando o anexo da empresa é "III" ou "V".
    """
    if anexo not in ("III", "V"):
        raise ValueError(f"Resolução de Fator R só se aplica ao Anexo III/V, recebido: {anexo}")
    return "III" if fator_r >= _FATOR_R_MINIMO else "V"


def _encontrar_faixa(rbt12: Decimal, faixas: list[FaixaDAS]) -> FaixaDAS:
    ordenadas = sorted(faixas, key=lambda f: f.faixa)
    for faixa in ordenadas:
        if rbt12 <= faixa.rbt12_ate:
            return faixa
    return ordenadas[-1]


def calcular_das(
    rbt12: Decimal,
    receita_mes: Decimal,
    faixas: list[FaixaDAS],
    *,
    anexo: str = "I",
    anexo_efetivo: str | None = None,
    fator_r: Decimal | None = None,
    uf: str | None = None,
    sublimite_estadual: Decimal | None = None,
    algoritmo_versao: str = ALGORITMO_VERSAO,
) -> ResultadoDAS:
    """Calcula o DAS do Simples Nacional para um mês de competência.

    Args:
        rbt12: Receita Bruta dos últimos 12 meses (RBT12).
        receita_mes: Receita bruta do mês de competência.
        faixas: Tabela do anexo efetivo já resolvida (Fator R aplicado antes de chamar).
        anexo: Anexo declarado na empresa ("I"–"V").
        anexo_efetivo: Anexo usado no cálculo; se None, igual a `anexo`.
        fator_r: Fator R calculado (folha_12m / rbt12), None se não aplicável.
        uf: UF da empresa (informativa; usada para selecionar sublimite default).
        sublimite_estadual: sublimite de ICMS/ISS aplicável; se None, usa o padrão
            R$3.600.000 (LC 123 art. 19 §1º). Estados podem ter optado pelo
            sublimite reduzido R$1.800.000.
        algoritmo_versao: Versão do algoritmo para rastreabilidade (SCD).

    Returns:
        ResultadoDAS imutável — pronto para persistir em apuracao_fiscal.

    Raises:
        ValueError: parâmetros básicos inválidos.
        EmpresaForaSimplesNacional: RBT12 excedeu o teto federal R$4.800.000.
    """
    if receita_mes < _ZERO:
        raise ValueError(f"receita_mes não pode ser negativa: {receita_mes}")
    if rbt12 < _ZERO:
        raise ValueError(f"rbt12 não pode ser negativo: {rbt12}")
    if not faixas:
        raise ValueError("faixas não pode ser vazia")

    if rbt12 > _TETO_FEDERAL:
        raise EmpresaForaSimplesNacional(
            f"RBT12 R${rbt12} excedeu o teto federal R${_TETO_FEDERAL} (LC 123 art. 3º II). "
            "Empresa deve ser desenquadrada do Simples Nacional."
        )

    sublimite = sublimite_estadual if sublimite_estadual is not None else _SUBLIMITE_PADRAO
    sublimite_excedido = rbt12 > sublimite

    ef = anexo_efetivo if anexo_efetivo is not None else anexo
    faixa_obj = _encontrar_faixa(rbt12, faixas)

    if rbt12 == _ZERO:
        aliq_raw = faixa_obj.aliquota_nominal
    else:
        aliq_raw = (rbt12 * faixa_obj.aliquota_nominal - faixa_obj.parcela_deduzir) / rbt12

    valor = (receita_mes * aliq_raw).quantize(_CENT, rounding=ROUND_HALF_EVEN)
    aliq_display = aliq_raw.quantize(_ALIQ_DISPLAY, rounding=ROUND_HALF_EVEN)

    return ResultadoDAS(
        anexo=anexo,
        anexo_efetivo=ef,
        faixa=faixa_obj.faixa,
        rbt12_usado=rbt12,
        aliquota_nominal=faixa_obj.aliquota_nominal,
        parcela_deduzir=faixa_obj.parcela_deduzir,
        aliquota_efetiva=aliq_display,
        receita_mes=receita_mes,
        valor=valor,
        fator_r=fator_r,
        algoritmo_versao=algoritmo_versao,
        uf=uf,
        sublimite_aplicado=sublimite,
        sublimite_excedido=sublimite_excedido,
    )
