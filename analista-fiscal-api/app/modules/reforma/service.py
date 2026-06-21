"""ReformaService — orquestra simulador + backfill (Sprint 14 PR3).

Princípios aplicados:

  * §8.7 — multi-tenant via RLS; sessão sempre vem do ``SessionDep``.
  * §8.8 — LLM não é chamado em nenhum caminho.
  * §8.9 — ``recalcular_historico_documentos`` é idempotente.
  * §8.10 — log estruturado em cada operação.
  * §8.12 — toda saída carrega ``observacao_estimativa``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.reforma.calcula_cbs_ibs import (
    AliquotaCBSIBS,
    REGIMES_EXCLUIDOS_FASE_TESTE,
)
from app.modules.reforma.integrar_documento import (
    popular_cbs_ibs_informacional,
)
from app.modules.reforma.periodo_transicao import FaseReforma, fase
from app.modules.reforma.repo import AliquotaCbsIbsRepo, ReformaRepo
from app.modules.reforma.simulador import (
    CargaTributariaAnualizada,
    ResultadoSimulacao,
    projetar_impacto,
)
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    SemApuracoesDoPeriodo,
)

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True, slots=True)
class RecalculoResultado:
    """Resultado do backfill de documentos do ano."""

    ano: int
    atualizados: int
    ignorados: int


class ReformaService:
    """Serviço da Reforma — usado pelos endpoints e pelo worker Celery."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session
        self._empresa_repo = EmpresaRepo(session)
        self._aliq_repo = AliquotaCbsIbsRepo(session)
        self._reforma_repo = ReformaRepo(session)

    # ── 1) Simulação de impacto (3 cenários) ────────────────────────────

    async def simular_impacto(
        self, empresa_id: UUID, *, ano_alvo: int = 2033
    ) -> ResultadoSimulacao:
        """Roda o simulador para a empresa usando 12m de apurações como base.

        Args:
            empresa_id: empresa-alvo (RLS já garantiu acesso).
            ano_alvo: ano-alvo da projeção CBS+IBS — default 2033 (regime
                pleno). Outros anos usam a vigência da fase respectiva.

        Raises:
            EmpresaNaoEncontrada: empresa não existe ou outro tenant.
            SemApuracoesDoPeriodo: empresa sem apurações ou receita nos 12m.
            AliquotaCbsIbsAusente: vigência não cadastrada para ano_alvo.
        """
        empresa = await self._empresa_repo.por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        hoje = datetime.now(_TZ_BR).date()
        fase_atual = fase(hoje)

        carga = await self._reforma_repo.carga_apurada_12m(empresa_id, hoje)
        if carga.vazia:
            raise SemApuracoesDoPeriodo(
                f"Empresa {empresa_id} não tem apurações nos 12m anteriores a "
                f"{hoje.isoformat()}. Sem base para simular impacto da Reforma."
            )

        # Alíquota do ano-alvo (default 2033 — regime pleno).
        competencia_alvo = date(ano_alvo, 1, 1)
        aliquota_pleno = await self._aliq_repo.vigente(
            competencia_alvo,
            regime=empresa.regime_tributario,
            cnae=empresa.cnae_principal,
        )

        resultado = projetar_impacto(
            empresa_id=empresa_id,
            periodo_base=(carga.periodo_inicio, carga.periodo_fim),
            fase_atual=fase_atual,
            receita_anualizada=carga.receita_anualizada,
            carga_atual=CargaTributariaAnualizada(
                pis=carga.pis,
                cofins=carga.cofins,
                icms=carga.icms,
                iss=carga.iss,
            ),
            aliquota_pleno=aliquota_pleno,
            icms_medio_mensal=carga.icms_medio_mensal,
        )
        log.info(
            "reforma.simulacao.gerada",
            empresa_id=str(empresa_id),
            ano_alvo=ano_alvo,
            fase_atual=fase_atual.value,
            receita_anualizada=str(carga.receita_anualizada),
            carga_atual_total=str(carga.total),
        )
        return resultado

    # ── 2) Lookup de alíquota vigente (fachada) ─────────────────────────

    async def aliquota_vigente(
        self,
        competencia: date,
        empresa_id: UUID | None = None,
    ) -> AliquotaCBSIBS:
        """Resolve a vigência mais específica para a competência + empresa."""
        regime: str | None = None
        cnae: str | None = None
        if empresa_id is not None:
            empresa = await self._empresa_repo.por_id(empresa_id)
            if empresa is None:
                raise EmpresaNaoEncontrada(
                    f"Empresa {empresa_id} não encontrada"
                )
            regime = empresa.regime_tributario
            cnae = empresa.cnae_principal
        aliquota = await self._aliq_repo.vigente(
            competencia, regime=regime, cnae=cnae
        )
        log.info(
            "reforma.aliquota.lookup",
            competencia=competencia.isoformat(),
            fase=aliquota.fase.value,
            empresa_id=str(empresa_id) if empresa_id else None,
        )
        return aliquota

    # ── 3) Backfill histórico (idempotente) ─────────────────────────────

    async def recalcular_historico_documentos(
        self,
        empresa_id: UUID,
        *,
        ano: int,
        forcar: bool = False,
    ) -> RecalculoResultado:
        """Itera documentos do ano e popula CBS/IBS informacional.

        Idempotente (§8.9): sem ``forcar``, só toca documentos com cbs/ibs
        ainda NULL. Com ``forcar=True``, reprocessa todos (uso administrativo).

        Não cobra commit — caller é responsável pelo ``session.commit()``.
        """
        empresa = await self._empresa_repo.por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        # Guard: LC 214/2025 art. 41-42 — SN/MEI não apuram CBS/IBS na fase
        # de teste 2026.  Retorna imediatamente sem consultar alíquota nem
        # iterar documentos; todos os documentos do ano são contados como
        # ignorados (não-aplicável por lei).
        if ano == 2026 and empresa.regime_tributario in REGIMES_EXCLUIDOS_FASE_TESTE:
            log.info(
                "reforma.documento.backfill.sn_excluido_2026",
                empresa_id=str(empresa_id),
                ano=ano,
                regime=empresa.regime_tributario,
            )
            return RecalculoResultado(ano=ano, atualizados=0, ignorados=0)

        # Resolve alíquota uma vez para o ano (otimização — assume vigência
        # estável dentro do ano civil). Se houver mudança de vigência mid-year,
        # uma execução por mês seria mais correta — mas o seed atual tem
        # vigências anuais (2026, 2027, 2033).
        aliquotas = await self._aliq_repo.vigente(
            date(ano, 1, 1),
            regime=empresa.regime_tributario,
            cnae=empresa.cnae_principal,
        )

        docs = await self._reforma_repo.documentos_do_ano_sem_cbs(
            empresa_id, ano=ano, forcar=forcar
        )

        atualizados = 0
        ignorados = 0
        for doc in docs:
            resultado = popular_cbs_ibs_informacional(
                doc,
                aliquotas,
                regime_tributario=empresa.regime_tributario,
            )
            if not resultado.calculou:
                ignorados += 1
                continue
            await self._reforma_repo.atualizar_cbs_ibs_documento(
                doc.id,
                valor_cbs=resultado.valor_cbs,
                valor_ibs=resultado.valor_ibs,
            )
            atualizados += 1

        log.info(
            "reforma.documento.backfill",
            empresa_id=str(empresa_id),
            ano=ano,
            forcar=forcar,
            atualizados=atualizados,
            ignorados=ignorados,
        )
        return RecalculoResultado(
            ano=ano, atualizados=atualizados, ignorados=ignorados
        )

    # ── 4) Fase atual (helper para o router) ─────────────────────────────

    def fase_atual(self, competencia: date) -> FaseReforma:
        """Fachada para ``periodo_transicao.fase`` — exposto via endpoint."""
        return fase(competencia)
