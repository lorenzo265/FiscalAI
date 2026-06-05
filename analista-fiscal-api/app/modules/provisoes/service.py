"""Service de provisões trabalhistas (Sprint 8 PR2)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.provisoes.calcula_provisao import (
    ALGORITMO_VERSAO,
    aliquota_patronal_regime,
    calcular_provisoes,
)
from app.modules.provisoes.repo import ProvisoesRepo
from app.modules.provisoes.schemas import (
    GerarProvisaoIn,
    GerarProvisaoOut,
)
from app.shared.exceptions import EmpresaNaoEncontrada

log = structlog.get_logger(__name__)


class ProvisoesService:
    async def gerar_provisao_mensal(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        competencia: date,
        payload: GerarProvisaoIn,
    ) -> GerarProvisaoOut:
        """Calcula e persiste as 6 linhas de provisão da empresa para o mês.

        Idempotente: linhas já existentes (empresa, competência, tipo) são
        puladas pelo UNIQUE parcial — ``linhas_existentes`` conta quantas.
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        competencia_mes1 = date(competencia.year, competencia.month, 1)

        # Determina a alíquota previdenciária patronal regime-aware.
        # RAT e Terceiros vêm do payload (default 0 — piso conservador até
        # seed definitivo por CNAE/grau de risco).
        # Ver docs/pendencias/rat-fap-terceiros-seed.md.
        aliq_patronal = aliquota_patronal_regime(
            regime=empresa.regime_tributario,
            anexo_simples=empresa.anexo_simples,
            rat_sat=payload.rat_sat,
            aliquota_terceiros=payload.aliquota_terceiros,
        )
        resultado = calcular_provisoes(
            payload.folha_mes_total,
            empresa.regime_tributario,
            aliquota_inss_patronal=aliq_patronal,
        )

        repo = ProvisoesRepo(session)
        linhas_geradas = 0
        linhas_existentes = 0
        valor_total = Decimal("0.00")

        for linha in resultado.as_lista():
            inserida = await repo.upsert_agregada(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                competencia=competencia_mes1,
                tipo=linha.tipo,
                base_calculo=linha.base_calculo,
                aliquota=linha.aliquota,
                valor_provisao=linha.valor_provisao,
                algoritmo_versao=resultado.algoritmo_versao,
            )
            if inserida:
                linhas_geradas += 1
                valor_total += linha.valor_provisao
            else:
                linhas_existentes += 1

        await session.commit()

        log.info(
            "provisoes.lote.ok",
            empresa_id=str(empresa_id),
            competencia=competencia_mes1.isoformat(),
            regime=empresa.regime_tributario,
            anexo_simples=empresa.anexo_simples,
            aliq_patronal=str(aliq_patronal),
            folha=str(payload.folha_mes_total),
            geradas=linhas_geradas,
            existentes=linhas_existentes,
            total=str(valor_total),
        )

        return GerarProvisaoOut(
            competencia=competencia_mes1,
            linhas_geradas=linhas_geradas,
            linhas_existentes=linhas_existentes,
            valor_total_provisionado=valor_total,
            inss_aplicavel=aliq_patronal > Decimal("0"),
            algoritmo_versao=ALGORITMO_VERSAO,
        )
