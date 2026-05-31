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

v3 (Fase 2 PR8 — MAJOR M2 da auditoria Sprints 4-6):
- ``ResultadoDAS.receitas_por_anexo`` discrimina a receita por anexo. PGDAS-D
  exige isso quando empresa tem atividades em anexos diferentes (Anexo I + III,
  ou Fator R alternando III↔V). Single-anexo continua passando: ``{anexo_efetivo:
  receita_mes}`` é serializado automaticamente.
- ``calcular_das_multi_anexo()`` orquestra cálculo por anexo: a RBT12 é a mesma
  (compartilhada) mas cada anexo usa sua tabela CGSN; o DAS total é a soma.
  Compat: ``calcular_das()`` single-anexo é inalterado (chamado por dentro).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

from app.shared.exceptions import EmpresaForaSimplesNacional

getcontext().prec = 28

ALGORITMO_VERSAO = "sn.das.v3"

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
    # ── v3: discriminação por anexo ────────────────────────────────────
    receitas_por_anexo: dict[str, Decimal] = field(default_factory=dict)
    # ``{"I": Decimal("10000.00"), "III": Decimal("5000.00")}``. Em single-anexo,
    # contém apenas ``{anexo_efetivo: receita_mes}``. PGDAS-D usa para iterar
    # ``atividades[]`` (multi-anexo exige discriminação por idAtividade).


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
        receitas_por_anexo={ef: receita_mes},
    )


_TOLERANCIA_SOMA = Decimal("0.01")


def calcular_das_multi_anexo(
    rbt12: Decimal,
    receitas_por_anexo: dict[str, Decimal],
    faixas_por_anexo: dict[str, list[FaixaDAS]],
    *,
    anexo_declarado: str = "I",
    fator_r: Decimal | None = None,
    uf: str | None = None,
    sublimite_estadual: Decimal | None = None,
    algoritmo_versao: str = ALGORITMO_VERSAO,
) -> ResultadoDAS:
    """Calcula DAS quando a empresa tem receitas em múltiplos anexos no mês.

    Cada anexo usa sua própria tabela CGSN (faixas), mas a RBT12 é compartilhada
    (é uma só por empresa). O DAS total é a soma dos DAS calculados por anexo.

    Args:
        rbt12: RBT12 compartilhada — mesma para todos os anexos.
        receitas_por_anexo: ``{"I": Decimal("10000"), "III": Decimal("5000")}``.
            Apenas anexos com receita > 0 são processados.
        faixas_por_anexo: ``{"I": [FaixaDAS, ...], "III": [...]}``. Cada lista é
            a tabela CGSN vigente daquele anexo no mês de competência.
        anexo_declarado: Anexo "principal" da empresa (informativo no resultado).
        fator_r: Quando informado e empresa tem Anexo III/V, é aplicado APENAS
            à parcela do Anexo III/V; demais anexos não são afetados.
        uf, sublimite_estadual, algoritmo_versao: Idem ``calcular_das``.

    Returns:
        ResultadoDAS com ``valor`` somado e ``receitas_por_anexo`` preservado.
        ``anexo_efetivo`` reflete o anexo principal (após resolução Fator R, se
        aplicável); ``aliquota_efetiva`` reflete o anexo principal (informativa).

    Raises:
        ValueError: ``receitas_por_anexo`` vazio ou ``faixas_por_anexo`` faltando
            tabela para algum anexo presente.
        EmpresaForaSimplesNacional: ``rbt12`` > teto federal R$4.800.000.
    """
    if not receitas_por_anexo:
        raise ValueError("receitas_por_anexo não pode ser vazio")

    receitas_positivas = {a: r for a, r in receitas_por_anexo.items() if r > _ZERO}
    if not receitas_positivas:
        raise ValueError("ao menos um anexo deve ter receita > 0")

    anexos_faltando = set(receitas_positivas) - set(faixas_por_anexo)
    if anexos_faltando:
        raise ValueError(
            f"faixas_por_anexo não cobre os anexos: {sorted(anexos_faltando)}"
        )

    # Resolução de Fator R aplica-se SOMENTE quando há receita em III ou V.
    anexo_efetivo_principal = anexo_declarado
    if anexo_declarado in ("III", "V") and fator_r is not None:
        anexo_efetivo_principal = resolver_anexo_fator_r(anexo_declarado, fator_r)
        # Se a empresa declarou III/V mas tem receita no outro, alinha:
        if anexo_declarado in receitas_positivas and anexo_efetivo_principal != anexo_declarado:
            receitas_positivas[anexo_efetivo_principal] = (
                receitas_positivas.pop(anexo_declarado)
                + receitas_positivas.get(anexo_efetivo_principal, _ZERO)
            )
            if anexo_efetivo_principal not in faixas_por_anexo:
                raise ValueError(
                    f"Fator R resolveu para {anexo_efetivo_principal}, mas "
                    f"faixas_por_anexo não tem essa tabela"
                )

    valor_total = _ZERO
    detalhes: list[ResultadoDAS] = []
    for anexo, receita in sorted(receitas_positivas.items()):
        parcial = calcular_das(
            rbt12=rbt12,
            receita_mes=receita,
            faixas=faixas_por_anexo[anexo],
            anexo=anexo,
            anexo_efetivo=anexo,
            fator_r=fator_r if anexo == anexo_efetivo_principal else None,
            uf=uf,
            sublimite_estadual=sublimite_estadual,
            algoritmo_versao=algoritmo_versao,
        )
        valor_total += parcial.valor
        detalhes.append(parcial)

    # Resultado agregado: usa o anexo "principal" (após Fator R) como referência
    # para faixa/alíquota informativas. ``valor`` é a soma; ``receitas_por_anexo``
    # preserva a discriminação para o PGDAS-D iterar.
    principal = next(
        (d for d in detalhes if d.anexo == anexo_efetivo_principal),
        detalhes[0],
    )
    receita_total = sum(receitas_positivas.values(), start=_ZERO)

    return ResultadoDAS(
        anexo=anexo_declarado,
        anexo_efetivo=anexo_efetivo_principal,
        faixa=principal.faixa,
        rbt12_usado=rbt12,
        aliquota_nominal=principal.aliquota_nominal,
        parcela_deduzir=principal.parcela_deduzir,
        aliquota_efetiva=principal.aliquota_efetiva,
        receita_mes=receita_total,
        valor=valor_total,
        fator_r=fator_r,
        algoritmo_versao=algoritmo_versao,
        uf=uf,
        sublimite_aplicado=principal.sublimite_aplicado,
        sublimite_excedido=principal.sublimite_excedido,
        receitas_por_anexo=dict(receitas_positivas),
    )


def validar_soma_receitas(
    receita_mes: Decimal,
    receitas_por_anexo: dict[str, Decimal],
    tolerancia: Decimal = _TOLERANCIA_SOMA,
) -> None:
    """Verifica que a soma de ``receitas_por_anexo`` casa com ``receita_mes``.

    Usado por callers que recebem ambos do usuário (proteção contra input ruim).
    """
    soma = sum(receitas_por_anexo.values(), start=_ZERO)
    diferenca = (soma - receita_mes).copy_abs()
    if diferenca > tolerancia:
        raise ValueError(
            f"receitas_por_anexo soma R${soma}; esperado R${receita_mes} "
            f"(diferença R${diferenca} > tolerância R${tolerancia})"
        )
