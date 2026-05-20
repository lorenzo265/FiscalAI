from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import Empresa


class EmpresaRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, empresa_id: UUID) -> Empresa | None:
        # RLS filtra por tenant automaticamente via SET LOCAL
        stmt = select(Empresa).where(Empresa.id == empresa_id, Empresa.ativa.is_(True))
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def rbt12_da_view(
        self, empresa_id: UUID, competencia: date
    ) -> Decimal | None:
        """RBT12 derivado de ``rbt12_mensal`` (view materializada da Fase 2 PR3).

        Retorna ``None`` quando a empresa não tem documentos fiscais emitidos
        até a competência informada — o service do consumidor deve aplicar
        fallback para ``empresa.faturamento_12m`` (valor declarado no onboarding).

        A view não tem RLS — segurança vem da filtragem por ``tenant_id``
        derivado da sessão atual (``current_setting('app.tenant_id')``).
        """
        stmt = text(
            """
            SELECT valor
              FROM rbt12_mensal
             WHERE empresa_id = :empresa_id
               AND tenant_id = NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid
               AND competencia <= :competencia
             ORDER BY competencia DESC
             LIMIT 1
            """
        )
        result = await self._s.execute(
            stmt, {"empresa_id": empresa_id, "competencia": competencia}
        )
        valor = result.scalar_one_or_none()
        if valor is None:
            return None
        return Decimal(valor) if not isinstance(valor, Decimal) else valor

    async def listar(self) -> list[Empresa]:
        stmt = select(Empresa).where(Empresa.ativa.is_(True)).order_by(Empresa.razao_social)
        return list((await self._s.execute(stmt)).scalars().all())

    async def cnpj_existe(self, tenant_id: UUID, cnpj: str) -> bool:
        stmt = select(Empresa.id).where(Empresa.tenant_id == tenant_id, Empresa.cnpj == cnpj)
        return (await self._s.execute(stmt)).scalar_one_or_none() is not None

    async def alocar_proximo_numero_rps(self, empresa_id: UUID) -> int:
        """Aloca atomicamente o próximo número de RPS para a empresa.

        Usa SELECT ... FOR UPDATE para serializar a alocação entre transações
        concorrentes, garantindo que a sequência por empresa seja contínua
        (exigência da maioria das prefeituras conforme ABNT NBR 15032 e ISS-e
        municipal).

        Deve ser chamado dentro de uma transação ativa — o lock é liberado no
        commit/rollback da transação corrente.
        """
        stmt = (
            select(Empresa)
            .where(Empresa.id == empresa_id, Empresa.ativa.is_(True))
            .with_for_update()
        )
        empresa = (await self._s.execute(stmt)).scalar_one_or_none()
        if empresa is None:
            raise ValueError(f"Empresa {empresa_id} não encontrada para alocar RPS")
        numero = empresa.proximo_numero_rps
        empresa.proximo_numero_rps = numero + 1
        await self._s.flush()
        return numero

    async def criar(
        self,
        tenant_id: UUID,
        cnpj: str,
        razao_social: str,
        regime_tributario: str,
        perfil_ui: str,
        *,
        nome_fantasia: str | None = None,
        anexo_simples: str | None = None,
        cnae_principal: str | None = None,
        municipio: str | None = None,
        uf: str | None = None,
        ie: str | None = None,
        im: str | None = None,
        faturamento_12m: Decimal | None = None,
    ) -> Empresa:
        empresa = Empresa(
            tenant_id=tenant_id,
            cnpj=cnpj,
            razao_social=razao_social,
            regime_tributario=regime_tributario,
            perfil_ui=perfil_ui,
            nome_fantasia=nome_fantasia,
            anexo_simples=anexo_simples,
            cnae_principal=cnae_principal,
            municipio=municipio,
            uf=uf,
            ie=ie,
            im=im,
            faturamento_12m=faturamento_12m,
        )
        self._s.add(empresa)
        await self._s.flush()
        return empresa
