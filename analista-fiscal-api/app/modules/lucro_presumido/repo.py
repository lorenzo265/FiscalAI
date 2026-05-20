"""Repositórios do Lucro Presumido (Sprint 11 PR1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import ApuracaoFiscal, PresuncaoLucroPresumido


@dataclass(frozen=True, slots=True)
class PresuncaoResolvida:
    """Grupo de presunção que casou com o CNAE da empresa."""

    grupo_atividade: str
    percentual_irpj: Decimal
    percentual_csll: Decimal
    cnae_pattern: str | None
    prioridade: int
    fonte: str


class PresuncaoLpRepo:
    """Leitura SCD (§8.3) de ``presuncao_lucro_presumido`` + match por CNAE."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def vigentes_em(self, em: date) -> list[PresuncaoLucroPresumido]:
        stmt = (
            select(PresuncaoLucroPresumido)
            .where(PresuncaoLucroPresumido.valid_from <= em)
            .where(
                (PresuncaoLucroPresumido.valid_to == None)  # noqa: E711
                | (PresuncaoLucroPresumido.valid_to >= em)
            )
            .order_by(PresuncaoLucroPresumido.prioridade)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def resolver_por_cnae(
        self,
        em: date,
        cnae_principal: str | None,
        *,
        faturamento_12m: Decimal | None = None,
    ) -> PresuncaoResolvida | None:
        """Match: maior prioridade (menor número) cujo ``cnae_pattern`` é
        prefixo do CNAE. Considera ``limite_receita_anual`` para regras
        condicionais (art. 15 §4º — serviços gerais ≤ R$120k/ano).
        """
        vigentes = await self.vigentes_em(em)
        cnae_norm = _normalizar_cnae(cnae_principal)

        candidatos: list[PresuncaoLucroPresumido] = []
        for v in vigentes:
            if v.cnae_pattern is None:
                # Regra condicional por faturamento (ex.: serviços ≤ 120k)
                if v.limite_receita_anual is not None:
                    if (
                        faturamento_12m is None
                        or faturamento_12m > v.limite_receita_anual
                    ):
                        continue
                candidatos.append(v)
                continue
            pattern_norm = _normalizar_cnae(v.cnae_pattern)
            if cnae_norm and cnae_norm.startswith(pattern_norm):
                candidatos.append(v)

        if not candidatos:
            return None

        # Ordenado por prioridade ASC; o primeiro é o mais específico.
        escolhido = sorted(candidatos, key=lambda x: x.prioridade)[0]
        return PresuncaoResolvida(
            grupo_atividade=escolhido.grupo_atividade,
            percentual_irpj=escolhido.percentual_irpj,
            percentual_csll=escolhido.percentual_csll,
            cnae_pattern=escolhido.cnae_pattern,
            prioridade=escolhido.prioridade,
            fonte=escolhido.fonte,
        )


def _normalizar_cnae(cnae: str | None) -> str:
    """Tira pontos/traços/espaços do CNAE para match por prefixo."""
    if not cnae:
        return ""
    return cnae.replace(".", "").replace("-", "").replace("/", "").strip()


class ApuracaoLpRepo:
    """Persiste apuração no ``apuracao_fiscal`` reaproveitando a tabela
    central criada na Sprint 2 (não duplica)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def buscar(
        self, empresa_id: UUID, competencia: date, tipo: str
    ) -> ApuracaoFiscal | None:
        stmt = select(ApuracaoFiscal).where(
            ApuracaoFiscal.empresa_id == empresa_id,
            ApuracaoFiscal.competencia == competencia,
            ApuracaoFiscal.tipo == tipo,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(
        self,
        empresa_id: UUID,
        *,
        tipo: str | None = None,
        limite: int = 24,
    ) -> list[ApuracaoFiscal]:
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .order_by(ApuracaoFiscal.competencia.desc())
            .limit(limite)
        )
        if tipo:
            stmt = stmt.where(ApuracaoFiscal.tipo == tipo)
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, apuracao: ApuracaoFiscal) -> ApuracaoFiscal:
        self._s.add(apuracao)
        await self._s.flush()
        await self._s.refresh(apuracao)
        return apuracao
