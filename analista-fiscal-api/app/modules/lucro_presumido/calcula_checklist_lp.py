"""Checklist de obrigações LP por trimestre — Lucro Presumido.

Camada 1 (determinística). Função pura, zero I/O.

Para cada trimestre, determina quais apurações e DARFs são obrigatórios
e marca o status de cada item: 'ok' | 'pendente' | 'atrasado'.

Obrigações por trimestre (IRPJ/CSLL/PIS/Cofins/DARF IRPJ/DARF CSLL):
  * IRPJ trimestral (Lei 9.430/1996 art. 1º)
  * CSLL trimestral (Lei 9.430/1996 art. 1º)
  * PIS mês 1, mês 2, mês 3 do trimestre (Lei 9.718/1998)
  * Cofins mês 1, mês 2, mês 3 do trimestre (Lei 9.718/1998)
  * DARF IRPJ (após apuração IRPJ)
  * DARF CSLL (após apuração CSLL)
  * DARF PIS × 3 meses
  * DARF Cofins × 3 meses

Sprint 20 PR2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

ALGORITMO_VERSAO = "lp.checklist.v1"

# Meses de cada trimestre (1-indexed)
_MESES_TRIMESTRE: dict[int, tuple[int, int, int]] = {
    1: (1, 2, 3),
    2: (4, 5, 6),
    3: (7, 8, 9),
    4: (10, 11, 12),
}

# Nomes de exibição pt-BR dos meses
_NOME_MES: dict[int, str] = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


@dataclass(frozen=True, slots=True)
class ItemChecklist:
    """Um item do checklist com seu status."""

    tipo: str           # 'apuracao_irpj' | 'apuracao_csll' | 'apuracao_pis' | ...
    descricao: str      # ex: "Apuração IRPJ — T1/2026"
    status: str         # 'ok' | 'pendente' | 'atrasado'
    competencia: date   # data canônica do item (primeiro dia do mês/trimestre)


@dataclass(frozen=True, slots=True)
class ChecklistTrimestre:
    """Checklist completo de obrigações LP para um trimestre."""

    ano: int
    trimestre: int
    itens: tuple[ItemChecklist, ...]
    total: int
    concluidos: int
    pendentes: int
    atrasados: int
    percentual_conclusao: int         # 0–100 (arredondado)
    status_geral: str                 # 'completo' | 'parcial' | 'pendente'
    algoritmo_versao: str = ALGORITMO_VERSAO

    @property
    def completo(self) -> bool:
        return self.status_geral == "completo"


def calcular_checklist_trimestre(
    ano: int,
    trimestre: int,
    *,
    apuracoes_existentes: frozenset[str],
    darfs_existentes: frozenset[str],
    data_referencia: date | None = None,
) -> ChecklistTrimestre:
    """Calcula o checklist de obrigações LP de um trimestre.

    Args:
        ano: ano-calendário (ex.: 2026).
        trimestre: 1, 2, 3 ou 4.
        apuracoes_existentes: conjunto de strings no formato "tipo:AAAA-MM-DD"
            (ex.: {"irpj:2026-01-01", "pis:2026-01-01", "pis:2026-02-01"}).
        darfs_existentes: conjunto de strings no formato "codigo_receita:AAAA-MM-DD"
            (ex.: {"2089:2026-01-01", "8109:2026-01-01"}).
        data_referencia: data atual (default: hoje). Itens com vencimento
            passado e status != 'ok' ficam como 'atrasado'.

    Returns:
        ChecklistTrimestre com status de cada obrigação.
    """
    _validar_trimestre(trimestre)

    hoje = data_referencia or date.today()
    meses = _MESES_TRIMESTRE[trimestre]
    comp_trim = date(ano, meses[0], 1)  # primeiro dia do trimestre

    itens: list[ItemChecklist] = []

    # ── Apurações trimestrais (IRPJ + CSLL) ──────────────────────────────
    for tipo_sig, tipo_nome, codigo_darf in (
        ("irpj", "IRPJ", "2089"),
        ("csll", "CSLL", "2372"),
    ):
        chave_ap = f"{tipo_sig}:{comp_trim.isoformat()}"
        status_ap = _status_item(
            chave_ap in apuracoes_existentes,
            vencimento=_ultimo_dia_mes_seguinte(ano, trimestre),
            hoje=hoje,
        )
        itens.append(
            ItemChecklist(
                tipo=f"apuracao_{tipo_sig}",
                descricao=f"Apuração {tipo_nome} — T{trimestre}/{ano}",
                status=status_ap,
                competencia=comp_trim,
            )
        )

        # DARF só faz sentido se a apuração existe
        chave_darf = f"{codigo_darf}:{comp_trim.isoformat()}"
        if chave_ap in apuracoes_existentes:
            status_darf = _status_item(
                chave_darf in darfs_existentes,
                vencimento=_ultimo_dia_mes_seguinte(ano, trimestre),
                hoje=hoje,
            )
            itens.append(
                ItemChecklist(
                    tipo=f"darf_{tipo_sig}",
                    descricao=f"DARF {tipo_nome} (código {codigo_darf}) — T{trimestre}/{ano}",
                    status=status_darf,
                    competencia=comp_trim,
                )
            )

    # ── Apurações + DARFs mensais (PIS e Cofins × 3 meses) ───────────────
    for mes in meses:
        comp_mes = date(ano, mes, 1)
        for tipo_sig, tipo_nome, codigo_darf in (
            ("pis", "PIS", "8109"),
            ("cofins", "Cofins", "2172"),
        ):
            chave_ap = f"{tipo_sig}:{comp_mes.isoformat()}"
            venc_mensal = _dia_25_mes_seguinte(comp_mes)
            status_ap = _status_item(
                chave_ap in apuracoes_existentes,
                vencimento=venc_mensal,
                hoje=hoje,
            )
            itens.append(
                ItemChecklist(
                    tipo=f"apuracao_{tipo_sig}_{mes:02d}",
                    descricao=(
                        f"Apuração {tipo_nome} — "
                        f"{_NOME_MES[mes]}/{ano}"
                    ),
                    status=status_ap,
                    competencia=comp_mes,
                )
            )

            chave_darf = f"{codigo_darf}:{comp_mes.isoformat()}"
            if chave_ap in apuracoes_existentes:
                status_darf = _status_item(
                    chave_darf in darfs_existentes,
                    vencimento=venc_mensal,
                    hoje=hoje,
                )
                itens.append(
                    ItemChecklist(
                        tipo=f"darf_{tipo_sig}_{mes:02d}",
                        descricao=(
                            f"DARF {tipo_nome} (código {codigo_darf}) — "
                            f"{_NOME_MES[mes]}/{ano}"
                        ),
                        status=status_darf,
                        competencia=comp_mes,
                    )
                )

    total = len(itens)
    concluidos = sum(1 for i in itens if i.status == "ok")
    atrasados = sum(1 for i in itens if i.status == "atrasado")
    pendentes = total - concluidos - atrasados
    pct = round(concluidos / total * 100) if total > 0 else 0

    if concluidos == total:
        status_geral = "completo"
    elif concluidos == 0 and atrasados == 0:
        status_geral = "pendente"
    else:
        status_geral = "parcial"

    return ChecklistTrimestre(
        ano=ano,
        trimestre=trimestre,
        itens=tuple(itens),
        total=total,
        concluidos=concluidos,
        pendentes=pendentes,
        atrasados=atrasados,
        percentual_conclusao=pct,
        status_geral=status_geral,
    )


# ── Helpers privados ─────────────────────────────────────────────────────────


def _validar_trimestre(trimestre: int) -> None:
    if trimestre not in (1, 2, 3, 4):
        raise ValueError(
            f"trimestre deve ser 1, 2, 3 ou 4 (recebido {trimestre})"
        )


def _status_item(feito: bool, *, vencimento: date, hoje: date) -> str:
    if feito:
        return "ok"
    if hoje > vencimento:
        return "atrasado"
    return "pendente"


def _ultimo_dia_mes_seguinte(ano: int, trimestre: int) -> date:
    """Vencimento IRPJ/CSLL: último dia do mês seguinte ao trimestre."""
    from calendar import monthrange

    mes_enc = trimestre * 3
    if mes_enc == 12:
        mes_venc, ano_venc = 1, ano + 1
    else:
        mes_venc, ano_venc = mes_enc + 1, ano
    _, ultimo = monthrange(ano_venc, mes_venc)
    return date(ano_venc, mes_venc, ultimo)


def _dia_25_mes_seguinte(competencia: date) -> date:
    """Vencimento PIS/Cofins: dia 25 do mês seguinte."""
    if competencia.month == 12:
        return date(competencia.year + 1, 1, 25)
    return date(competencia.year, competencia.month + 1, 25)
