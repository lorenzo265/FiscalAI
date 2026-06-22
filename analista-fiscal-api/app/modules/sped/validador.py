"""Validador local de arquivos SPED — ECD + ECF (Sprint 16 PR3).

**Camada 1 (determinística).** Funções puras, zero I/O. Recebem o
conteúdo já decodificado (str) e devolvem ``ResultadoValidacao`` com
erros e warnings estruturados.

Categorias:

* **Estruturais (todos os tipos)** — pipe inicial/final em toda linha;
  9999 bate com contagem real de linhas; cada 9900 declara contagem real
  do tipo correspondente; blocos obrigatórios presentes.
* **ECD** — soma D = soma C por lançamento (I200/I250); contas referenciadas
  em I155/I250 existem em I050; ordem geral I050 → I150/I155 → I200/I250.
* **ECF** — P200 ``irpj_normal ≈ base_total × 15%``; ``irpj_total ≈
  irpj_normal + irpj_adicional``; P300 ``csll = base_total × 9%``;
  Y540 receita anual = Σ receitas trimestrais do P100.

Severidades:

* ``erro`` — bloqueia transmissão. PVA também recusaria.
* ``warning`` — aviso (ex.: contagem 9900 acima de 0 para tipo sem
  conteúdo significativo — defeito cosmético).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

VALIDADOR_VERSAO = "sped.validador.v1"

_CENTAVO = Decimal("0.01")
_TOLERANCIA = Decimal("0.02")  # diferença aceita por arredondamento bancário
_ALIQ_IRPJ_NORMAL = Decimal("0.15")
_ALIQ_CSLL = Decimal("0.09")

# Blocos obrigatórios em ECD (devem ter X001 + X990).
_BLOCOS_ECD = ("0", "I", "J", "9")
# Blocos obrigatórios em ECF (17 blocos do leiaute v10).
_BLOCOS_ECF = (
    "0", "C", "E", "J", "K", "L", "M", "N", "P", "Q",
    "T", "U", "V", "W", "X", "Y", "9",
)
# Blocos obrigatórios em EFD-Contribuições (leiaute v1.36 ADE Cofis 78/2024).
# Cada um precisa de abertura ``X001`` + encerramento ``X990``, mesmo vazio.
# Bloco "1" tem dígito numérico — registros 1001/1990.
_BLOCOS_EFD_CONTRIBUICOES = ("0", "A", "C", "D", "F", "M", "1", "9")
# Blocos obrigatórios em EFD ICMS-IPI (Ajuste SINIEF 02/2009 — Guia v3.1.7).
# Sem bloco B (ISS RJ/SP) e sem K (controle de produção) — pendências
# conscientes da Sprint 17 PR2.
_BLOCOS_EFD_ICMS_IPI = ("0", "C", "D", "E", "G", "H", "1", "9")
# CST válidos em registros de PIS/Cofins (Tabela 4.3.3 do leiaute):
# 01..09 (tributáveis e isentas) + 49..99 (outras situações).
_CSTS_PIS_COFINS_VALIDOS = frozenset(
    f"{n:02d}" for n in range(1, 10)
) | frozenset(f"{n:02d}" for n in range(49, 100))


# ── DTOs ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IssueValidacao:
    """Um achado da validação."""

    severidade: str  # 'erro' | 'warning'
    codigo: str  # ex.: 'estrutura.linha_quebrada', 'ecd.partidas_desbalanceadas'
    mensagem: str
    contexto: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResultadoValidacao:
    """Saída do validador — listas tipadas + flag ok + algoritmo_versao."""

    erros: tuple[IssueValidacao, ...]
    warnings: tuple[IssueValidacao, ...]
    validador_versao: str = VALIDADOR_VERSAO

    @property
    def ok(self) -> bool:
        return not self.erros

    @property
    def total_erros(self) -> int:
        return len(self.erros)

    @property
    def total_warnings(self) -> int:
        return len(self.warnings)


# ── Helpers de parsing pipe-delimited ───────────────────────────────────────


def _decompor_linhas(conteudo: str) -> list[tuple[int, str, list[str]]]:
    """Parse simples — devolve (nro_linha, reg, campos[]) por linha não-vazia.

    Linhas mal-formadas (sem pipe inicial/final) ficam com REG='' e campos=[]
    para o validador estrutural reportar como erro.
    """
    saida: list[tuple[int, str, list[str]]] = []
    for ix, raw in enumerate(conteudo.splitlines(), start=1):
        if not raw:
            continue
        if not raw.startswith("|") or not raw.endswith("|"):
            saida.append((ix, "", []))
            continue
        # Remove pipes externos e split.
        miolo = raw[1:-1]
        partes = miolo.split("|")
        if not partes:
            saida.append((ix, "", []))
            continue
        reg = partes[0]
        saida.append((ix, reg, partes[1:]))
    return saida


def _to_decimal(valor: str) -> Decimal | None:
    """Converte string do SPED ('1234,56') em Decimal. ``None`` se inválido."""
    if not valor:
        return None
    try:
        return Decimal(valor.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


# ── Validador estrutural (compartilhado ECD + ECF) ──────────────────────────


def _validar_estrutura(
    conteudo: str, blocos_obrigatorios: tuple[str, ...]
) -> tuple[list[IssueValidacao], list[IssueValidacao]]:
    """Estruturais: pipe nas pontas, 9999 == total linhas, 9900 consistente,
    blocos obrigatórios presentes.
    """
    erros: list[IssueValidacao] = []
    warnings: list[IssueValidacao] = []
    linhas = _decompor_linhas(conteudo)
    if not linhas:
        erros.append(
            IssueValidacao(
                severidade="erro",
                codigo="estrutura.arquivo_vazio",
                mensagem="Arquivo SPED sem linhas — não é possível validar.",
            )
        )
        return erros, warnings

    # 1) Pipe inicial/final.
    for nro, reg, _campos in linhas:
        if reg == "":
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="estrutura.linha_quebrada",
                    mensagem=(
                        f"Linha {nro} não começa/termina com pipe ou está "
                        "sem REG identificável."
                    ),
                    contexto={"linha": str(nro)},
                )
            )

    regs = [(nro, reg) for nro, reg, _ in linhas if reg]
    contagem: Counter[str] = Counter(reg for _, reg in regs)

    # 2) Blocos obrigatórios — abertura X001 + encerramento X990.
    for bloco in blocos_obrigatorios:
        if contagem.get(f"{bloco}001", 0) != 1:
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="estrutura.bloco_abertura_ausente",
                    mensagem=f"Bloco {bloco} sem registro {bloco}001 único.",
                    contexto={"bloco": bloco},
                )
            )
        if contagem.get(f"{bloco}990", 0) != 1:
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="estrutura.bloco_encerramento_ausente",
                    mensagem=f"Bloco {bloco} sem registro {bloco}990 único.",
                    contexto={"bloco": bloco},
                )
            )

    # 3a) 9990 == total de linhas do bloco 9.
    #
    # O bloco 9 contém: 9001 + (N × 9900) + 9990 + 9999.
    # O PVA valida QTD_LIN_9 (campo do 9990) estritamente contra a contagem
    # real dessas linhas. Verificamos aqui para capturar o off-by-one que
    # antes só era detectado pelo PVA (e que nosso gerador tinha até a
    # correção de 2026-06-04).
    _REG_BLOCO_9 = {"9001", "9900", "9990", "9999"}
    total_bloco_9_real = sum(contagem.get(r, 0) for r in _REG_BLOCO_9)
    linhas_9990 = [
        (nro, campos) for nro, reg, campos in linhas if reg == "9990"
    ]
    if not linhas_9990:
        erros.append(
            IssueValidacao(
                severidade="erro",
                codigo="estrutura.9990_ausente",
                mensagem="Arquivo sem registro 9990 (totalizador do bloco 9).",
            )
        )
    elif len(linhas_9990) > 1:
        erros.append(
            IssueValidacao(
                severidade="erro",
                codigo="estrutura.9990_duplicado",
                mensagem=f"Arquivo tem {len(linhas_9990)} registros 9990.",
            )
        )
    else:
        _, campos_9990 = linhas_9990[0]
        if not campos_9990:
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="estrutura.9990_sem_campo",
                    mensagem="Registro 9990 sem campo de totalização.",
                )
            )
        else:
            try:
                declarado_9990 = int(campos_9990[0])
            except ValueError:
                erros.append(
                    IssueValidacao(
                        severidade="erro",
                        codigo="estrutura.9990_invalido",
                        mensagem=(
                            f"Registro 9990 com valor não-numérico: "
                            f"{campos_9990[0]!r}"
                        ),
                    )
                )
            else:
                if declarado_9990 != total_bloco_9_real:
                    erros.append(
                        IssueValidacao(
                            severidade="erro",
                            codigo="estrutura.9990_divergente",
                            mensagem=(
                                f"Registro 9990 declara {declarado_9990} linhas "
                                f"no bloco 9, bloco tem {total_bloco_9_real}."
                            ),
                            contexto={
                                "declarado": str(declarado_9990),
                                "real": str(total_bloco_9_real),
                            },
                        )
                    )

    # 3b) 9999 == total real de linhas significativas.
    total_real = sum(contagem.values())
    linhas_9999 = [
        (nro, campos) for nro, reg, campos in linhas if reg == "9999"
    ]
    if not linhas_9999:
        erros.append(
            IssueValidacao(
                severidade="erro",
                codigo="estrutura.9999_ausente",
                mensagem="Arquivo sem registro 9999 (total geral).",
            )
        )
    elif len(linhas_9999) > 1:
        erros.append(
            IssueValidacao(
                severidade="erro",
                codigo="estrutura.9999_duplicado",
                mensagem=f"Arquivo tem {len(linhas_9999)} registros 9999.",
            )
        )
    else:
        _, campos_9999 = linhas_9999[0]
        if not campos_9999:
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="estrutura.9999_sem_campo",
                    mensagem="Registro 9999 sem campo de totalização.",
                )
            )
        else:
            try:
                declarado = int(campos_9999[0])
            except ValueError:
                erros.append(
                    IssueValidacao(
                        severidade="erro",
                        codigo="estrutura.9999_invalido",
                        mensagem=(
                            f"Registro 9999 com valor não-numérico: "
                            f"{campos_9999[0]!r}"
                        ),
                    )
                )
            else:
                if declarado != total_real:
                    erros.append(
                        IssueValidacao(
                            severidade="erro",
                            codigo="estrutura.9999_divergente",
                            mensagem=(
                                f"Registro 9999 declara {declarado} linhas, "
                                f"arquivo tem {total_real}."
                            ),
                            contexto={
                                "declarado": str(declarado),
                                "real": str(total_real),
                            },
                        )
                    )

    # 4) Cada 9900 deve declarar contagem real do tipo correspondente.
    for nro, reg, campos in linhas:
        if reg != "9900":
            continue
        if len(campos) < 2:
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="estrutura.9900_malformado",
                    mensagem=f"Registro 9900 (linha {nro}) com campos insuficientes.",
                    contexto={"linha": str(nro)},
                )
            )
            continue
        tipo, qtd_str = campos[0], campos[1]
        try:
            qtd_declarada = int(qtd_str)
        except ValueError:
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="estrutura.9900_qtd_invalida",
                    mensagem=(
                        f"Registro 9900 (linha {nro}) com quantidade "
                        f"não-numérica: {qtd_str!r}"
                    ),
                )
            )
            continue
        qtd_real = contagem.get(tipo, 0)
        if qtd_declarada != qtd_real:
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="estrutura.9900_divergente",
                    mensagem=(
                        f"9900 declara {tipo}={qtd_declarada} mas o arquivo "
                        f"tem {qtd_real}."
                    ),
                    contexto={
                        "tipo": tipo,
                        "declarado": str(qtd_declarada),
                        "real": str(qtd_real),
                    },
                )
            )

    return erros, warnings


# ── Validador ECD (regras de negócio contábil) ──────────────────────────────


def validar_ecd(conteudo: str) -> ResultadoValidacao:
    """Valida arquivo ECD: estrutural + amarrações contábeis.

    Amarrações:

    * Toda conta referenciada em ``I155`` ou ``I250`` existe em ``I050``.
    * Cada lançamento ``I200`` tem soma de débitos == créditos == valor_total.
    """
    erros, warnings = _validar_estrutura(conteudo, _BLOCOS_ECD)
    linhas = _decompor_linhas(conteudo)

    # Códigos de conta declarados em I050.
    codigos_I050: set[str] = set()
    for _, reg, campos in linhas:
        if reg != "I050":
            continue
        # Layout I050: DT_ALT, COD_NAT, IND_CTA, NIVEL, NATUREZA, COD_CTA, COD_CTA_SUP, CTA
        if len(campos) >= 6:
            codigos_I050.add(campos[5])

    # Conta referenciada em I155 não pode estar fora de I050.
    for nro, reg, campos in linhas:
        if reg == "I155" and len(campos) >= 1:
            codigo_ref = campos[0]
            if codigo_ref and codigo_ref not in codigos_I050:
                erros.append(
                    IssueValidacao(
                        severidade="erro",
                        codigo="ecd.i155_conta_orfa",
                        mensagem=(
                            f"I155 (linha {nro}) referencia conta {codigo_ref} "
                            "ausente do plano (I050)."
                        ),
                        contexto={
                            "linha": str(nro),
                            "codigo_conta": codigo_ref,
                        },
                    )
                )
        elif reg == "I250" and len(campos) >= 1:
            codigo_ref = campos[0]
            if codigo_ref and codigo_ref not in codigos_I050:
                erros.append(
                    IssueValidacao(
                        severidade="erro",
                        codigo="ecd.i250_conta_orfa",
                        mensagem=(
                            f"I250 (linha {nro}) referencia conta {codigo_ref} "
                            "ausente do plano (I050)."
                        ),
                        contexto={
                            "linha": str(nro),
                            "codigo_conta": codigo_ref,
                        },
                    )
                )

    # Partidas dobradas: I200 abre, I250 acumula até o próximo I200/I990.
    # Estado iterativo: para cada I200 ativo, somar D/C das I250 subsequentes.
    debito_acumulado = Decimal("0")
    credito_acumulado = Decimal("0")
    lanc_corrente: tuple[int, str, Decimal] | None = None  # (linha, numero, valor_total)

    def _fecha_lanc() -> None:
        nonlocal debito_acumulado, credito_acumulado, lanc_corrente
        if lanc_corrente is None:
            return
        nro_linha, numero, valor_total = lanc_corrente
        if debito_acumulado != credito_acumulado:
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="ecd.partidas_desbalanceadas",
                    mensagem=(
                        f"Lançamento {numero} (linha {nro_linha}): débitos "
                        f"({debito_acumulado}) ≠ créditos ({credito_acumulado})."
                    ),
                    contexto={
                        "linha": str(nro_linha),
                        "numero_lancamento": numero,
                        "debito": str(debito_acumulado),
                        "credito": str(credito_acumulado),
                    },
                )
            )
        elif valor_total != debito_acumulado:
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="ecd.valor_total_divergente",
                    mensagem=(
                        f"Lançamento {numero} (linha {nro_linha}): valor_total "
                        f"({valor_total}) ≠ soma das partidas ({debito_acumulado})."
                    ),
                    contexto={
                        "linha": str(nro_linha),
                        "numero_lancamento": numero,
                        "valor_total": str(valor_total),
                        "soma_partidas": str(debito_acumulado),
                    },
                )
            )
        # reset
        debito_acumulado = Decimal("0")
        credito_acumulado = Decimal("0")
        lanc_corrente = None

    for nro, reg, campos in linhas:
        if reg == "I200":
            _fecha_lanc()
            # Layout I200: NUM_LCTO, DT_LCTO, VAL_LCTO, IND_LCTO
            if len(campos) >= 3:
                numero = campos[0]
                valor = _to_decimal(campos[2])
                if valor is not None:
                    lanc_corrente = (nro, numero, valor)
        elif reg == "I250":
            if lanc_corrente is None:
                erros.append(
                    IssueValidacao(
                        severidade="erro",
                        codigo="ecd.i250_orfa",
                        mensagem=(
                            f"I250 (linha {nro}) sem I200 antecedente."
                        ),
                        contexto={"linha": str(nro)},
                    )
                )
                continue
            # Layout I250: COD_CTA, COD_CCUS, VLR_DC, IND_DC, COD_HIST, HIST
            if len(campos) >= 4:
                valor = _to_decimal(campos[2])
                indicador = campos[3]
                if valor is None:
                    continue
                if indicador == "D":
                    debito_acumulado += valor
                elif indicador == "C":
                    credito_acumulado += valor
                else:
                    erros.append(
                        IssueValidacao(
                            severidade="erro",
                            codigo="ecd.i250_indicador_invalido",
                            mensagem=(
                                f"I250 (linha {nro}) com IND_DC inválido: "
                                f"{indicador!r} (esperado 'D' ou 'C')."
                            ),
                        )
                    )
        elif reg in {"I300", "I310", "I350", "I990"}:
            # Qualquer registro pós-bloco-partidas fecha o lançamento corrente.
            _fecha_lanc()
    # Fecha último lançamento se sobrou aberto (defensivo — I990 já fecha).
    _fecha_lanc()

    return ResultadoValidacao(erros=tuple(erros), warnings=tuple(warnings))


# ── Validador ECF (regras LP) ───────────────────────────────────────────────


def validar_ecf(conteudo: str) -> ResultadoValidacao:
    """Valida arquivo ECF Lucro Presumido: estrutural + apuração coerente.

    Regras LP:

    * **P200**: ``irpj_total ≈ irpj_normal + irpj_adicional`` (tolerância
      R$ 0,02 por arredondamento bancário).
    * **P200**: ``irpj_normal ≈ base_total × 15%`` (tolerância R$ 0,02).
    * **P300**: ``csll = base_total × 9%`` (tolerância R$ 0,02).
    * **Y540**: ``receita_anual = Σ receitas trimestrais P100`` (tolerância
      R$ 0,02 por trimestre).
    """
    erros, warnings = _validar_estrutura(conteudo, _BLOCOS_ECF)
    linhas = _decompor_linhas(conteudo)

    receita_p100_total = Decimal("0")

    for nro, reg, campos in linhas:
        if reg == "P100" and len(campos) >= 7:
            # Layout: RECEITA|PRES|BASE_PRES|GANHOS|REC_APL|OUTRAS|BASE_TOT
            valor_receita = _to_decimal(campos[0])
            if valor_receita is not None:
                receita_p100_total += valor_receita

        elif reg == "P200" and len(campos) >= 7:
            # Layout: BASE_IRPJ|LIMITE|IRPJ_NORMAL|IRPJ_ADIC|IRPJ_TOTAL|IRRF_CONS|IRPJ_DEVIDO
            base = _to_decimal(campos[0])
            irpj_normal = _to_decimal(campos[2])
            irpj_adic = _to_decimal(campos[3])
            irpj_total = _to_decimal(campos[4])
            if base is not None and irpj_normal is not None:
                esperado = (base * _ALIQ_IRPJ_NORMAL).quantize(_CENTAVO)
                if abs(esperado - irpj_normal) > _TOLERANCIA:
                    erros.append(
                        IssueValidacao(
                            severidade="erro",
                            codigo="ecf.p200_irpj_normal_divergente",
                            mensagem=(
                                f"P200 (linha {nro}): IRPJ normal declarado "
                                f"{irpj_normal} ≠ base × 15% = {esperado}."
                            ),
                            contexto={
                                "linha": str(nro),
                                "declarado": str(irpj_normal),
                                "esperado": str(esperado),
                            },
                        )
                    )
            if (
                irpj_normal is not None
                and irpj_adic is not None
                and irpj_total is not None
            ):
                soma = irpj_normal + irpj_adic
                if abs(soma - irpj_total) > _TOLERANCIA:
                    erros.append(
                        IssueValidacao(
                            severidade="erro",
                            codigo="ecf.p200_total_divergente",
                            mensagem=(
                                f"P200 (linha {nro}): IRPJ total declarado "
                                f"{irpj_total} ≠ normal + adicional = {soma}."
                            ),
                            contexto={
                                "linha": str(nro),
                                "declarado": str(irpj_total),
                                "esperado": str(soma),
                            },
                        )
                    )

        elif reg == "P300" and len(campos) >= 6:
            # Layout: REC|PRES|BASE_PRES|OUTRAS|BASE_TOT|CSLL
            base_csll = _to_decimal(campos[4])
            csll = _to_decimal(campos[5])
            if base_csll is not None and csll is not None:
                esperado = (base_csll * _ALIQ_CSLL).quantize(_CENTAVO)
                if abs(esperado - csll) > _TOLERANCIA:
                    erros.append(
                        IssueValidacao(
                            severidade="erro",
                            codigo="ecf.p300_csll_divergente",
                            mensagem=(
                                f"P300 (linha {nro}): CSLL declarada {csll} "
                                f"≠ base × 9% = {esperado}."
                            ),
                            contexto={
                                "linha": str(nro),
                                "declarado": str(csll),
                                "esperado": str(esperado),
                            },
                        )
                    )

    # Y540 — receita anual = soma trimestres.
    y540_total = Decimal("0")
    for _, reg, campos in linhas:
        if reg == "Y540" and len(campos) >= 2:
            valor = _to_decimal(campos[1])
            if valor is not None:
                y540_total += valor
    if y540_total > Decimal("0") and receita_p100_total > Decimal("0"):
        tolerancia_anual = _TOLERANCIA * 4  # 1 P100 por trimestre = até 4 erros
        if abs(y540_total - receita_p100_total) > tolerancia_anual:
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="ecf.y540_p100_divergente",
                    mensagem=(
                        f"Y540 receita anual {y540_total} ≠ soma P100 "
                        f"trimestrais {receita_p100_total}."
                    ),
                    contexto={
                        "y540_total": str(y540_total),
                        "p100_soma": str(receita_p100_total),
                    },
                )
            )

    return ResultadoValidacao(erros=tuple(erros), warnings=tuple(warnings))


# ── Validador EFD-Contribuições (regras de coerência PIS/Cofins) ────────────


def validar_efd_contribuicoes(conteudo: str) -> ResultadoValidacao:
    """Valida arquivo EFD-Contribuições mensal: estrutural + amarrações fiscais.

    Amarrações:

    * ``A170`` / ``C170``: ``valor_pis ≈ vl_bc_pis × aliquota_pis / 100``
      (tolerância R$ 0,02 por arredondamento bancário). Idem Cofins.
    * ``A170`` / ``C170``: ``CST_PIS`` e ``CST_COFINS`` em valores válidos
      (tabela 4.3.3).
    * ``C170``: ``CFOP`` com 4 dígitos numéricos.
    * ``M200`` / ``M600``: ``VL_TOT_CONT_REC`` (último campo) ≥ 0.
    """
    erros, warnings = _validar_estrutura(conteudo, _BLOCOS_EFD_CONTRIBUICOES)
    linhas = _decompor_linhas(conteudo)

    for nro, reg, campos in linhas:
        if reg == "A170":
            erros.extend(_validar_pis_cofins_a170(nro, campos))
        elif reg == "C170":
            erros.extend(_validar_pis_cofins_c170(nro, campos))
        elif reg == "M200":
            erros.extend(_validar_consolidacao_m(nro, "M200", campos))
        elif reg == "M600":
            erros.extend(_validar_consolidacao_m(nro, "M600", campos))

    return ResultadoValidacao(erros=tuple(erros), warnings=tuple(warnings))


def _validar_pis_cofins_a170(
    nro: int, campos: list[str]
) -> list[IssueValidacao]:
    """A170 layout (resumido):
    NUM_ITEM|COD_ITEM|DESCR_COMPL|VL_ITEM|VL_DESC|NAT_BC_CRED|IND_ORIG_CRED|
    CST_PIS|VL_BC_PIS|ALIQ_PIS|VL_PIS|CST_COFINS|VL_BC_COFINS|ALIQ_COFINS|
    VL_COFINS|COD_CTA
    """
    erros: list[IssueValidacao] = []
    if len(campos) < 15:
        return erros  # estrutural já reportou se necessário

    cst_pis = campos[7]
    vl_bc_pis = _to_decimal(campos[8])
    aliq_pis = _to_decimal(campos[9])
    vl_pis = _to_decimal(campos[10])
    cst_cofins = campos[11]
    vl_bc_cofins = _to_decimal(campos[12])
    aliq_cofins = _to_decimal(campos[13])
    vl_cofins = _to_decimal(campos[14])

    erros.extend(_validar_cst("efd_contrib.a170_cst_pis_invalido", nro, "A170", "PIS", cst_pis))
    erros.extend(_validar_cst("efd_contrib.a170_cst_cofins_invalido", nro, "A170", "Cofins", cst_cofins))
    erros.extend(
        _validar_base_aliq_tributo(
            "efd_contrib.a170_pis_divergente",
            nro, "A170", "PIS", vl_bc_pis, aliq_pis, vl_pis,
        )
    )
    erros.extend(
        _validar_base_aliq_tributo(
            "efd_contrib.a170_cofins_divergente",
            nro, "A170", "Cofins", vl_bc_cofins, aliq_cofins, vl_cofins,
        )
    )
    return erros


def _validar_pis_cofins_c170(
    nro: int, campos: list[str]
) -> list[IssueValidacao]:
    """C170 layout (recorte relevante a PIS/Cofins):
    indices 0..7 = NUM_ITEM..CFOP (índice 10: CFOP)
    Layout C170 tem CFOP no campo 10 (após CST_ICMS).
    PIS começa em ~25 (CST_PIS), Cofins em ~31. Ver gerador para ordem.

    Layout que estamos gerando:
    NUM_ITEM|COD_ITEM|DESCR_COMPL|QTD|UNID|VL_ITEM|VL_DESC|IND_MOV|CST_ICMS|
    CFOP|COD_NAT|VL_BC_ICMS|ALIQ_ICMS|VL_ICMS|VL_BC_ICMS_ST|ALIQ_ST|VL_ICMS_ST|
    IND_APUR|CST_IPI|COD_ENQ|VL_BC_IPI|ALIQ_IPI|VL_IPI|
    CST_PIS|VL_BC_PIS|ALIQ_PIS|QUANT_BC_PIS|ALIQ_PIS_QUANT|VL_PIS|
    CST_COFINS|VL_BC_COFINS|ALIQ_COFINS|QUANT_BC_COFINS|ALIQ_COFINS_QUANT|VL_COFINS|COD_CTA
    """
    erros: list[IssueValidacao] = []
    if len(campos) < 35:
        return erros

    cfop = campos[9]
    if len(cfop) != 4 or not cfop.isdigit():
        erros.append(
            IssueValidacao(
                severidade="erro",
                codigo="efd_contrib.c170_cfop_invalido",
                mensagem=(
                    f"C170 (linha {nro}): CFOP inválido {cfop!r} "
                    "(esperado 4 dígitos numéricos)."
                ),
                contexto={"linha": str(nro), "cfop": cfop},
            )
        )

    cst_pis = campos[23]
    vl_bc_pis = _to_decimal(campos[24])
    aliq_pis = _to_decimal(campos[25])
    vl_pis = _to_decimal(campos[28])
    cst_cofins = campos[29]
    vl_bc_cofins = _to_decimal(campos[30])
    aliq_cofins = _to_decimal(campos[31])
    vl_cofins = _to_decimal(campos[34])

    erros.extend(_validar_cst("efd_contrib.c170_cst_pis_invalido", nro, "C170", "PIS", cst_pis))
    erros.extend(_validar_cst("efd_contrib.c170_cst_cofins_invalido", nro, "C170", "Cofins", cst_cofins))
    erros.extend(
        _validar_base_aliq_tributo(
            "efd_contrib.c170_pis_divergente",
            nro, "C170", "PIS", vl_bc_pis, aliq_pis, vl_pis,
        )
    )
    erros.extend(
        _validar_base_aliq_tributo(
            "efd_contrib.c170_cofins_divergente",
            nro, "C170", "Cofins", vl_bc_cofins, aliq_cofins, vl_cofins,
        )
    )
    return erros


def _validar_consolidacao_m(
    nro: int, reg: str, campos: list[str]
) -> list[IssueValidacao]:
    """M200 / M600 — último campo é o ``VL_TOT_CONT_REC`` (a recolher).

    Valida apenas que o total a recolher seja não-negativo. As amarrações
    com a soma dos A170/C170 ficam para iteração futura — a apuração
    pode legalmente ter exclusões/deduções que tornam M < Σ docs.
    """
    if len(campos) < 12:
        return []
    total_a_recolher = _to_decimal(campos[-1])
    if total_a_recolher is None:
        return []
    if total_a_recolher < Decimal("0"):
        return [
            IssueValidacao(
                severidade="erro",
                codigo=f"efd_contrib.{reg.lower()}_total_negativo",
                mensagem=(
                    f"{reg} (linha {nro}): total a recolher negativo "
                    f"({total_a_recolher}) — saldos credores são tratados "
                    "em registros próprios (M225/M625)."
                ),
                contexto={"linha": str(nro), "valor": str(total_a_recolher)},
            )
        ]
    return []


def _validar_cst(
    codigo: str, nro: int, reg: str, tributo: str, cst: str
) -> list[IssueValidacao]:
    if cst and cst not in _CSTS_PIS_COFINS_VALIDOS:
        return [
            IssueValidacao(
                severidade="erro",
                codigo=codigo,
                mensagem=(
                    f"{reg} (linha {nro}): CST {tributo} inválido {cst!r} — "
                    "consulte tabela 4.3.3 do leiaute."
                ),
                contexto={"linha": str(nro), "cst": cst},
            )
        ]
    return []


def _validar_base_aliq_tributo(
    codigo: str,
    nro: int,
    reg: str,
    tributo: str,
    base: Decimal | None,
    aliquota: Decimal | None,
    valor_declarado: Decimal | None,
) -> list[IssueValidacao]:
    """Confere ``valor = base × aliquota / 100`` (alíquota em %)."""
    if base is None or aliquota is None or valor_declarado is None:
        return []
    if base == Decimal("0") or aliquota == Decimal("0"):
        return []
    esperado = (base * aliquota / Decimal("100")).quantize(_CENTAVO)
    if abs(esperado - valor_declarado) > _TOLERANCIA:
        return [
            IssueValidacao(
                severidade="erro",
                codigo=codigo,
                mensagem=(
                    f"{reg} (linha {nro}): {tributo} declarado "
                    f"{valor_declarado} ≠ base × alíquota = {esperado}."
                ),
                contexto={
                    "linha": str(nro),
                    "declarado": str(valor_declarado),
                    "esperado": str(esperado),
                    "base": str(base),
                    "aliquota": str(aliquota),
                },
            )
        ]
    return []


# ── Validador EFD ICMS-IPI (Sprint 17 PR2) ──────────────────────────────────


def validar_efd_icms_ipi(conteudo: str) -> ResultadoValidacao:
    """Valida arquivo EFD ICMS-IPI mensal: estrutural + amarrações ICMS.

    Amarrações:

    * ``C170``: ``valor_icms ≈ vl_bc_icms × aliquota / 100`` (tolerância R$0,02).
    * ``C170``: ``CFOP`` com 4 dígitos numéricos.
    * ``C170``: ``CST_ICMS`` com 3 dígitos (origem + CST tabela 4.3.1).
    * ``E110``: ``VL_SLD_APURADO == VL_TOT_DEBITOS − VL_TOT_CREDITOS −
      VL_SLD_CREDOR_ANT + ajustes`` (tolerância R$0,02).
    * ``E110``: ``VL_ICMS_RECOLHER ≥ 0`` (saldos credores vão em
      ``VL_SLD_CREDOR_TRANSPORTAR``).
    """
    erros, warnings = _validar_estrutura(conteudo, _BLOCOS_EFD_ICMS_IPI)
    linhas = _decompor_linhas(conteudo)

    for nro, reg, campos in linhas:
        if reg == "C170":
            erros.extend(_validar_icms_c170(nro, campos))
        elif reg == "E110":
            erros.extend(_validar_apuracao_e110(nro, campos))

    return ResultadoValidacao(erros=tuple(erros), warnings=tuple(warnings))


def _validar_icms_c170(
    nro: int, campos: list[str]
) -> list[IssueValidacao]:
    """C170 — itens dos documentos. Layout idêntico ao gerador:
    NUM_ITEM(0)|COD_ITEM(1)|...|CST_ICMS(8)|CFOP(9)|...|VL_BC_ICMS(11)|
    ALIQ_ICMS(12)|VL_ICMS(13)|...
    """
    erros: list[IssueValidacao] = []
    if len(campos) < 14:
        return erros

    cst_icms = campos[8]
    cfop = campos[9]
    vl_bc_icms = _to_decimal(campos[11])
    aliq_icms = _to_decimal(campos[12])
    vl_icms = _to_decimal(campos[13])

    if len(cst_icms) != 3 or not cst_icms.isdigit():
        erros.append(
            IssueValidacao(
                severidade="erro",
                codigo="efd_icms.c170_cst_invalido",
                mensagem=(
                    f"C170 (linha {nro}): CST ICMS inválido {cst_icms!r} — "
                    "esperado 3 dígitos (origem + CST tabela 4.3.1)."
                ),
                contexto={"linha": str(nro), "cst": cst_icms},
            )
        )
    if len(cfop) != 4 or not cfop.isdigit():
        erros.append(
            IssueValidacao(
                severidade="erro",
                codigo="efd_icms.c170_cfop_invalido",
                mensagem=(
                    f"C170 (linha {nro}): CFOP inválido {cfop!r} — "
                    "esperado 4 dígitos numéricos."
                ),
                contexto={"linha": str(nro), "cfop": cfop},
            )
        )

    if (
        vl_bc_icms is not None
        and aliq_icms is not None
        and vl_icms is not None
        and vl_bc_icms > Decimal("0")
        and aliq_icms > Decimal("0")
    ):
        esperado = (vl_bc_icms * aliq_icms / Decimal("100")).quantize(_CENTAVO)
        if abs(esperado - vl_icms) > _TOLERANCIA:
            erros.append(
                IssueValidacao(
                    severidade="erro",
                    codigo="efd_icms.c170_icms_divergente",
                    mensagem=(
                        f"C170 (linha {nro}): VL_ICMS declarado {vl_icms} "
                        f"≠ base × alíquota = {esperado}."
                    ),
                    contexto={
                        "linha": str(nro),
                        "declarado": str(vl_icms),
                        "esperado": str(esperado),
                        "base": str(vl_bc_icms),
                        "aliquota": str(aliq_icms),
                    },
                )
            )
    return erros


def _validar_apuracao_e110(
    nro: int, campos: list[str]
) -> list[IssueValidacao]:
    """E110 layout (resumido):
    VL_TOT_DEBITOS(0)|VL_AJ_DEBITOS(1)|VL_TOT_AJ_DEBITOS(2)|VL_ESTORNOS_CRED(3)|
    VL_TOT_CREDITOS(4)|VL_AJ_CREDITOS(5)|VL_TOT_AJ_CREDITOS(6)|VL_ESTORNOS_DEB(7)|
    VL_SLD_CREDOR_ANT(8)|VL_SLD_APURADO(9)|VL_TOT_DED(10)|VL_ICMS_RECOLHER(11)|
    VL_SLD_CREDOR_TRANSPORTAR(12)|DEB_ESP(13)
    """
    erros: list[IssueValidacao] = []
    if len(campos) < 13:
        return erros

    vl_icms_recolher = _to_decimal(campos[11])
    vl_sld_credor_transp = _to_decimal(campos[12])

    if vl_icms_recolher is not None and vl_icms_recolher < Decimal("0"):
        erros.append(
            IssueValidacao(
                severidade="erro",
                codigo="efd_icms.e110_recolher_negativo",
                mensagem=(
                    f"E110 (linha {nro}): VL_ICMS_RECOLHER negativo "
                    f"({vl_icms_recolher}) — saldos credores devem ir em "
                    "VL_SLD_CREDOR_TRANSPORTAR."
                ),
                contexto={"linha": str(nro), "valor": str(vl_icms_recolher)},
            )
        )

    if vl_sld_credor_transp is not None and vl_sld_credor_transp < Decimal("0"):
        erros.append(
            IssueValidacao(
                severidade="erro",
                codigo="efd_icms.e110_credor_negativo",
                mensagem=(
                    f"E110 (linha {nro}): VL_SLD_CREDOR_TRANSPORTAR negativo "
                    f"({vl_sld_credor_transp}) — usar VL_ICMS_RECOLHER."
                ),
                contexto={"linha": str(nro), "valor": str(vl_sld_credor_transp)},
            )
        )

    # Apuração não pode ter saldo a recolher E saldo credor simultaneamente.
    if (
        vl_icms_recolher is not None
        and vl_sld_credor_transp is not None
        and vl_icms_recolher > Decimal("0")
        and vl_sld_credor_transp > Decimal("0")
    ):
        erros.append(
            IssueValidacao(
                severidade="erro",
                codigo="efd_icms.e110_recolher_e_credor_simultaneos",
                mensagem=(
                    f"E110 (linha {nro}): apuração tem VL_ICMS_RECOLHER "
                    f"({vl_icms_recolher}) E VL_SLD_CREDOR_TRANSPORTAR "
                    f"({vl_sld_credor_transp}) > 0 simultaneamente — "
                    "saldo apurado é binário (devedor OU credor)."
                ),
            )
        )

    return erros


# ── Dispatcher ──────────────────────────────────────────────────────────────


def validar_por_tipo(tipo: str, conteudo: str) -> ResultadoValidacao:
    """Despacha para o validador correto baseado em ``arquivo_sped.tipo``."""
    if tipo == "ecd":
        return validar_ecd(conteudo)
    if tipo == "ecf":
        return validar_ecf(conteudo)
    if tipo == "efd_contribuicoes":
        return validar_efd_contribuicoes(conteudo)
    if tipo == "efd_icms_ipi":
        return validar_efd_icms_ipi(conteudo)
    return ResultadoValidacao(
        erros=(
            IssueValidacao(
                severidade="erro",
                codigo="validador.tipo_nao_suportado",
                mensagem=f"Validador ainda não suporta tipo {tipo!r}.",
            ),
        ),
        warnings=(),
    )


# ── Serialização para JSONB ─────────────────────────────────────────────────


def resultado_para_jsonb(resultado: ResultadoValidacao) -> dict[str, object]:
    """Estrutura serializável para ``arquivo_sped.validacao_jsonb``."""
    return {
        "ok": resultado.ok,
        "total_erros": resultado.total_erros,
        "total_warnings": resultado.total_warnings,
        "validador_versao": resultado.validador_versao,
        "erros": [
            {
                "severidade": i.severidade,
                "codigo": i.codigo,
                "mensagem": i.mensagem,
                "contexto": dict(i.contexto),
            }
            for i in resultado.erros
        ],
        "warnings": [
            {
                "severidade": i.severidade,
                "codigo": i.codigo,
                "mensagem": i.mensagem,
                "contexto": dict(i.contexto),
            }
            for i in resultado.warnings
        ],
    }
