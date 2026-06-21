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

v4 (fix/auditoria-onda-c — achado 🟠 proporcionalização RBT12 empresa nova):
- Res. CGSN 140/2018 art. 18 §§2º-3º: nos primeiros meses de atividade (< 12
  meses) o RBT12 deve ser PROPORCIONALIZADO, não substituído pela faixa 1 nominal.
  * 1º mês: RBT12_prop = receita_do_mes × 12.
  * Meses seguintes até completar 12: RBT12_prop = (receita_acumulada / meses) × 12.
- Novos parâmetros opcionais em ``calcular_das()``: ``receita_acumulada`` e
  ``meses_atividade``. Quando ambos são fornecidos e ``rbt12 == 0`` (empresa ainda
  sem histórico de 12 meses), o RBT12 proporcionalizado substitui o zero APENAS
  para encontrar a faixa e calcular a alíquota efetiva. O campo
  ``ResultadoDAS.rbt12_proporcionalizado`` sinaliza quando esse ramo foi ativado.
- Retrocompatibilidade total: chamadas sem os novos parâmetros continuam no ramo
  legado (rbt12=0 → alíquota nominal da faixa 1), preservando comportamento de
  todos os callers existentes que não fornecem dados de início de atividade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, getcontext

from app.shared.exceptions import EmpresaForaSimplesNacional

getcontext().prec = 28

ALGORITMO_VERSAO = "sn.das.v4"

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
    # ── v4: proporcionalização empresa nova ────────────────────────────
    rbt12_proporcionalizado: Decimal | None = None
    # Quando preenchido, indica que o RBT12 foi calculado via proporcionalização
    # (Res. CGSN 140/2018 art. 18 §§2º-3º) por ser empresa com < 12 meses de
    # atividade. O ``rbt12_usado`` neste caso contém o RBT12 proporcionalizado
    # (mesmo valor), e ``rbt12_proporcionalizado`` está preenchido para
    # rastreabilidade. Quando None, a empresa tem ≥ 12 meses de atividade e o
    # RBT12 real foi usado normalmente.


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


