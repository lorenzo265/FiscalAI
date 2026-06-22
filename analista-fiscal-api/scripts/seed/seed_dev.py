"""Seed de DESENVOLVIMENTO para a integração front↔back (Fase A — Fundação).

Cria, de forma idempotente, o mínimo para o frontend Arkan logar e ver dados:

  * 1 tenant  — slug ``demo``.
  * 1 usuário — ``demo@arkan.dev`` / ``arkan1234`` (credenciais FIXAS de dev).
  * 1 empresa — Simples Nacional, Anexo I, CNPJ válido, São Paulo/SP.

Diferença vs ``seed_1k_tenants.py`` (load test): aqui usamos os **services**
reais de auth/empresa (hash bcrypt de verdade → login funciona; perfil_ui
derivado), e o foco é uma conta única navegável, não escala.

Uso (PowerShell):

    $env:PATH = "C:\\Users\\loren\\AppData\\Roaming\\Python\\Scripts;$env:PATH"
    cd C:\\dev\\Apresentação-Ideia\\analista-fiscal-api
    poetry run python -m scripts.seed.seed_dev

Princípios:
  * §8.9 idempotência — re-rodar reaproveita tenant/usuário/empresa existentes.
  * §8.1 RLS — ativa ``app.tenant_id`` antes das queries de empresa.
  * **Não é para produção.** Falha-rápido se ``ENVIRONMENT == 'prod'``.
"""

from __future__ import annotations

import asyncio
import sys
from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Environment, get_settings
from app.modules.auth.repo import TenantRepo, UsuarioRepo
from app.modules.auth.schemas import RegisterIn
from app.modules.auth.service import AuthService
from app.modules.empresa.repo import EmpresaRepo
from app.modules.empresa.schemas import AnexoSimples, EmpresaIn, RegimeTributario
from app.modules.empresa.service import EmpresaService
from app.shared.auth.jwt import TenantContext
from app.shared.db.perf import build_async_engine
from app.shared.db.rls import set_tenant_id
from app.shared.exceptions import CnpjJaCadastrado
from scripts.seed.seed_helpers import calcular_dv_cnpj

log = structlog.get_logger(__name__)

# ── Credenciais fixas de dev (documentadas no hadoff-front-back.md) ──────────
TENANT_NOME = "Arkan Demo"
TENANT_SLUG = "demo"
USUARIO_NOME = "Contador Demo"
USUARIO_EMAIL = "demo@arkan.dev"
USUARIO_SENHA = "arkan1234"  # nosec B105 — credencial de dev, nunca prod

# Empresa SN plausível. CNPJ válido determinístico (base + DV calculado).
_CNPJ_BASE_12 = "112223330001"
EMPRESA_CNPJ = _CNPJ_BASE_12 + calcular_dv_cnpj(_CNPJ_BASE_12)
EMPRESA_RAZAO = "Comércio Demonstração Arkan LTDA"
EMPRESA_FANTASIA = "Arkan Demo Store"
EMPRESA_CNAE = "4781400"  # comércio varejista de vestuário
EMPRESA_MUNICIPIO = "São Paulo"
EMPRESA_IBGE = "3550308"
EMPRESA_UF = "SP"
EMPRESA_FAT_12M = Decimal("680000.00")  # faixa estável Anexo I


async def _seed() -> dict[str, str]:
    settings = get_settings()
    if settings.ENVIRONMENT is Environment.PROD:
        raise RuntimeError("seed_dev JAMAIS roda em ENVIRONMENT=prod")

    engine = build_async_engine(settings)
    sess_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )

    auth_service = AuthService()
    empresa_service = EmpresaService()

    try:
        # ── Tenant + usuário (idempotente via service / fallback de lookup) ──
        async with sess_factory() as session:
            tenant_repo = TenantRepo(session)
            existente = await tenant_repo.por_slug(TENANT_SLUG)
            if existente is None:
                _t, _u, _tok, _ttl = await auth_service.registrar(
                    session,
                    RegisterIn(
                        tenant_nome=TENANT_NOME,
                        tenant_slug=TENANT_SLUG,
                        usuario_nome=USUARIO_NOME,
                        usuario_email=USUARIO_EMAIL,
                        usuario_senha=USUARIO_SENHA,
                    ),
                )
                tenant_id = _t.id
                usuario_id = _u.id
                log.info("seed_dev.tenant_criado", tenant_id=str(tenant_id))
            else:
                tenant_id = existente.id
                await set_tenant_id(session, tenant_id)
                usuario = await UsuarioRepo(session).por_email(
                    tenant_id, USUARIO_EMAIL
                )
                usuario_id = usuario.id if usuario else tenant_id
                log.info("seed_dev.tenant_reutilizado", tenant_id=str(tenant_id))

        # ── Empresa (idempotente: captura CnpjJaCadastrado e relê) ──────────
        async with sess_factory() as session:
            await set_tenant_id(session, tenant_id)
            ctx = TenantContext(tenant_id=tenant_id, usuario_id=usuario_id)
            try:
                empresa = await empresa_service.criar(
                    session,
                    ctx,
                    EmpresaIn(
                        cnpj=EMPRESA_CNPJ,
                        razao_social=EMPRESA_RAZAO,
                        nome_fantasia=EMPRESA_FANTASIA,
                        regime_tributario=RegimeTributario.SIMPLES_NACIONAL,
                        anexo_simples=AnexoSimples.I,
                        cnae_principal=EMPRESA_CNAE,
                        municipio=EMPRESA_MUNICIPIO,
                        codigo_municipio_ibge=EMPRESA_IBGE,
                        uf=EMPRESA_UF,
                        faturamento_12m=EMPRESA_FAT_12M,
                    ),
                )
                empresa_id = empresa.id
                log.info("seed_dev.empresa_criada", empresa_id=str(empresa_id))
            except CnpjJaCadastrado:
                # Re-execução: localiza a empresa já seedada para reportar o id.
                empresas = await EmpresaRepo(session).listar()
                match = next(
                    (e for e in empresas if e.cnpj == EMPRESA_CNPJ), None
                )
                empresa_id = match.id if match else tenant_id
                log.info(
                    "seed_dev.empresa_reutilizada", empresa_id=str(empresa_id)
                )
    finally:
        await engine.dispose()

    return {
        "tenant_id": str(tenant_id),
        "usuario_id": str(usuario_id),
        "empresa_id": str(empresa_id),
    }


def main() -> int:
    ids = asyncio.run(_seed())
    print(
        "\n"
        "════════════════════════════════════════════════════════════\n"
        " seed_dev concluído — credenciais de DEV (Arkan / Fase A)\n"
        "════════════════════════════════════════════════════════════\n"
        f"  tenant_slug : {TENANT_SLUG}\n"
        f"  email       : {USUARIO_EMAIL}\n"
        f"  senha       : {USUARIO_SENHA}\n"
        f"  tenant_id   : {ids['tenant_id']}\n"
        f"  empresa_id  : {ids['empresa_id']}\n"
        f"  empresa cnpj: {EMPRESA_CNPJ}  (Simples Nacional, Anexo I)\n"
        "════════════════════════════════════════════════════════════\n"
        " Login no front: tenant_slug='demo', email/senha acima.\n"
        "════════════════════════════════════════════════════════════",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
