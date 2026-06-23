"""Schemas Pydantic — Lucro Presumido (Sprint 11 PR1 + Sprint 20 PR1)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApurarIrpjCsllTrimestralIn(BaseModel):
    """Input para apurar IRPJ ou CSLL de um trimestre completo."""

    model_config = ConfigDict(extra="forbid")

    ano: Annotated[int, Field(ge=2000, le=2100)]
    trimestre: Annotated[int, Field(ge=1, le=4)]
    receita_bruta_trimestre: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    ganhos_capital: Annotated[Decimal, Field(ge=0, decimal_places=2, default=Decimal("0"))]
    receitas_aplicacoes: Annotated[
        Decimal, Field(ge=0, decimal_places=2, default=Decimal("0"))
    ]
    outras_adicoes: Annotated[
        Decimal, Field(ge=0, decimal_places=2, default=Decimal("0"))
    ]
    meses_periodo: Annotated[int, Field(ge=1, le=3, default=3)]
    irrf_a_compensar: Annotated[
        Decimal,
        Field(
            ge=0,
            decimal_places=2,
            default=Decimal("0"),
            description=(
                "IRRF retido na fonte (Lei 9.430 art. 64) deduzido do IRPJ devido. "
                "Aplica-se apenas à apuração de IRPJ — ignorado para CSLL. "
                "Inclui saldo credor de IRRF acumulado de trimestres anteriores."
            ),
        ),
    ]
    csll_a_compensar: Annotated[
        Decimal,
        Field(
            ge=0,
            decimal_places=2,
            default=Decimal("0"),
            description=(
                "CSLL retida na fonte (Lei 9.430 art. 64 c/c Lei 10.833/2003 art. 30 "
                "— retenção PCC 1% de CSLL em serviços PJ→PJ) deduzida da CSLL devida. "
                "Aplica-se apenas à apuração de CSLL — ignorado para IRPJ. "
                "Inclui saldo credor de CSLL acumulado de trimestres anteriores."
            ),
        ),
    ]


class ApurarPisCofinsMensalIn(BaseModel):
    """Input para apurar PIS ou Cofins de um mês."""

    model_config = ConfigDict(extra="forbid")

    competencia: date
    receita_bruta_mes: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    exclusoes: Annotated[
        Decimal, Field(ge=0, decimal_places=2, default=Decimal("0"))
    ]


class ApuracaoLpOut(BaseModel):
    """Resultado persistido — reusa ``apuracao_fiscal``."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    competencia: date
    tipo: str
    regime: str
    valor_total: Decimal
    algoritmo_versao: str
    output_jsonb: dict[str, object]
    criado_em: datetime
    status: str

    @classmethod
    def from_apuracao(cls, apuracao: object) -> ApuracaoLpOut:
        from app.shared.db.models import ApuracaoFiscal

        assert isinstance(apuracao, ApuracaoFiscal)
        valor_total = _extrair_valor_total(apuracao.tipo, apuracao.output_jsonb)
        return cls(
            id=apuracao.id,
            empresa_id=apuracao.empresa_id,
            competencia=apuracao.competencia,
            tipo=apuracao.tipo,
            regime=apuracao.regime,
            valor_total=valor_total,
            algoritmo_versao=apuracao.algoritmo_versao,
            output_jsonb=apuracao.output_jsonb,
            criado_em=apuracao.created_at,
            status=apuracao.status,
        )


def _extrair_valor_total(tipo: str, output: dict[str, object]) -> Decimal:
    """Mapeia o campo principal de cada tipo para `valor_total` no Out.

    Para IRPJ usa ``irpj_devido`` (valor a recolher após IRRF compensado).
    Fallback para ``irpj_total`` mantém compatibilidade com apurações antigas
    geradas pela v1 do algoritmo (sem campo irpj_devido).
    """
    if tipo == "irpj":
        valor = output.get("irpj_devido")
        if valor is None:
            valor = output.get("irpj_total", "0")
        return Decimal(str(valor))
    if tipo == "csll":
        # FA3/M3: usa csll_a_recolher (após compensação); fallback para "csll"
        # mantém compat com apurações antigas geradas pela v1 do algoritmo.
        valor = output.get("csll_a_recolher")
        if valor is None:
            valor = output.get("csll", "0")
        return Decimal(str(valor))
    if tipo in ("pis", "cofins"):
        return Decimal(str(output.get("tributo", "0")))
    return Decimal("0")


class PresuncaoResolvidaOut(BaseModel):
    """Helper diagnóstico: qual grupo o sistema escolheu para o CNAE."""

    grupo_atividade: str
    percentual_irpj: Decimal
    percentual_csll: Decimal
    cnae_pattern: str | None
    prioridade: int
    fonte: str