def _calcular_rbt12_proporcionalizado(
    receita_acumulada: Decimal,
    meses_atividade: int,
) -> Decimal:
    """RBT12 proporcionalizado para empresa com < 12 meses de atividade.

    Res. CGSN 140/2018 art. 18 §§2º-3º:
    - 1º mês: RBT12_prop = receita_1o_mes × 12.
    - Demais meses (até 11): RBT12_prop = (receita_acumulada / meses) × 12.
    Em ambos os casos a fórmula reduz a: (receita_acumulada / meses_atividade) × 12.
    """
    if meses_atividade <= 0:
        raise ValueError(f"meses_atividade deve ser >= 1, recebido: {meses_atividade}")
    if meses_atividade >= 12:
        raise ValueError(
            f"meses_atividade deve ser < 12 para proporcionalização; "
            f"recebido: {meses_atividade}. Use o RBT12 real para empresas com ≥ 12 meses."
        )
    if receita_acumulada < _ZERO:
        raise ValueError(f"receita_acumulada não pode ser negativa: {receita_acumulada}")
    return (receita_acumulada / Decimal(meses_atividade)) * Decimal("12")


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
    receita_acumulada: Decimal | None = None,
    meses_atividade: int | None = None,
) -> ResultadoDAS:
    """Calcula o DAS do Simples Nacional para um mês de competência.

    Args:
        rbt12: Receita Bruta dos últimos 12 meses (RBT12). Para empresa com
            menos de 12 meses de atividade, forneça ``receita_acumulada`` e
            ``meses_atividade`` em vez de um RBT12 proporcionalizado manualmente —
            a função calcula e aplica conforme Res. CGSN 140/2018 art. 18 §§2º-3º.
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
        receita_acumulada: Soma da receita bruta desde o início de atividade até
            e incluindo o mês atual (inclusive ``receita_mes``). Obrigatório junto
            com ``meses_atividade`` para empresas com < 12 meses de atividade.
            Ignorado quando ``meses_atividade`` é None ou quando ``rbt12 > 0``.
        meses_atividade: Número de meses de atividade até o mês atual, inclusive
            (mínimo 1). Quando fornecido junto com ``receita_acumulada`` e
            ``rbt12 == 0``, ativa a proporcionalização do RBT12 (Res. CGSN
            140/2018 art. 18 §§2º-3º). Deve ser < 12 (se >= 12, use o RBT12 real).

    Returns:
        ResultadoDAS imutável — pronto para persistir em apuracao_fiscal.
        ``rbt12_proporcionalizado`` fica preenchido quando a proporcionalização
        foi ativada; ``rbt12_usado`` contém o RBT12 efetivamente aplicado.

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

    # ── v4: proporcionalização RBT12 para empresa nova ─────────────────────────
    # Ativado apenas quando rbt12 == 0 (sem histórico de 12 meses) E ambos os
    # parâmetros de início de atividade são fornecidos.
    # Quando rbt12 > 0 o valor real prevalece (empresa já tem RBT12 disponível).
    rbt12_prop: Decimal | None = None
    rbt12_efetivo = rbt12

    if rbt12 == _ZERO and receita_acumulada is not None and meses_atividade is not None:
        rbt12_prop = _calcular_rbt12_proporcionalizado(receita_acumulada, meses_atividade)
        rbt12_efetivo = rbt12_prop

    if rbt12_efetivo > _TETO_FEDERAL:
        raise EmpresaForaSimplesNacional(
            f"RBT12 R${rbt12_efetivo} excedeu o teto federal R${_TETO_FEDERAL} (LC 123 art. 3º II). "
            "Empresa deve ser desenquadrada do Simples Nacional."
        )

    sublimite = sublimite_estadual if sublimite_estadual is not None else _SUBLIMITE_PADRAO
    sublimite_excedido = rbt12_efetivo > sublimite

    ef = anexo_efetivo if anexo_efetivo is not None else anexo
    faixa_obj = _encontrar_faixa(rbt12_efetivo, faixas)

    if rbt12_efetivo == _ZERO:
        # Ramo legado: rbt12=0 sem dados de início de atividade.
        # Usa alíquota nominal da faixa 1 (comportamento anterior à v4).
        # Mantido para retrocompatibilidade com callers que não fornecem
        # receita_acumulada/meses_atividade.
        aliq_raw = faixa_obj.aliquota_nominal
    else:
        aliq_raw = (rbt12_efetivo * faixa_obj.aliquota_nominal - faixa_obj.parcela_deduzir) / rbt12_efetivo

    valor = (receita_mes * aliq_raw).quantize(_CENT, rounding=ROUND_HALF_EVEN)
    aliq_display = aliq_raw.quantize(_ALIQ_DISPLAY, rounding=ROUND_HALF_EVEN)

    return ResultadoDAS(
        anexo=anexo,
        anexo_efetivo=ef,
        faixa=faixa_obj.faixa,
        rbt12_usado=rbt12_efetivo,
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
        rbt12_proporcionalizado=rbt12_prop,
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
    receita_acumulada: Decimal | None = None,
    meses_atividade: int | None = None,
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
        receita_acumulada: Idem ``calcular_das`` — propagado para cada parcela.
        meses_atividade: Idem ``calcular_das`` — propagado para cada parcela.

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
            receita_acumulada=receita_acumulada,
            meses_atividade=meses_atividade,
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

    # rbt12_proporcionalizado: todos os parciais compartilham o mesmo RBT12 (é global),
    # portanto basta pegar do principal — se ativado, todos terão o mesmo valor.
    rbt12_prop_agregado = principal.rbt12_proporcionalizado

    return ResultadoDAS(
        anexo=anexo_declarado,
        anexo_efetivo=anexo_efetivo_principal,
        faixa=principal.faixa,
        rbt12_usado=principal.rbt12_usado,  # reflete RBT12 efetivo (proporcionalizado ou real)
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
        rbt12_proporcionalizado=rbt12_prop_agregado,
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
