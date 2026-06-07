from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.empresa.schemas import (
    EmpresaIn,
    EmpresaUpdateIn,
    _derivar_perfil_ui,
)
from app.shared.auth.jwt import TenantContext
from app.shared.db.models import Empresa
from app.shared.exceptions import (
    CnpjJaCadastrado,
    EmpresaNaoEncontrada,
    MunicipioIbgeAusente,
)

log = structlog.get_logger(__name__)


class EmpresaService:
    async def criar(
        self,
        session: AsyncSession,
        ctx: TenantContext,
        payload: EmpresaIn,
    ) -> Empresa:
        repo = EmpresaRepo(session)

        # codigo_municipio_ibge é NOT NULL no banco (migration 0049). Validar aqui
        # devolve 422 MunicipioIbgeAusente em vez de deixar o INSERT estourar 500.
        if payload.codigo_municipio_ibge is None:
            raise MunicipioIbgeAusente(
                "Empresa não pode ser cadastrada sem o código IBGE do município. "
                "Informe o código IBGE de 7 dígitos."
            )

        if await repo.cnpj_existe(ctx.tenant_id, payload.cnpj):
            raise CnpjJaCadastrado(f"CNPJ {payload.cnpj} já cadastrado para este tenant")

        perfil = _derivar_perfil_ui(payload.regime_tributario)

        empresa = await repo.criar(
            tenant_id=ctx.tenant_id,
            cnpj=payload.cnpj,
            razao_social=payload.razao_social,
            regime_tributario=payload.regime_tributario,
            perfil_ui=perfil,
            nome_fantasia=payload.nome_fantasia,
            anexo_simples=payload.anexo_simples,
            cnae_principal=payload.cnae_principal,
            municipio=payload.municipio,
            codigo_municipio_ibge=payload.codigo_municipio_ibge,
            uf=payload.uf,
            ie=payload.ie,
            im=payload.im,
            faturamento_12m=payload.faturamento_12m,
        )

        await session.commit()

        log.info(
            "empresa.criou",
            tenant_id=str(ctx.tenant_id),
            empresa_id=str(empresa.id),
            regime=empresa.regime_tributario,
        )
        return empresa

    async def listar(self, session: AsyncSession) -> list[Empresa]:
        return await EmpresaRepo(session).listar()

    async def buscar(self, session: AsyncSession, empresa_id: UUID) -> Empresa:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        return empresa

    async def atualizar(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        payload: EmpresaUpdateIn,
    ) -> Empresa:
        """Atualiza dados cadastrais da empresa (PUT — atualização parcial).

        Só aplica os campos enviados pelo cliente (``exclude_unset``). Quando
        ``regime_tributario`` muda, re-deriva ``perfil_ui`` (mesma regra do
        cadastro). ``razao_social``, ``regime_tributario`` e
        ``codigo_municipio_ibge`` são NOT NULL no banco (este último desde a
        migration 0049) — uma tentativa de limpá-los (``null`` explícito) é
        ignorada, não estoura.
        """
        dados = payload.model_dump(exclude_unset=True)
        for nao_nulo in ("razao_social", "regime_tributario", "codigo_municipio_ibge"):
            if nao_nulo in dados and dados[nao_nulo] is None:
                del dados[nao_nulo]

        perfil_ui: str | None = None
        if payload.regime_tributario is not None and "regime_tributario" in dados:
            perfil_ui = _derivar_perfil_ui(payload.regime_tributario).value

        empresa = await EmpresaRepo(session).atualizar(
            empresa_id, dados, perfil_ui=perfil_ui
        )
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        await session.commit()
        log.info(
            "empresa.atualizou",
            empresa_id=str(empresa_id),
            campos=sorted(dados.keys()),
        )
        return empresa

    async def atualizar_municipio_ibge(
        self,
        session: AsyncSession,
        empresa_id: UUID,
        codigo_municipio_ibge: str,
    ) -> Empresa:
        """Atualiza o código IBGE da empresa (PATCH manual)."""
        empresa = await EmpresaRepo(session).atualizar_municipio_ibge(
            empresa_id, codigo_municipio_ibge
        )
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        await session.commit()
        log.info(
            "empresa.municipio_ibge.atualizado",
            empresa_id=str(empresa_id),
            codigo_ibge=codigo_municipio_ibge,
        )
        return empresa

    async def marcar_iss_validada(
        self,
        session: AsyncSession,
        empresa_id: UUID,
    ) -> Empresa:
        """Confirma que o contador validou a alíquota ISS — aviso não aparece mais."""
        empresa = await EmpresaRepo(session).marcar_iss_validada(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
        await session.commit()
        log.info("empresa.iss_validada", empresa_id=str(empresa_id))
        return empresa
