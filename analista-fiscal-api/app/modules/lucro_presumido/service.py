"""Service do Lucro Presumido (Sprint 11 PR1 + Sprint 20 PR1 + PR2).

Apura IRPJ/CSLL trimestrais e PIS/Cofins mensais, resolve presunção por
CNAE da empresa e persiste em ``apuracao_fiscal`` (tabela central — §8.2,
§8.9 garante idempotência via UNIQUE composto).

Sprint 20 PR1 adiciona geração de DARF para os 4 tributos LP.

§8.1 RLS via ``get_session``.
§8.2 Apuração + guia persistidas são fatos imutáveis.
§8.3 Snapshot da presunção vigente vai pro ``output_jsonb`` (SCD-friendly).
§8.10 Log estruturado por apuração.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.types import JsonObject

from app.modules.empresa.repo import EmpresaRepo
from app.modules.lucro_presumido.calcula_csll import (
    ResultadoCsllLp,
    calcular_csll_trimestral,
)
from app.modules.lucro_presumido.calcula_checklist_lp import (
    ChecklistTrimestre,
    calcular_checklist_trimestre,
)
from app.modules.lucro_presumido.calcula_darf_lp import (
    calcular_darf_cofins,
    calcular_darf_csll,
    calcular_darf_irpj,
    calcular_darf_pis,
)
from app.modules.lucro_presumido.calcula_irpj import (
    ResultadoIrpjLp,
    calcular_irpj_trimestral,
)
from app.modules.lucro_presumido.calcula_pis_cofins import (
    ResultadoTributoCumulativo,
    calcular_cofins_cumulativo_mensal,
    calcular_pis_cumulativo_mensal,
)
from app.modules.lucro_presumido.repo import (
    ApuracaoLpRepo,
    GuiaPagamentoRepo,
    PresuncaoLpRepo,
    PresuncaoResolvida,
)
from app.modules.lucro_presumido.schemas import (
    ApurarIrpjCsllTrimestralIn,
    ApurarPisCofinsMensalIn,
)
from app.shared.db.models import ApuracaoFiscal, Empresa, GuiaPagamento
from app.shared.exceptions import (
    ApuracaoLPJaExiste,
    ApuracaoLpNaoEncontrada,
    ChecklistLpNaoConcluido,
    EmpresaForaDoRegimeLP,
    EmpresaNaoEncontrada,
    PresuncaoNaoEncontrada,
)

log = structlog.get_logger(__name__)

_REGIME_LP = "lucro_presumido"


class LucroPresumidoService:
    # ── IRPJ / CSLL trimestrais ─────────────────────────────────────────

    async def apurar_irpj_trimestral(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApurarIrpjCsllTrimestralIn,
    ) -> ApuracaoFiscal:
        empresa = await _empresa_lp(session, empresa_id)
        competencia = _data_trimestre(payload.ano, payload.trimestre)
        presuncao = await _resolver_presuncao(session, competencia, empresa)

        if await ApuracaoLpRepo(session).buscar(empresa_id, competencia, "irpj"):
            raise ApuracaoLPJaExiste(
                f"IRPJ {payload.ano}-T{payload.trimestre} já apurado"
            )

        resultado = calcular_irpj_trimestral(
            receita_bruta_trimestre=payload.receita_bruta_trimestre,
            percentual_presuncao=presuncao.percentual_irpj,
            ganhos_capital=payload.ganhos_capital,
            receitas_aplicacoes=payload.receitas_aplicacoes,
            outras_adicoes=payload.outras_adicoes,
            meses_periodo=payload.meses_periodo,
            irrf_a_compensar=payload.irrf_a_compensar,
        )
        apuracao = ApuracaoFiscal(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            competencia=competencia,
            tipo="irpj",
            regime=_REGIME_LP,
            input_jsonb=_stringify(payload.model_dump()),
            output_jsonb=_stringify(asdict(resultado)),
            faixas_usadas=_stringify(_presuncao_snapshot(presuncao)),
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await _commit_apuracao(session, apuracao)
        _log_apuracao(empresa_id, "irpj", competencia, resultado)
        return apuracao

    async def apurar_csll_trimestral(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApurarIrpjCsllTrimestralIn,
    ) -> ApuracaoFiscal:
        empresa = await _empresa_lp(session, empresa_id)
        competencia = _data_trimestre(payload.ano, payload.trimestre)
        presuncao = await _resolver_presuncao(session, competencia, empresa)

        if await ApuracaoLpRepo(session).buscar(empresa_id, competencia, "csll"):
            raise ApuracaoLPJaExiste(
                f"CSLL {payload.ano}-T{payload.trimestre} já apurada"
            )

        resultado = calcular_csll_trimestral(
            receita_bruta_trimestre=payload.receita_bruta_trimestre,
            percentual_presuncao=presuncao.percentual_csll,
            ganhos_capital=payload.ganhos_capital,
            receitas_aplicacoes=payload.receitas_aplicacoes,
            outras_adicoes=payload.outras_adicoes,
        )
        apuracao = ApuracaoFiscal(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            competencia=competencia,
            tipo="csll",
            regime=_REGIME_LP,
            input_jsonb=_stringify(payload.model_dump()),
            output_jsonb=_stringify(asdict(resultado)),
            faixas_usadas=_stringify(_presuncao_snapshot(presuncao)),
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await _commit_apuracao(session, apuracao)
        _log_apuracao(empresa_id, "csll", competencia, resultado)
        return apuracao

    # ── PIS / Cofins mensais ────────────────────────────────────────────

    async def apurar_pis_mensal(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApurarPisCofinsMensalIn,
    ) -> ApuracaoFiscal:
        return await self._apurar_cumulativo(
            session, tenant_id, empresa_id, payload, tipo="pis",
        )

    async def apurar_cofins_mensal(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApurarPisCofinsMensalIn,
    ) -> ApuracaoFiscal:
        return await self._apurar_cumulativo(
            session, tenant_id, empresa_id, payload, tipo="cofins",
        )

    async def _apurar_cumulativo(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApurarPisCofinsMensalIn,
        *,
        tipo: str,
    ) -> ApuracaoFiscal:
        await _empresa_lp(session, empresa_id)
        competencia = date(payload.competencia.year, payload.competencia.month, 1)

        if await ApuracaoLpRepo(session).buscar(empresa_id, competencia, tipo):
            raise ApuracaoLPJaExiste(
                f"{tipo.upper()} de {competencia.isoformat()} já apurado"
            )

        fn = (
            calcular_pis_cumulativo_mensal
            if tipo == "pis"
            else calcular_cofins_cumulativo_mensal
        )
        resultado = fn(
            payload.receita_bruta_mes, exclusoes=payload.exclusoes
        )
        apuracao = ApuracaoFiscal(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            competencia=competencia,
            tipo=tipo,
            regime=_REGIME_LP,
            input_jsonb=_stringify(payload.model_dump()),
            output_jsonb=_stringify(asdict(resultado)),
            faixas_usadas={"observacao": "regime cumulativo (Lei 9.718/1998)"},
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await _commit_apuracao(session, apuracao)
        _log_apuracao(empresa_id, tipo, competencia, resultado)
        return apuracao

    # ── Helper de diagnóstico (debug do match de CNAE) ──────────────────

    async def resolver_presuncao(
        self, session: AsyncSession, empresa_id: UUID, em: date
    ) -> PresuncaoResolvida:
        empresa = await _empresa_lp(session, empresa_id)
        return await _resolver_presuncao(session, em, empresa)

    # ── DARF — Sprint 20 PR1 ─────────────────────────────────────────────

    async def gerar_darf_irpj(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        ano: int,
        trimestre: int,
    ) -> GuiaPagamento:
        """Gera DARF IRPJ (código 2089) a partir da apuração trimestral.

        Levanta ``ApuracaoLpNaoEncontrada`` se a apuração ainda não foi feita.
        Levanta ``DarfLpJaGerada`` se já existe guia para o período.
        """
        await _empresa_lp(session, empresa_id)
        competencia = _data_trimestre(ano, trimestre)
        apuracao = await ApuracaoLpRepo(session).buscar(
            empresa_id, competencia, "irpj"
        )
        if apuracao is None:
            raise ApuracaoLpNaoEncontrada(
                f"Apuração IRPJ {ano}-T{trimestre} não encontrada — "
                f"execute POST /v1/empresas/{empresa_id}/lp/irpj primeiro."
            )
        valor_devido = Decimal(str(apuracao.output_jsonb.get("irpj_devido", "0")))
        resultado = calcular_darf_irpj(valor_devido, ano, trimestre)
        guia = _montar_guia(resultado, tenant_id, empresa_id, apuracao.id, "darf")
        return await GuiaPagamentoRepo(session).criar(guia)

    async def gerar_darf_csll(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        ano: int,
        trimestre: int,
    ) -> GuiaPagamento:
        """Gera DARF CSLL (código 2372) a partir da apuração trimestral."""
        await _empresa_lp(session, empresa_id)
        competencia = _data_trimestre(ano, trimestre)
        apuracao = await ApuracaoLpRepo(session).buscar(
            empresa_id, competencia, "csll"
        )
        if apuracao is None:
            raise ApuracaoLpNaoEncontrada(
                f"Apuração CSLL {ano}-T{trimestre} não encontrada — "
                f"execute POST /v1/empresas/{empresa_id}/lp/csll primeiro."
            )
        valor_devido = Decimal(str(apuracao.output_jsonb.get("csll", "0")))
        resultado = calcular_darf_csll(valor_devido, ano, trimestre)
        guia = _montar_guia(resultado, tenant_id, empresa_id, apuracao.id, "darf")
        return await GuiaPagamentoRepo(session).criar(guia)

    async def gerar_darf_pis(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        competencia: date,
    ) -> GuiaPagamento:
        """Gera DARF PIS (código 8109) a partir da apuração mensal."""
        await _empresa_lp(session, empresa_id)
        apuracao = await ApuracaoLpRepo(session).buscar(
            empresa_id, competencia, "pis"
        )
        if apuracao is None:
            raise ApuracaoLpNaoEncontrada(
                f"Apuração PIS {competencia.isoformat()} não encontrada — "
                f"execute POST /v1/empresas/{empresa_id}/lp/pis primeiro."
            )
        valor_devido = Decimal(str(apuracao.output_jsonb.get("tributo", "0")))
        resultado = calcular_darf_pis(valor_devido, competencia)
        guia = _montar_guia(resultado, tenant_id, empresa_id, apuracao.id, "darf")
        return await GuiaPagamentoRepo(session).criar(guia)

    async def gerar_darf_cofins(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        competencia: date,
    ) -> GuiaPagamento:
        """Gera DARF Cofins (código 2172) a partir da apuração mensal."""
        await _empresa_lp(session, empresa_id)
        apuracao = await ApuracaoLpRepo(session).buscar(
            empresa_id, competencia, "cofins"
        )
        if apuracao is None:
            raise ApuracaoLpNaoEncontrada(
                f"Apuração Cofins {competencia.isoformat()} não encontrada — "
                f"execute POST /v1/empresas/{empresa_id}/lp/cofins primeiro."
            )
        valor_devido = Decimal(str(apuracao.output_jsonb.get("tributo", "0")))
        resultado = calcular_darf_cofins(valor_devido, competencia)
        guia = _montar_guia(resultado, tenant_id, empresa_id, apuracao.id, "darf")
        return await GuiaPagamentoRepo(session).criar(guia)

    async def listar_guias(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        *,
        status: str | None = None,
        limite: int = 50,
    ) -> list[GuiaPagamento]:
        return await GuiaPagamentoRepo(session).listar(
            empresa_id, status=status, limite=limite
        )

    async def marcar_pago(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        guia_id: UUID,
        pago_em: date,
    ) -> GuiaPagamento:
        guia = await GuiaPagamentoRepo(session).por_id(guia_id)
        if guia is None or guia.empresa_id != empresa_id:
            from app.shared.exceptions import GuiaPagamentoNaoEncontrada
            raise GuiaPagamentoNaoEncontrada(
                f"Guia {guia_id} não encontrada para a empresa {empresa_id}"
            )
        return await GuiaPagamentoRepo(session).marcar_pago(guia_id, pago_em)


# ── Checklist LP — Sprint 20 PR2 ─────────────────────────────────────────────


class LpChecklistService:
    """Checklist de obrigações LP por trimestre + health score da empresa."""

    async def checklist_trimestre(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        ano: int,
        trimestre: int,
        *,
        data_referencia: date | None = None,
    ) -> ChecklistTrimestre:
        await _empresa_lp(session, empresa_id)
        apuracoes = await ApuracaoLpRepo(session).listar_trimestre(
            empresa_id, ano, trimestre
        )
        guias = await GuiaPagamentoRepo(session).listar_trimestre(
            empresa_id, ano, trimestre
        )
        apuracoes_set = frozenset(
            f"{a.tipo}:{a.competencia.isoformat()}" for a in apuracoes
        )
        darfs_set = frozenset(
            f"{g.codigo_receita}:{g.competencia.isoformat()}" for g in guias
        )
        return calcular_checklist_trimestre(
            ano,
            trimestre,
            apuracoes_existentes=apuracoes_set,
            darfs_existentes=darfs_set,
            data_referencia=data_referencia,
        )

    async def fechar_trimestre(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        ano: int,
        trimestre: int,
    ) -> ChecklistTrimestre:
        """Valida que todas as obrigações do trimestre estão concluídas.

        Levanta ``ChecklistLpNaoConcluido`` se ainda há pendentes ou atrasados.
        Retorna o checklist completo para confirmação ao cliente.
        """
        checklist = await self.checklist_trimestre(
            session, empresa_id, ano, trimestre
        )
        if not checklist.completo:
            raise ChecklistLpNaoConcluido(
                f"T{trimestre}/{ano} não está completo: "
                f"{checklist.pendentes} pendente(s), "
                f"{checklist.atrasados} atrasado(s)."
            )
        return checklist

    async def saude_lp(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        *,
        trimestres: int = 4,
        data_referencia: date | None = None,
    ) -> list[ChecklistTrimestre]:
        """Retorna checklist dos últimos ``trimestres`` trimestres encerrados."""
        hoje = data_referencia or date.today()
        # Trimestre corrente (ainda em curso), depois retrocede
        trim_atual = (hoje.month - 1) // 3 + 1
        resultados: list[ChecklistTrimestre] = []
        ano = hoje.year
        trim = trim_atual
        for _ in range(trimestres):
            trim -= 1
            if trim == 0:
                trim = 4
                ano -= 1
            c = await self.checklist_trimestre(
                session, empresa_id, ano, trim,
                data_referencia=data_referencia,
            )
            resultados.append(c)
        resultados.reverse()  # cronológico
        return resultados


# ── Helpers privados ─────────────────────────────────────────────────────


def _data_trimestre(ano: int, trimestre: int) -> date:
    """Primeiro dia do trimestre (1/1, 1/4, 1/7, 1/10) — competência canônica."""
    mes_inicial = {1: 1, 2: 4, 3: 7, 4: 10}[trimestre]
    return date(ano, mes_inicial, 1)


async def _empresa_lp(session: AsyncSession, empresa_id: UUID) -> Empresa:
    empresa = await EmpresaRepo(session).por_id(empresa_id)
    if empresa is None:
        raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
    if empresa.regime_tributario != _REGIME_LP:
        raise EmpresaForaDoRegimeLP(
            f"Empresa está em regime {empresa.regime_tributario!r}, não em "
            f"lucro_presumido — apuração indevida"
        )
    return empresa


async def _resolver_presuncao(
    session: AsyncSession, em: date, empresa: Empresa
) -> PresuncaoResolvida:
    # Fase 2 PR3: RBT12 vem de rbt12_mensal (view materializada) com fallback
    # para empresa.faturamento_12m declarado.
    rbt12_da_view = await EmpresaRepo(session).rbt12_da_view(empresa.id, em)
    faturamento = (
        rbt12_da_view if rbt12_da_view is not None else empresa.faturamento_12m
    )
    resolvida = await PresuncaoLpRepo(session).resolver_por_cnae(
        em, empresa.cnae_principal, faturamento_12m=faturamento,
    )
    if resolvida is None:
        raise PresuncaoNaoEncontrada(
            f"Sem grupo de presunção LP para CNAE {empresa.cnae_principal!r} "
            f"em {em.isoformat()}"
        )
    return resolvida


def _presuncao_snapshot(p: PresuncaoResolvida) -> JsonObject:
    return {
        "grupo_atividade": p.grupo_atividade,
        "percentual_irpj": str(p.percentual_irpj),
        "percentual_csll": str(p.percentual_csll),
        "cnae_pattern": p.cnae_pattern,
        "prioridade": p.prioridade,
        "fonte": p.fonte,
    }


async def _commit_apuracao(
    session: AsyncSession, apuracao: ApuracaoFiscal
) -> None:
    try:
        await ApuracaoLpRepo(session).criar(apuracao)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApuracaoLPJaExiste(
            f"Apuração ({apuracao.tipo}, {apuracao.competencia}) já existe"
        ) from exc


def _log_apuracao(
    empresa_id: UUID, tipo: str, competencia: date, resultado: object
) -> None:
    log.info(
        f"lp.{tipo}.apurado",
        empresa_id=str(empresa_id),
        competencia=competencia.isoformat(),
        algoritmo_versao=getattr(resultado, "algoritmo_versao", None),
    )


def _stringify(o: Any) -> Any:  # noqa: ANN401 — helper recursivo dinâmico
    """Converte Decimals e datas em strings JSON-safe."""
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: _stringify(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_stringify(x) for x in o]
    return o


def _montar_guia(
    resultado: object,
    tenant_id: UUID,
    empresa_id: UUID,
    apuracao_id: UUID,
    tipo: str,
) -> GuiaPagamento:
    """Converte ResultadoDarfLp em GuiaPagamento ORM."""
    from app.modules.lucro_presumido.calcula_darf_lp import ResultadoDarfLp

    assert isinstance(resultado, ResultadoDarfLp)
    return GuiaPagamento(
        tenant_id=tenant_id,
        empresa_id=empresa_id,
        apuracao_id=apuracao_id,
        tipo=tipo,
        codigo_receita=resultado.codigo_receita,
        denominacao=resultado.denominacao,
        competencia=resultado.competencia,
        periodo_apuracao=resultado.periodo_apuracao,
        valor_principal=resultado.valor_principal,
        juros=resultado.juros,
        multa=resultado.multa,
        total=resultado.total,
        data_vencimento=resultado.data_vencimento,
        status="a_pagar",
        algoritmo_versao=resultado.algoritmo_versao,
        fundamento_legal=resultado.fundamento_legal,
    )
