"""Service de imobilizado (Sprint 8 PR1)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.imobilizado.calcula_depreciacao import (
    ALGORITMO_VERSAO,
    BemView,
    calcular_parcela_mensal,
)
from app.modules.imobilizado.repo import (
    BemImobilizadoRepo,
    DepreciacaoRepo,
    TabelaDepreciacaoRepo,
)
from app.modules.imobilizado.schemas import (
    BaixarBemIn,
    BemImobilizadoOut,
    CadastrarBemIn,
    CategoriaBem,
    GerarDepreciacaoOut,
    MetodoDepreciacao,
)
from app.shared.db.models import BemImobilizado
from app.shared.exceptions import (
    BemJaBaixado,
    BemNaoEncontrado,
    EmpresaNaoEncontrada,
    LancamentoInvalido,
    TabelaTributariaAusente,
)

log = structlog.get_logger(__name__)


class ImobilizadoService:
    # ── cadastro ─────────────────────────────────────────────────────────────

    async def cadastrar(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        payload: CadastrarBemIn,
    ) -> BemImobilizadoOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        taxa, vida_util = await self._resolver_taxa_vida_util(
            session,
            payload.categoria,
            payload.data_aquisicao,
            taxa_informada=payload.taxa_depreciacao_anual,
            vida_util_informada=payload.vida_util_meses,
        )

        repo = BemImobilizadoRepo(session)
        bem = await repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            descricao=payload.descricao,
            categoria=payload.categoria.value,
            data_aquisicao=payload.data_aquisicao,
            valor_aquisicao=payload.valor_aquisicao,
            taxa_depreciacao_anual=taxa,
            vida_util_meses=vida_util,
            valor_residual=payload.valor_residual,
            metodo_depreciacao=payload.metodo_depreciacao.value,
            documento_fiscal_id=payload.documento_fiscal_id,
            conta_contabil_id=payload.conta_contabil_id,
        )
        await session.commit()

        log.info(
            "imobilizado.cadastrou",
            empresa_id=str(empresa_id),
            bem_id=str(bem.id),
            categoria=bem.categoria,
            valor=str(bem.valor_aquisicao),
            taxa_anual=str(bem.taxa_depreciacao_anual),
            vida_util_meses=bem.vida_util_meses,
        )
        return _para_out(bem)

    # Tolerância para comparação taxa ≈ 12 / vida_util_meses.
    # IN SRF 162/1998: taxa anual e vida útil são a mesma grandeza;
    # admitimos ±0.5 p.p. de folga para arredondamentos do cliente
    # (ex.: taxa 0.1667 ≈ 12/72 = 0.1666̄).
    _TOLERANCIA_COERENCIA = Decimal("0.005")

    async def _resolver_taxa_vida_util(
        self,
        session: AsyncSession,
        categoria: CategoriaBem,
        em: date,
        *,
        taxa_informada: Decimal | None,
        vida_util_informada: int | None,
    ) -> tuple[Decimal, int]:
        """Resolve taxa e vida útil garantindo coerência com IN SRF 162/1998.

        Regra: ``taxa_anual = 12 / vida_util_meses`` (com tolerância ±0.5 p.p.).

        Casos:
          * Ambos informados → valida coerência; rejeita se divergirem.
            A vida útil é a grandeza primária: ``taxa_anual = 12 / vida_meses``.
          * Só taxa → deriva vida útil: ``vida = round(12 / taxa)``; mínimo 1 mês.
          * Só vida → deriva taxa: ``taxa = 12 / vida``; quantizada em 4 casas.
          * Nenhum → busca na ``TabelaDepreciacaoRfb`` pela categoria.
        """
        if taxa_informada is not None and vida_util_informada is not None:
            # Ambos fornecidos: verificar coerência.
            # taxa esperada a partir da vida útil informada.
            taxa_esperada = Decimal(12) / Decimal(vida_util_informada)
            diferenca = abs(taxa_informada - taxa_esperada)
            if diferenca > self._TOLERANCIA_COERENCIA:
                raise LancamentoInvalido(
                    f"Coerência IN SRF 162/1998 violada: taxa_depreciacao_anual={taxa_informada} "
                    f"e vida_util_meses={vida_util_informada} são incompatíveis. "
                    f"Para vida de {vida_util_informada} meses a taxa esperada é "
                    f"{taxa_esperada.quantize(Decimal('0.0001'))} "
                    f"(tolerância ±{self._TOLERANCIA_COERENCIA}). "
                    f"Informe apenas um deles para que o sistema derive o outro."
                )
            # Coerentes: a vida útil é a grandeza primária; deriva taxa de forma
            # consistente para que ficha e cálculo jamais divirjam.
            taxa_derivada = (Decimal(12) / Decimal(vida_util_informada)).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_EVEN
            )
            log.info(
                "imobilizado.taxa_vida_derivada_de_vida",
                taxa_informada=str(taxa_informada),
                taxa_derivada=str(taxa_derivada),
                vida_util_meses=vida_util_informada,
            )
            return taxa_derivada, vida_util_informada

        if taxa_informada is not None and vida_util_informada is None:
            # Só taxa: deriva vida = round(12 / taxa); garante >= 1 mês.
            vida_derivada = max(1, round(Decimal(12) / taxa_informada))
            return taxa_informada, vida_derivada

        if taxa_informada is None and vida_util_informada is not None:
            # Só vida: deriva taxa.
            taxa_derivada = (Decimal(12) / Decimal(vida_util_informada)).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_EVEN
            )
            return taxa_derivada, vida_util_informada

        # Nenhum informado: busca na tabela RFB.
        tabela = await TabelaDepreciacaoRepo(session).taxa_vigente(
            categoria.value, em
        )
        if tabela is None:
            raise TabelaTributariaAusente(
                f"Tabela de depreciação RFB não encontrada para categoria "
                f"'{categoria.value}' em {em.isoformat()}"
            )

        return tabela.taxa_anual, tabela.vida_util_anos * 12

    # ── baixa ────────────────────────────────────────────────────────────────

    async def baixar(
        self,
        session: AsyncSession,
        empresa_id: uuid.UUID,
        bem_id: uuid.UUID,
        payload: BaixarBemIn,
    ) -> BemImobilizadoOut:
        repo = BemImobilizadoRepo(session)
        bem = await repo.por_id(bem_id)
        if bem is None or bem.empresa_id != empresa_id:
            raise BemNaoEncontrado(f"Bem {bem_id} não encontrado")
        if bem.data_baixa is not None:
            raise BemJaBaixado(f"Bem {bem_id} já foi baixado em {bem.data_baixa}")
        if payload.data_baixa < bem.data_aquisicao:
            raise BemJaBaixado(
                "Data de baixa não pode ser anterior à data de aquisição"
            )

        await repo.baixar(
            bem, data_baixa=payload.data_baixa, motivo=payload.motivo_baixa
        )
        await session.commit()
        log.info(
            "imobilizado.baixou",
            bem_id=str(bem_id),
            data_baixa=payload.data_baixa.isoformat(),
        )
        return _para_out(bem)

    # ── depreciação mensal ──────────────────────────────────────────────────

    async def gerar_depreciacao_mensal(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        competencia: date,
    ) -> GerarDepreciacaoOut:
        """Roda o algoritmo para todos os bens depreciáveis da empresa.

        Idempotente: linhas já existentes em ``depreciacao_mensal`` para a
        (bem, competência) são puladas via verificação prévia.
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        competencia_mes1 = date(competencia.year, competencia.month, 1)

        bens = await BemImobilizadoRepo(session).listar_ativos_depreciaveis(empresa_id)
        depr_repo = DepreciacaoRepo(session)

        bens_processados = 0
        bens_depreciados = 0
        bens_totais_finalizados = 0
        total_depreciado = Decimal("0.00")

        for bem in bens:
            bens_processados += 1
            if await depr_repo.existe(bem.id, competencia_mes1):
                continue

            acumulado_anterior = await depr_repo.buscar_acumulado_ate(
                bem.id, exclusive_competencia=competencia_mes1
            )
            view = BemView(
                valor_aquisicao=bem.valor_aquisicao,
                valor_residual=bem.valor_residual,
                vida_util_meses=bem.vida_util_meses,
                data_aquisicao=bem.data_aquisicao,
                data_baixa=bem.data_baixa,
                ativo=bem.ativo,
            )
            resultado = calcular_parcela_mensal(
                view,
                competencia_mes1,
                valor_acumulado_anterior=acumulado_anterior,
            )

            # Mesmo valor_depreciado=0 vira linha — registra que o algoritmo
            # rodou e por que não depreciou (saldo_contabil mantém estado).
            await depr_repo.criar(
                tenant_id=tenant_id,
                bem_id=bem.id,
                competencia=competencia_mes1,
                valor_depreciado=resultado.valor_depreciado,
                valor_acumulado=resultado.valor_acumulado,
                saldo_contabil=resultado.saldo_contabil,
            )
            if resultado.valor_depreciado > Decimal("0"):
                bens_depreciados += 1
                total_depreciado += resultado.valor_depreciado
            if resultado.eh_ultima_parcela:
                bens_totais_finalizados += 1

        await session.commit()

        log.info(
            "imobilizado.depreciacao.lote",
            empresa_id=str(empresa_id),
            competencia=competencia_mes1.isoformat(),
            bens=bens_processados,
            depreciados=bens_depreciados,
            total=str(total_depreciado),
        )
        return GerarDepreciacaoOut(
            competencia=competencia_mes1,
            bens_processados=bens_processados,
            bens_depreciados=bens_depreciados,
            bens_totalmente_depreciados=bens_totais_finalizados,
            valor_total_depreciado=total_depreciado,
            algoritmo_versao=ALGORITMO_VERSAO,
        )


def _para_out(b: BemImobilizado) -> BemImobilizadoOut:
    return BemImobilizadoOut(
        id=b.id,
        empresa_id=b.empresa_id,
        descricao=b.descricao,
        categoria=CategoriaBem(b.categoria),
        data_aquisicao=b.data_aquisicao,
        valor_aquisicao=b.valor_aquisicao,
        taxa_depreciacao_anual=b.taxa_depreciacao_anual,
        vida_util_meses=b.vida_util_meses,
        valor_residual=b.valor_residual,
        metodo_depreciacao=MetodoDepreciacao(b.metodo_depreciacao),
        documento_fiscal_id=b.documento_fiscal_id,
        data_baixa=b.data_baixa,
        motivo_baixa=b.motivo_baixa,
        ativo=b.ativo,
        criado_em=b.criado_em,
    )