# ── Sprint 20 PR1 — DARF LP ───────────────────────────────────────────────────


class GuiaPagamentoOut(BaseModel):
    """Guia de pagamento LP gerada a partir de apuração fiscal."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    empresa_id: UUID
    apuracao_id: UUID | None
    tipo: str
    codigo_receita: str
    denominacao: str
    periodo_apuracao: str
    competencia: date
    valor_principal: Decimal
    juros: Decimal
    multa: Decimal
    total: Decimal
    data_vencimento: date
    status: str
    pago_em: date | None
    algoritmo_versao: str
    fundamento_legal: str

    @classmethod
    def from_guia(cls, guia: object) -> GuiaPagamentoOut:
        from app.shared.db.models import GuiaPagamento

        assert isinstance(guia, GuiaPagamento)
        return cls(
            id=guia.id,
            empresa_id=guia.empresa_id,
            apuracao_id=guia.apuracao_id,
            tipo=guia.tipo,
            codigo_receita=guia.codigo_receita,
            denominacao=guia.denominacao,
            periodo_apuracao=guia.periodo_apuracao,
            competencia=guia.competencia,
            valor_principal=guia.valor_principal,
            juros=guia.juros,
            multa=guia.multa,
            total=guia.total,
            data_vencimento=guia.data_vencimento,
            status=guia.status,
            pago_em=guia.pago_em,
            algoritmo_versao=guia.algoritmo_versao,
            fundamento_legal=guia.fundamento_legal,
        )


class MarcarPagoIn(BaseModel):
    """Input para marcar guia como paga."""

    model_config = ConfigDict(extra="forbid")

    pago_em: date


# ── Sprint 20 PR2 — Checklist LP ──────────────────────────────────────────────


class ItemChecklistOut(BaseModel):
    """Um item do checklist de obrigações LP."""

    tipo: str
    descricao: str
    status: str   # 'ok' | 'pendente' | 'atrasado'
    competencia: date


class ChecklistTrimestreOut(BaseModel):
    """Checklist completo de obrigações LP de um trimestre."""

    ano: int
    trimestre: int
    itens: list[ItemChecklistOut]
    total: int
    concluidos: int
    pendentes: int
    atrasados: int
    percentual_conclusao: int
    status_geral: str   # 'completo' | 'parcial' | 'pendente'
    algoritmo_versao: str
    completo: bool

    @classmethod
    def from_checklist(cls, c: object) -> ChecklistTrimestreOut:
        from app.modules.lucro_presumido.calcula_checklist_lp import ChecklistTrimestre

        assert isinstance(c, ChecklistTrimestre)
        return cls(
            ano=c.ano,
            trimestre=c.trimestre,
            itens=[
                ItemChecklistOut(
                    tipo=i.tipo,
                    descricao=i.descricao,
                    status=i.status,
                    competencia=i.competencia,
                )
                for i in c.itens
            ],
            total=c.total,
            concluidos=c.concluidos,
            pendentes=c.pendentes,
            atrasados=c.atrasados,
            percentual_conclusao=c.percentual_conclusao,
            status_geral=c.status_geral,
            algoritmo_versao=c.algoritmo_versao,
            completo=c.completo,
        )


class SaudeLpOut(BaseModel):
    """Health score LP da empresa nos últimos N trimestres."""

    empresa_id: UUID
    trimestres_analisados: int
    trimestres_completos: int
    total_itens: int
    concluidos: int
    pendentes: int
    atrasados: int
    score: int   # 0-100 (% de itens concluídos no período)
    status: str  # 'saudavel' | 'atencao' | 'critico'
    checklist_por_trimestre: list[ChecklistTrimestreOut]

    @classmethod
    def from_checklists(
        cls, empresa_id: UUID, checklists: Sequence[ChecklistTrimestreOut]
    ) -> SaudeLpOut:
        total = sum(c.total for c in checklists)
        concluidos = sum(c.concluidos for c in checklists)
        pendentes = sum(c.pendentes for c in checklists)
        atrasados = sum(c.atrasados for c in checklists)
        trimestres_completos = sum(1 for c in checklists if c.completo)
        score = round(concluidos / total * 100) if total > 0 else 0
        if score >= 90:
            status = "saudavel"
        elif score >= 60:
            status = "atencao"
        else:
            status = "critico"
        return cls(
            empresa_id=empresa_id,
            trimestres_analisados=len(list(checklists)),
            trimestres_completos=trimestres_completos,
            total_itens=total,
            concluidos=concluidos,
            pendentes=pendentes,
            atrasados=atrasados,
            score=score,
            status=status,
            checklist_por_trimestre=list(checklists),
        )
